"""Independent interval/category/graph and owned-file FAT allocation oracles."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from support.tempdir import managed_directory

import test_fat_capture as capture
from test_fat_capture import Volume, MASKS, boot

ARGS=None
RECORDS=[]


class SparseVolume(Volume):
    def __init__(self,bits=12,offset=17,unit=512,copies=2,clusters=None):
        super().__init__(bits,offset,unit,copies=copies)
        if clusters is not None:
            self.boot,self.g=boot(clusters,unit,1,copies)
            self.length=self.g['total']*unit;self.table=self.g['fat_sectors']*unit
            self.data=self.g['first']*unit;self.root_offset=self.data
            self.regions={0:bytes(self.boot)}

    def request(self):
        # Store only touched packing groups: never construct a resident large FAT.
        regions=dict(self.regions)
        for copy,mapping in enumerate(self.maps):
            groups={}
            for index,value in mapping.items():
                group=index//2 if self.bits==12 else index
                groups.setdefault(group,{})[index]=value
            for group,values in groups.items():
                if self.bits==12:
                    n=values.get(group*2,0)|(values.get(group*2+1,0)<<12)
                    data=n.to_bytes(3,'little');relative=group*3
                else:
                    width=self.bits//8;data=next(iter(values.values())).to_bytes(width,'little');relative=group*width
                at=(self.g['reserved']+copy*self.g['fat_sectors'])*self.unit+relative
                regions[at]=data
        return dict(op='observe',source_bytes=str(self.offset+self.length),offset=str(self.offset),length=str(self.length),copy='0',
                    regions=[dict(offset=str(self.offset+at),hex=data.hex()) for at,data in sorted(regions.items())])


def window(first,count):return dict(first_cluster=str(first),clusters=str(count))
def request(volume,first,count,**fields):return dict(volume.request(),allocation_window=window(first,count),**fields)
def run(rows,probe=None,environment=None):
    data=b''.join(json.dumps(r,separators=(',',':')).encode()+b'\n' for r in rows)
    result=subprocess.run([str(probe or ARGS.probe)],input=data,capture_output=True,timeout=45,env=environment)
    assert result.returncode==0 and not result.stderr,(result.returncode,result.stderr)
    values=[json.loads(line) for line in result.stdout.splitlines()];assert len(values)==len(rows)
    RECORDS.append(dict(surface='ordinary-file' if any(r['op']=='file' for r in rows) else 'supplied-reader',cases=len(rows),
        input_sha256=hashlib.sha256(data).hexdigest(),output_sha256=hashlib.sha256(result.stdout).hexdigest()))
    return values


def oracle(volume,first,count,copy=0):
    mask=MASKS[volume.bits];values={n:volume.maps[copy].get(n,0)&mask for n in range(first,first+count)}
    def kind(v):
        if not v:return 'free'
        if v>=mask-7:return 'end'
        if v==mask-8:return 'bad'
        if 2<=v<=volume.g['clusters']+1:return 'next'
        return 'reserved'
    kinds={n:kind(v) for n,v in values.items()};incoming={n:0 for n in values};outside=free=bad=reserved=0
    for n,v in values.items():
        if kinds[n]!='next':continue
        if v not in values:outside+=1;continue
        incoming[v]+=1;free+=kinds[v]=='free';bad+=kinds[v]=='bad';reserved+=kinds[v]=='reserved'
    cycles=set();done=set()
    for start in values:
        trail=[];seen={};n=start
        while n in values and n not in done and n not in seen and kinds[n]=='next':
            seen[n]=len(trail);trail.append(n);n=values[n]
        if n in seen:cycles.add(frozenset(trail[seen[n]:]))
        done.update(trail)
    return dict(categories={k:sum(x==k for x in kinds.values()) for k in ('free','next','end','bad','reserved')},
        links_outside_coverage=outside,links_into_free=free,links_into_bad=bad,links_into_reserved=reserved,
        merge_points=sum(n>1 for n in incoming.values()),cycle_components=len(cycles),cyclic_clusters=sum(map(len,cycles)))


class AllocationWindowTests(unittest.TestCase):
    def observed(self,v,first,count,**fields):
        row=run([request(v,first,count,**fields)])[0];self.assertTrue(row['inputs_unchanged']);self.assertIn('report',row)
        return row['report'],row['report']['allocation_window'],row['calls']

    def check_oracle(self,v,result,first,count,copy=0):
        expected=oracle(v,first,count,copy)
        for key,value in expected.items():
            actual=result[key]
            if isinstance(value,dict):actual={k:int(n) for k,n in actual.items()}
            else:actual=int(actual)
            self.assertEqual(value,actual,key)
        self.assertEqual(sum(map(int,result['categories'].values())),int(result['scanned_clusters']))

    def test_windows_categories_graph_and_both_outside_boundaries(self):
        for bits in (12,16,32):
            for unit in (512,4096):
                v=SparseVolume(bits,unit=unit)
                for n,to in {100:99,101:120,102:103,103:104,104:102,105:110,106:110,107:108,109:111,
                             111:MASKS[bits]-8,112:MASKS[bits]-9,113:MASKS[bits]}.items():v.link(n,to)
                full,result,calls=self.observed(v,100,20)
                self.check_oracle(v,result,100,20)
                self.assertTrue(result['coverage_complete']);self.assertTrue(result['comparison_complete'])
                self.assertFalse(result['all_volume_coverage']);self.assertFalse(result['unreferenced_allocation_qualified'])
                self.assertEqual('100',result['first_cluster']);self.assertEqual('120',result['covered_end'])
                self.assertIsNone(result['next_cluster']);self.assertNotIn('allocation_scan',full)
                for call in calls:self.assertLessEqual(int(call['bytes']),4096)

    def test_page_crossings_and_final_cell_are_exact(self):
        for bits,start in ((12,2730),(16,2047),(32,1023)):
            v=SparseVolume(bits);v.link(start,start+1);v.link(start+1,MASKS[bits])
            _,result,_=self.observed(v,start,4);self.check_oracle(v,result,start,4)
            _,last,_=self.observed(v,v.g['clusters']+1,1)
            self.assertTrue(last['coverage_complete']);self.assertEqual(str(v.g['clusters']+2),last['covered_end'])

    def test_larger_geometry_and_high_window_without_table_residency(self):
        v=SparseVolume(32,offset=2**32+19,clusters=1000000)
        for n,to in {800000:800002,800002:MASKS[32],800003:799999,800004:900000}.items():v.link(n,to)
        _,result,calls=self.observed(v,800000,1024)
        self.check_oracle(v,result,800000,1024)
        self.assertTrue(result['coverage_complete']);self.assertEqual('1000000',result['volume_clusters'])
        self.assertLess(sum(int(c['bytes']) for c in calls),32768)
        self.assertFalse(result['all_volume_coverage']);self.assertFalse(result['unreferenced_allocation_qualified'])

    def test_actual_all_volume_window_and_default_global_meanings(self):
        v=SparseVolume(12)
        full,result,_=self.observed(v,2,v.g['clusters'])
        self.assertTrue(result['all_volume_coverage']);self.assertTrue(result['unreferenced_allocation_qualified'])
        baseline=run([dict(v.request(),allocation_scan=True)])[0]['report']['allocation_scan']
        for key in ('categories','scanned_clusters','links_outside_coverage','cycle_components','unreferenced_allocation_qualified'):
            self.assertEqual(baseline[key],result[key])
        self.assertNotIn('scope',baseline);self.assertNotIn('allocation_scan',full)

    def test_interval_free_count_cannot_qualify_global_fsinfo(self):
        from test_fat_auxiliary import MetadataVolume
        v=MetadataVolume(32,count=1024)
        row=run([request(v,100,1024,auxiliary_checks=True)])[0]['report']
        self.assertTrue(row['allocation_window']['coverage_complete'])
        self.assertEqual('1024',row['allocation_window']['categories']['free'])
        info=row['auxiliary_checks']['fsinfo']
        self.assertFalse(info['count_comparison_applicable']);self.assertIsNone(info['free_count_matches'])

    def test_missing_copy_does_not_commit_partial_cell_and_budgets_stay_explicit(self):
        v=SparseVolume(16)
        row=run([request(v,2047,20)])[0]
        calls=row['calls'];second=(v.g['reserved']+v.g['fat_sectors'])*v.unit
        stop=next(i+1 for i,c in enumerate(calls) if int(c['offset'])>=v.offset+second and int(c['offset'])<v.offset+second+v.table and int(c['bytes'])>4)
        damaged=run([request(v,2047,20,fault=dict(call=str(stop),kind='short'))])[0]['report']
        self.assertTrue(damaged['selected_tree_complete']);r=damaged['allocation_window']
        self.assertFalse(r['coverage_complete']);self.assertEqual('0',r['scanned_clusters'])
        for limits in (dict(allocation_clusters='3'),dict(read_bytes='1024'),dict(compare_copies='1')):
            _,r,_=self.observed(v,100,20,limits=limits)
            self.assertFalse(r['coverage_complete'] and r['comparison_complete'])
            self.assertFalse(r['unreferenced_allocation_qualified'])

    def test_geometry_outside_range_and_invalid_inputs_before_callback(self):
        v=SparseVolume()
        for first,count in ((v.g['clusters']+1,2),(v.g['clusters']+2,1)):
            full,r,_=self.observed(v,first,count);self.assertTrue(full['selected_tree_complete'])
            self.assertEqual('0',r['scanned_clusters']);self.assertIn('fat_allocation_window_range',r['diagnostics'])
        for first,count in ((1,1),(2,0),(2,8193),(268435447,1)):
            r=run([request(v,first,count)])[0];self.assertIn('error',r);self.assertEqual([],r['calls'])
        r=run([request(v,2,1,allocation_scan=True)])[0];self.assertIn('error',r);self.assertEqual([],r['calls'])

    def test_copy_variants_and_finding_omissions_do_not_stop_coverage(self):
        v=SparseVolume(32)
        for n in range(100,160):v.link(n,MASKS[32],copy_index=0);v.link(n,0,copy_index=1)
        _,r,_=self.observed(v,100,100,limits=dict(allocation_findings='1'))
        self.assertTrue(r['coverage_complete']);self.assertTrue(r['comparison_complete'])
        self.assertEqual('60',r['different_cells']);self.assertGreater(int(r['omitted_findings']),0)
        self.assertEqual(1,len(r['findings']));self.assertFalse(r['details_complete'])
        _,r,_=self.observed(v,100,100,copy='1');self.check_oracle(v,r,100,100,1)

    def test_actual_ordinary_files_and_recapture_applicability(self):
        with managed_directory(prefix='fat-window-') as folder:
            for bits in (12,16,32):
                v=SparseVolume(bits,offset=512);path=Path(folder)/f'{bits}.img';v.write(path)
                before=hashlib.sha256(path.read_bytes()).hexdigest()
                req=dict(op='file',path=str(path),offset=str(v.offset),length=str(v.length),copy='0',allocation_window=window(100,32))
                value=run([req])[0]['result'];r=value['observation']['allocation_window']
                self.assertTrue(value['capture']['observed_stable']);self.assertTrue(r['coverage_complete'])
                self.check_oracle(v,r,100,32);self.assertEqual(before,hashlib.sha256(path.read_bytes()).hexdigest())
            v=SparseVolume();path=Path(folder)/'whole.img';v.write(path)
            req=dict(op='file',path=str(path),offset=str(v.offset),length=str(v.length),copy='0',allocation_window=window(2,v.g['clusters']))
            env=os.environ.copy();env['DISKED_FAT_TEST_VERIFY_CHANGED']='1'
            r=run([req],probe=ARGS.fault,environment=env)[0]['result']
            self.assertFalse(r['capture']['observed_stable']);self.assertFalse(r['observation']['allocation_window']['unreferenced_allocation_qualified'])


def main():
    global ARGS
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('probe','fault','root'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--output',type=Path);ARGS,rest=p.parse_known_args()
    ARGS.probe=ARGS.probe.resolve();ARGS.fault=ARGS.fault.resolve();ARGS.root=ARGS.root.resolve()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AllocationWindowTests))
    if ARGS.output:ARGS.output.write_text(json.dumps(dict(passed=result.wasSuccessful(),tests_run=result.testsRun,cases=sum(r['cases'] for r in RECORDS),batches=RECORDS),indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__=='__main__':main()
