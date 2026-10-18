"""Independent full FAT allocation/count/functional-graph and file oracles."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from support.tempdir import fixture_parent,managed_directory
import unittest

import test_fat_capture as capture
from test_fat_capture import Volume, short, MASKS


def request(volume, **limits):
    out = volume.request()
    out['allocation_scan'] = True
    if limits:
        out['limits'] = {key:str(value) for key,value in limits.items()}
    return out


def observe(volume, **limits):
    value, calls = capture.report(request(volume, **limits))
    return value, value['allocation_scan'], calls


def oracle(volume, count=None):
    count = volume.g['clusters'] if count is None else count
    mapping = volume.maps[0]
    mask = MASKS[volume.bits]
    def kind(value):
        value &= mask
        if value == 0: return 'free'
        if value >= mask-7: return 'end'
        if value == mask-8: return 'bad'
        if 2 <= value <= volume.g['clusters']+1: return 'next'
        return 'reserved'
    values = {n:mapping.get(n,0)&mask for n in range(2,count+2)}
    kinds = {n:kind(v) for n,v in values.items()}
    categories = {k:sum(v==k for v in kinds.values()) for k in ('free','next','end','bad','reserved')}
    incoming = {n:0 for n in values}
    outside=free=bad=reserved=0
    for n,k in kinds.items():
        if k != 'next': continue
        target = values[n]
        if target not in values: outside += 1; continue
        incoming[target] += 1
        free += kinds[target]=='free'
        bad += kinds[target]=='bad'
        reserved += kinds[target]=='reserved'
    cycles = set()
    finished = set()
    for start in values:
        path=[];seen={};n=start
        while n in values and n not in finished and n not in seen and kinds[n]=='next':
            seen[n]=len(path);path.append(n);n=values[n]
        if n in seen:
            cycles.add(frozenset(path[seen[n]:]))
        finished.update(path)
    return dict(categories=categories,links_outside_coverage=outside,links_into_free=free,
                links_into_bad=bad,links_into_reserved=reserved,merge_points=sum(n>1 for n in incoming.values()),
                cycle_components=len(cycles),cyclic_clusters=sum(map(len,cycles)))


class AllocationScanTests(unittest.TestCase):
    def assert_oracle(self, volume, result, count=None):
        expected=oracle(volume,count)
        for key,value in expected.items():
            actual=result[key]
            if isinstance(value,dict):actual={k:int(v) for k,v in actual.items()}
            else:actual=int(actual)
            self.assertEqual(actual,value,key)
        self.assertEqual(sum(map(int,result['categories'].values())),int(result['scanned_clusters']))

    def test_full_empty_all_types_sector_sizes_and_offset(self):
        for bits in (12,16,32):
            for unit in (512,1024,2048,4096):
                volume=Volume(bits,unit=unit,offset=4097)
                value,scan,calls=observe(volume)
                self.assertTrue(scan['coverage_complete']);self.assertTrue(scan['comparison_complete'])
                self.assertEqual(scan['scanned_clusters'],str(volume.g['clusters']))
                self.assertIsNone(scan['next_cluster']);self.assertTrue(scan['tree_ownership_complete'])
                self.assertTrue(scan['unreferenced_allocation_qualified']);self.assertEqual(scan['allocated_without_observed_owner'],'0')
                self.assertEqual(value['allocation_scope'],'all-data-clusters');self.assertTrue(value['selected_tree_complete'])
                self.assertFalse(value['filesystem_health_qualified']);self.assert_oracle(volume,scan)
                for call in calls:
                    at=int(call['offset']);size=int(call['bytes'])
                    self.assertGreaterEqual(at,volume.offset);self.assertLessEqual(at+size,volume.offset+volume.length)
                    self.assertLessEqual(size,4096)

    def test_global_cycles_merges_and_invalid_targets(self):
        for bits in (12,16,32):
            volume=Volume(bits)
            for a,b in {3:4,4:5,5:4,6:6,7:8,8:9,9:7,10:4,11:12,13:14,14:MASKS[bits]-8,15:16,16:1,17:MASKS[bits]}.items():volume.link(a,b)
            value,scan,_=observe(volume)
            self.assert_oracle(volume,scan);self.assertEqual(scan['cycle_components'],'3');self.assertEqual(scan['cyclic_clusters'],'6')
            self.assertEqual(scan['merge_points'],'1');self.assertEqual(scan['links_into_free'],'1')
            self.assertEqual(scan['links_into_bad'],'1');self.assertEqual(scan['links_into_reserved'],'1')
            self.assertTrue(scan['tree_ownership_complete']);self.assertTrue(scan['unreferenced_allocation_qualified'])
            self.assertFalse(scan['prefix_graph_consistent']);self.assertFalse(value['observed_metadata_consistent'])
            self.assertTrue(value['tree_metadata_consistent']);self.assertTrue(value['selected_tree_complete'])

    def test_owner_and_unreferenced_allocation_dimensions(self):
        for bits in (12,16,32):
            volume=Volume(bits);volume.chain([3,4]);volume.chain([7,8])
            volume.directory([bytes(short(cluster=3,size=700))]);value,scan,_=observe(volume)
            self.assertEqual(scan['allocated_without_observed_owner'],'2');self.assertTrue(scan['unreferenced_allocation_qualified'])
            self.assertFalse(value['observed_metadata_consistent'])
            self.assertTrue(value['tree_metadata_consistent']);self.assertTrue(value['selected_tree_complete'])
            volume.directory([bytes(short(cluster=3,size=700)),bytes(short(name=b'SHARED  BIN',cluster=4,size=20))])
            value,scan,_=observe(volume)
            self.assertFalse(scan['tree_ownership_complete']);self.assertFalse(scan['unreferenced_allocation_qualified'])
            self.assertEqual(scan['allocated_without_observed_owner'],'2');self.assertTrue(value['selected_tree_complete'])

    def test_page_crossing_fat12_cell_and_padding_exclusion(self):
        volume=Volume();volume.link(2730,2731);volume.link(2731,MASKS[12]);volume.link(3000,MASKS[12])
        # Cluster2730 starts at4095;3000 is outside geometry and stays table padding.
        value,scan,calls=observe(volume);self.assert_oracle(volume,scan)
        self.assertEqual(scan['categories']['next'],'1');self.assertEqual(scan['categories']['end'],'1')
        first=volume.offset+volume.g['reserved']*volume.unit
        self.assertTrue(any(int(c['offset'])==first+4096 for c in calls))
        self.assertEqual(scan['allocated_without_observed_owner'],'2');self.assertTrue(value['selected_tree_complete'])

    def test_raw_variants_and_interpreted_disagreements(self):
        volume=Volume(32);volume.link(7,0xffffffff,copy_index=1)
        volume.link(7,0x0fffffff,copy_index=0)
        _,scan,_=observe(volume);self.assertEqual(scan['different_cells'],'0');self.assertEqual(scan['raw_variant_cells'],'1')
        self.assertTrue(scan['comparison_complete']);self.assertTrue(scan['unreferenced_allocation_qualified'])
        volume.link(7,0,copy_index=1);value,scan,_=observe(volume)
        self.assertEqual(scan['different_cells'],'1');self.assertFalse(scan['unreferenced_allocation_qualified'])
        self.assertTrue(value['selected_tree_complete']);self.assertFalse(value['observed_metadata_consistent'])
        self.assertTrue(any(f['code']=='fat_allocation_copy_disagreement' for f in scan['findings']))

    def test_copy_choice_and_incomplete_comparison(self):
        volume=Volume();volume.link(8,MASKS[12],copy_index=0)
        rows=capture.run([dict(request(volume),copy=str(copy)) for copy in (0,1)])
        self.assertEqual(rows[0]['report']['allocation_scan']['categories']['end'],'1')
        self.assertEqual(rows[1]['report']['allocation_scan']['categories']['end'],'0')
        value,scan,_=observe(volume,compare_copies=1)
        self.assertTrue(scan['coverage_complete']);self.assertFalse(scan['comparison_complete'])
        self.assertFalse(scan['unreferenced_allocation_qualified']);self.assertFalse(value['selected_tree_complete'])

    def test_prefix_missing_links_are_not_free(self):
        volume=Volume();volume.link(3,50);value,scan,_=observe(volume,allocation_clusters=10)
        self.assert_oracle(volume,scan,10);self.assertFalse(scan['coverage_complete']);self.assertEqual(scan['next_cluster'],'12')
        self.assertEqual(scan['links_outside_coverage'],'1');self.assertEqual(scan['links_into_free'],'0')
        self.assertTrue(value['selected_tree_complete']);self.assertFalse(scan['unreferenced_allocation_qualified'])
        self.assertIn('fat_allocation_cluster_budget',scan['diagnostics'])

    def test_detail_count_and_output_budget_preserve_full_counts(self):
        volume=Volume();[volume.link(n,MASKS[12]) for n in range(3,300)]
        for limits in ({'allocation_findings':1},{'output_bytes':16384}):
            value,scan,_=observe(volume,**limits)
            self.assertTrue(scan['coverage_complete']);self.assertTrue(scan['prefix_analysis_complete'])
            self.assertEqual(scan['allocated_without_observed_owner'],'297');self.assertFalse(scan['details_complete'])
            self.assertEqual(int(scan['total_findings']),len(scan['findings'])+int(scan['omitted_findings']))
            self.assertLessEqual(len(json.dumps(value,separators=(',',':')).encode()),limits.get('output_bytes',1048576))
            self.assert_oracle(volume,scan)

    def test_every_scan_read_failure_preserves_tree(self):
        volume=Volume();value,scan,calls=observe(volume)
        plain,tree_calls=capture.report(volume.request());self.assertTrue(plain['selected_tree_complete'])
        requests=[]
        for number in range(len(tree_calls)+1,len(calls)+1):
            for kind in ('short','oversized','null','throw','change'):
                r=request(volume);r['fault']=dict(call=str(number),kind=kind);requests.append(r)
        for supplied,row in zip(requests,capture.run(requests)):
            v=row['report'];s=v['allocation_scan'];self.assertTrue(v['selected_tree_complete'])
            if s['coverage_complete']:
                self.assertEqual(supplied['fault']['kind'],'change')
                self.assertGreater(int(s['different_cells']),0)
                self.assertFalse(s['unreferenced_allocation_qualified'])
                continue
            self.assertFalse(s['unreferenced_allocation_qualified']);self.assertTrue(s['diagnostics'])
            self.assertEqual(s['covered_end'],str(2+int(s['scanned_clusters'])))
            self.assertEqual(v['nodes'][0]['chain'],'fixed_root');self.assertTrue(v['nodes'][0]['entries_complete'])

    def test_combined_read_and_byte_budgets(self):
        volume=Volume();_,tree_calls=capture.report(volume.request())
        for limits in ({'read_requests':len(tree_calls)}, {'read_bytes':sum(int(c['bytes']) for c in tree_calls)}, {'read_requests':len(tree_calls)+1}):
            value,scan,_=observe(volume,**limits)
            self.assertTrue(value['selected_tree_complete']);self.assertFalse(scan['coverage_complete'])
            self.assertIn('fat_read_budget',scan['diagnostics']);self.assertFalse(scan['unreferenced_allocation_qualified'])
        for key,max_value in (('allocation_clusters',262144),('allocation_findings',128)):
            for n in (0,max_value+1):
                r=request(volume,**{key:n});row=capture.run([r])[0]
                self.assertIn('error',row);self.assertEqual(row['calls'],[])

    def test_default_behavior_and_unusable_layout(self):
        volume=Volume();plain,_=capture.report(volume.request())
        self.assertNotIn('allocation_scan',plain);self.assertNotIn('tree_metadata_consistent',plain)
        r=volume.request();r['allocation_scan']=False;disabled,_=capture.report(r);self.assertEqual(plain,disabled)
        volume.boot[510]=0;volume.regions[0]=bytes(volume.boot)
        value,_=capture.report(request(volume))
        self.assertIsNone(value['allocation_scan']);self.assertEqual(value['allocation_scope'],'not-observed')

    def test_wide_origin_and_incomplete_tree_ownership(self):
        volume=Volume(offset=2**48+17);volume.chain([3]);volume.directory([bytes(short(cluster=3,size=12))])
        value,scan,calls=observe(volume)
        self.assertTrue(scan['coverage_complete']);self.assertTrue(scan['unreferenced_allocation_qualified'])
        self.assertTrue(all(int(c['offset'])>=volume.offset for c in calls));self.assert_oracle(volume,scan)
        value,scan,_=observe(volume,nodes=1)
        self.assertTrue(scan['coverage_complete']);self.assertFalse(value['selected_tree_complete'])
        self.assertFalse(scan['tree_ownership_complete']);self.assertFalse(scan['unreferenced_allocation_qualified'])
        self.assertEqual(scan['allocated_without_observed_owner'],'1')

    def test_ordinary_files_and_recapture_faults(self):
        root=fixture_parent()
        self.assertTrue(root.resolve().is_relative_to(Path(os.environ['DISKED_WORK_ROOT']).resolve()))
        with managed_directory(prefix='fatscan-') as folder:
            self.assertTrue(Path(folder).resolve().is_relative_to(root.resolve()))
            for bits in (12,16,32):
                volume=Volume(bits,offset=512);volume.chain([3,4]);path=Path(folder)/f'{bits}.img';volume.write(path)
                before=hashlib.sha256(path.read_bytes()).hexdigest()
                r=dict(op='file',path=str(path),offset='512',length=str(volume.length),copy='0',allocation_scan=True)
                value=capture.run([r])[0]['result'];self.assertTrue(value['observation']['allocation_scan']['coverage_complete'])
                self.assertTrue(value['capture']['observed_stable']);self.assert_oracle(volume,value['observation']['allocation_scan'])
                for fault in ('DISKED_FAT_TEST_VERIFY_CHANGED','DISKED_FAT_TEST_VERIFY_ERROR','DISKED_FAT_TEST_METADATA_CHANGED'):
                    env=os.environ.copy();env[fault]='1'
                    denied=capture.run([r],probe=capture.FAULT_PROBE,environment=env)[0]['result']
                    normal=capture.run([r],environment=env)[0]['result']
                    self.assertFalse(denied['capture']['observed_stable']);self.assertTrue(normal['capture']['observed_stable'])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe',type=Path,required=True);parser.add_argument('--fault-probe',type=Path,required=True)
    parser.add_argument('--output',type=Path);args=parser.parse_args()
    capture.PROBE=args.probe.resolve();capture.FAULT_PROBE=args.fault_probe.resolve()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AllocationScanTests))
    if args.output:args.output.write_text(json.dumps(dict(tests_run=result.testsRun,passed=result.wasSuccessful(),
        cases=sum(r['cases'] for r in capture.RECEIPTS),batches=capture.RECEIPTS),indent=2)+'\n',encoding='utf-8')
    print('FAT allocation scan cases executed: '+str(sum(r['cases'] for r in capture.RECEIPTS)),flush=True)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__=='__main__':main()
