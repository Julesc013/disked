"""Independent sparse FAT volume, directory and exact-file-extent fixtures."""
import argparse
import copy
import hashlib
import json
import os
import struct
import subprocess
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from support.tempdir import fixture_parent,managed_directory

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'property'))
from test_fat import boot, packed, MASKS
from test_fat_directory import short, slots, code_units

PROBE=None
FAULT_PROBE=None
RECEIPTS=[]


class Volume:
    def __init__(self,bits=12,offset=0,unit=512,per=1,copies=2):
        self.bits=bits;self.offset=offset;self.unit=unit;self.per=per;self.copies=copies
        self.boot,self.g=boot({12:2847,16:5000,32:65525}[bits],unit,per,copies)
        self.length=self.g['total']*unit;self.table=self.g['fat_sectors']*unit
        self.data=self.g['first']*unit;self.maps=[{0:MASKS[bits]&~0xff|0xf8,1:MASKS[bits]} for _ in range(copies)]
        self.regions={0:bytes(self.boot)};self.root_cluster=2 if bits==32 else None
        self.root_offset=self.data if bits==32 else (self.g['reserved']+copies*self.g['fat_sectors'])*unit
        if bits==32:self.link(2,MASKS[bits])

    def link(self,index,value,copy_index=None):
        for n,mapping in enumerate(self.maps):
            if copy_index is None or n==copy_index:mapping[index]=value

    def chain(self,values):
        for a,b in zip(values,values[1:]+[MASKS[self.bits]]):self.link(a,b)

    def cluster_offset(self,index):return self.data+(index-2)*self.unit*self.per

    def directory(self,records,cluster=None,end=True):
        body=b''.join(records)+(bytes(32) if end else b'')
        at=self.root_offset if cluster is None else self.cluster_offset(cluster)
        self.regions[at]=body

    def request(self):
        regions=dict(self.regions)
        for n,mapping in enumerate(self.maps):regions[(self.g['reserved']+n*self.g['fat_sectors'])*self.unit]=packed(self.bits,mapping)
        return dict(op='observe',source_bytes=str(self.offset+self.length),offset=str(self.offset),length=str(self.length),copy='0',
                    regions=[dict(offset=str(self.offset+at),hex=raw.hex()) for at,raw in sorted(regions.items())])

    def write(self,path):
        request=self.request()
        with path.open('xb') as stream:
            stream.truncate(int(request['source_bytes']))
            for row in request['regions']:stream.seek(int(row['offset']));stream.write(bytes.fromhex(row['hex']))


def run(requests,probe=None,environment=None):
    data=b''.join(json.dumps(row,sort_keys=True,separators=(',',':')).encode()+b'\n' for row in requests)
    result=subprocess.run([str(PROBE if probe is None else probe)],input=data,capture_output=True,timeout=90,env=environment)
    assert result.returncode==0 and not result.stderr,result.stderr.decode(errors='replace')
    rows=[json.loads(line) for line in result.stdout.splitlines()];assert len(rows)==len(requests)
    RECEIPTS.append(dict(cases=len(requests),input_sha256=hashlib.sha256(data).hexdigest(),output_sha256=hashlib.sha256(result.stdout).hexdigest(),
                         surface='ordinary-file' if any(r['op']=='file' for r in requests) else 'supplied-reader'))
    return rows


def report(request):
    value=run([request])[0];assert value.get('inputs_unchanged') is True,value
    assert 'report' in value,value
    return value['report'],value['calls']


def diagnostic(value,code):
    return code in [x['code'] for x in value['diagnostics']] or any(code in n['diagnostics'] for n in value['nodes'])


def file_node(value,name=None):
    return next(n for n in value['nodes'] if n['kind']=='file' and (name is None or n['name_oem']==name.hex()))


class FatCaptureTests(unittest.TestCase):
    def test_empty_roots_and_all_sector_cluster_units(self):
        fixtures=[Volume(bits,offset=17,unit=unit,per=per) for bits in (12,16,32) for unit in (512,1024,2048,4096) for per in (1,2,8,128)]
        for fixture,row in zip(fixtures,run([v.request() for v in fixtures])):
            v=row['report'];self.assertTrue(v['selected_tree_complete']);self.assertTrue(v['observed_metadata_consistent'])
            self.assertEqual(int(v['geometry']['bits']),fixture.bits);self.assertEqual(len(v['nodes']),1)
            self.assertTrue(v['nodes'][0]['entries_complete']);self.assertFalse(v['filesystem_health_qualified'])
            self.assertEqual(v['allocation_scope'],'observed-tree-only')
            for call in row['calls']:
                self.assertGreaterEqual(int(call['offset']),fixture.offset)
                self.assertLessEqual(int(call['offset'])+int(call['bytes']),fixture.offset+fixture.length)
                self.assertLessEqual(int(call['bytes']),4096)

    def test_exact_file_extents_and_unread_payload(self):
        for bits in (12,16,32):
            fixture=Volume(bits,offset=4096);fixture.chain([3,5])
            item=short(name=b'CONTENT BIN',cluster=3,size=700);names,_=slots(code_units('Mixed source.bin'),item)
            fixture.directory([names,bytes(item)])
            fixture.regions[fixture.cluster_offset(3)]=b'A'*512;fixture.regions[fixture.cluster_offset(5)]=b'B'*512
            value,calls=report(fixture.request());node=file_node(value)
            self.assertEqual(node['chain'],'end');self.assertEqual(node['allocated_bytes'],'1024')
            self.assertEqual([e['cluster'] for e in node['extents']],['3','5'])
            self.assertEqual([e['content_bytes'] for e in node['extents']],['512','188'])
            self.assertEqual([e['file_offset'] for e in node['extents']],['0','512'])
            self.assertEqual([int(e['source_offset']) for e in node['extents']],[fixture.offset+fixture.cluster_offset(n) for n in (3,5)])
            self.assertTrue(node['long_name']['associated']);self.assertEqual(node['long_name']['display'],'Mixed source.bin')
            for call in calls:
                for n in (3,5):
                    first=fixture.offset+fixture.cluster_offset(n)
                    self.assertFalse(int(call['offset'])<first+512 and first<int(call['offset'])+int(call['bytes']))

    def test_nested_directory_and_dot_entries_never_followed(self):
        for bits in (12,16,32):
            fixture=Volume(bits);fixture.chain([4]);fixture.directory([bytes(short(name=b'DIR        ',attributes=16,cluster=4))])
            fixture.directory([bytes(short(name=b'.          ',attributes=16,cluster=4)),bytes(short(name=b'..         ',attributes=16)),bytes(short(name=b'EMPTY   TXT'))],cluster=4)
            value,_=report(fixture.request());self.assertTrue(value['selected_tree_complete'])
            self.assertEqual([n['kind'] for n in value['nodes']],['root','directory','dot','dot','file'])
            self.assertEqual([n['chain'] for n in value['nodes'][2:4]],['not_followed','not_followed'])
            self.assertEqual(file_node(value)['parent'],'1');self.assertEqual(file_node(value)['chain'],'empty')

    def test_names_span_noncontiguous_directory_clusters(self):
        fixture=Volume(32,offset=700);fixture.chain([2,7]);item=short(name=b'SPANNED TXT')
        name=code_units('A'*31+'.txt');raw,_=slots(name,item);self.assertEqual(len(raw),96)
        deleted=bytes([0xe5])+bytes(31)
        fixture.regions[fixture.cluster_offset(2)]=deleted*15+raw[:32]
        fixture.regions[fixture.cluster_offset(7)]=raw[32:]+bytes(item)+bytes(32)
        value,_=report(fixture.request());node=file_node(value);self.assertTrue(node['long_name']['associated'])
        self.assertEqual(node['long_name']['units'][:len(name)],list(map(str,name)))
        self.assertEqual(list(map(int,node['long_name']['source_offsets'])),[fixture.offset+fixture.cluster_offset(2)+480,fixture.offset+fixture.cluster_offset(7),fixture.offset+fixture.cluster_offset(7)+32])
        self.assertEqual(node['directory_ordinal'],'18')

    def test_end_marker_does_not_expose_slack_as_files(self):
        fixture=Volume();fixture.directory([bytes(32),bytes(short(name=b'HIDDEN  TXT',cluster=3,size=1))],end=False)
        value,_=report(fixture.request());self.assertEqual(len(value['nodes']),1);self.assertEqual(value['directory_records'],'1')

    def test_orphan_deleted_replaced_and_malformed_names(self):
        fixture=Volume();raw,_=slots(code_units('A lost name.txt'));other,_=slots(code_units('A retained name.txt'))
        fixture.directory([raw[:32],bytes([0xe5])+bytes(31),raw[:32],other,bytes(short())])
        value,_=report(fixture.request());reasons=[x['reason'] for x in value['nodes'][0]['orphan_records']]
        self.assertIn('deleted_boundary',reasons);self.assertIn('replaced_start',reasons)
        fixture.directory([raw[:32]])
        value,_=report(fixture.request());self.assertEqual(value['nodes'][0]['orphan_records'][0]['reason'],'end_marker')
        bad=bytearray(other);bad[13]^=1;fixture.directory([bytes(bad),bytes(short())]);value,_=report(fixture.request())
        self.assertFalse(file_node(value)['long_name']['associated']);self.assertIn('fat_name_metadata',file_node(value)['diagnostics'])

    def test_cycle_bad_free_reserved_short_excess_and_empty_chains(self):
        for bits in (12,16,32):
            for terminal,label in ((0,'free'),(1,'reserved'),(MASKS[bits]-8,'bad'),(3,'cycle')):
                fixture=Volume(bits);fixture.link(3,terminal);fixture.directory([bytes(short(cluster=3,size=700))]);value,_=report(fixture.request())
                self.assertEqual(file_node(value)['chain'],label);self.assertFalse(value['selected_tree_complete'])
            fixture=Volume(bits);fixture.chain([3]);fixture.directory([bytes(short(cluster=3,size=700))]);value,_=report(fixture.request())
            self.assertIn('fat_file_chain_short',file_node(value)['diagnostics'])
            fixture.chain([3,4]);fixture.directory([bytes(short(cluster=3,size=100))]);value,_=report(fixture.request())
            self.assertIn('fat_file_chain_excess',file_node(value)['diagnostics'])
            fixture.directory([bytes(short())]);value,_=report(fixture.request());self.assertEqual(file_node(value)['extents'],[])

    def test_crosslinks_annotate_every_owner(self):
        fixture=Volume();fixture.chain([3]);fixture.directory([bytes(short(name=b'ONE     TXT',cluster=3,size=10)),bytes(short(name=b'TWO     TXT',cluster=3,size=10))])
        value,_=report(fixture.request());self.assertEqual(value['cross_links'],[dict(cluster='3',owners=['1','2'])])
        for node in value['nodes'][1:]:self.assertIn('fat_cross_link',node['diagnostics'])
        self.assertFalse(value['observed_metadata_consistent']);self.assertFalse(value['filesystem_health_qualified'])

    def test_reused_directory_starts_stop_expansion(self):
        fixture=Volume(32);fixture.directory([bytes(short(name=b'LOOP       ',attributes=16,cluster=2))])
        value,_=report(fixture.request());self.assertFalse(value['selected_tree_complete'])
        self.assertTrue(diagnostic(value,'fat_directory_reused'));self.assertEqual(len(value['nodes']),2)

    def test_copies_are_explicit_and_high_raw_bits_preserved(self):
        fixture=Volume(32);fixture.chain([3]);fixture.directory([bytes(short(cluster=3,size=5))]);fixture.link(3,0,copy_index=1)
        value,_=report(fixture.request());self.assertEqual(file_node(value)['chain'],'end');self.assertTrue(diagnostic(value,'fat_copy_disagreement'))
        request=fixture.request();request['copy']='1';value,_=report(request);self.assertEqual(file_node(value)['chain'],'free')
        fixture.link(3,0xafffffff,copy_index=1);value,_=report(fixture.request());cell=file_node(value)['cells'][0]
        self.assertEqual(cell['copies'],[['0',str(MASKS[32])],['1',str(0xafffffff)]])
        self.assertFalse(diagnostic(value,'fat_copy_disagreement'))
        changed=bytearray(fixture.boot);struct.pack_into('<H',changed,40,0x81);fixture.regions[0]=bytes(changed)
        value,_=report(fixture.request());self.assertTrue(diagnostic(value,'fat_inactive_copy_selected'))

    def test_large_sparse_offsets_without_resident_table(self):
        fixture=Volume(32,offset=2**32+123);fixture.chain([70000]);fixture.directory([bytes(short(cluster=70000,size=15))])
        # Extend declared volume using an independent boot fixture; sparse data is
        # represented only where read, rather than allocating its logical length.
        raw,g=boot(1000000);fixture.boot=raw;fixture.g=g;fixture.table=g['fat_sectors']*512;fixture.data=g['first']*512
        fixture.root_offset=fixture.data;fixture.length=g['total']*512;fixture.regions={0:bytes(raw)};fixture.directory([bytes(short(cluster=70000,size=15))])
        value,calls=report(fixture.request());self.assertTrue(all(int(c['offset'])>=fixture.offset for c in calls))
        self.assertEqual(file_node(value)['extents'][0]['source_offset'],str(fixture.offset+fixture.cluster_offset(70000)))
        self.assertTrue(all(int(c['bytes'])<=4096 for c in calls))

    def test_stream_cells_cross_sector_and_large_index(self):
        requests=[];expected=[]
        for bits,count,index,raw in ((12,2847,341,b'\xf0\xff'),(16,5000,4999,b'\xff\xff'),(32,268435445,268435446,b'\xff'*4)):
            requests.append(dict(op='cell',bits=str(bits),clusters=str(count),index=str(index),cell=raw.hex()));expected.append((index*bits//8,MASKS[bits]))
        for row,(offset,value) in zip(run(requests),expected):self.assertEqual((row['status'],int(row['offset']),int(row['value'])),('0',offset,value))
        for n in (0,1,3,4):
            row=run([dict(op='cell',bits='12',clusters='2847',index='341',cell=bytes(n).hex())])[0];self.assertEqual(row['cell_status'],'7')

    def test_invalid_windows_and_limits_before_callback(self):
        valid=Volume().request();cases=[]
        for updates in ({'epoch':'0'},{'source_id':''},{'source_id':'a\x00b'},
                        {'source_bytes':str(2**64-1),'offset':str(2**64-512),'length':'513'},
                        {'length':'0'},{'offset':str(int(valid['source_bytes'])+1)}):
            request=copy.deepcopy(valid);request.update(updates);request['regions']=[];cases.append(request)
        for limit in ('nodes','depth','chain_clusters','total_clusters','records','read_requests','read_bytes','orphan_groups','compare_copies','output_bytes'):
            request=copy.deepcopy(valid);request['limits']={limit:'0'};cases.append(request)
        for row in run(cases):self.assertIn('error',row);self.assertEqual(row['calls'],[])

    def test_each_budget_keeps_explicit_partial_result(self):
        fixture=Volume();fixture.chain([3,5]);names,_=slots(code_units('A budgeted name.txt'),short(cluster=3,size=700));fixture.directory([names,bytes(short(cluster=3,size=700))])
        for limit,n,code in (('nodes',1,'fat_node_budget'),('records',1,'fat_record_budget'),('read_requests',1,'fat_read_budget'),
                             ('read_bytes',511,'fat_read_budget'),('chain_clusters',1,'fat_chain_budget'),('total_clusters',1,'fat_chain_budget'),
                             ('output_bytes',16384,'fat_output_budget')):
            request=fixture.request();request['limits']={limit:str(n)};value,_=report(request)
            self.assertFalse(value['selected_tree_complete']);self.assertTrue(diagnostic(value,code),(limit,value))
        request=fixture.request();request['limits']={'compare_copies':'1'};value,_=report(request)
        self.assertTrue(diagnostic(value,'fat_copy_comparison_budget'))

    def test_depth_and_orphan_budgets(self):
        fixture=Volume();fixture.chain([3]);fixture.chain([4]);fixture.directory([bytes(short(name=b'LEVEL1     ',attributes=16,cluster=3))])
        fixture.directory([bytes(short(name=b'LEVEL2     ',attributes=16,cluster=4))],cluster=3)
        fixture.directory([],cluster=4);request=fixture.request();request['limits']={'depth':'1'};value,calls=report(request)
        self.assertTrue(diagnostic(value,'fat_depth_budget'))
        self.assertFalse(any(int(c['offset'])==fixture.cluster_offset(4) for c in calls))
        fixture=Volume();fixture.directory([bytes([0xe5])+bytes(31)]*3);request=fixture.request();request['limits']={'orphan_groups':'1'}
        value,_=report(request);self.assertTrue(diagnostic(value,'fat_orphan_budget'))

    def test_reader_failures_and_overlap_conflict(self):
        fixture=Volume();fixture.directory([])
        for mode,code in (('short','fat_reader_short'),('oversized','fat_reader_shape'),('null','fat_reader_shape'),('throw','fat_reader_exception')):
            request=fixture.request();request['fault']=dict(call='1',kind=mode);value,_=report(request)
            self.assertTrue(diagnostic(value,code));self.assertFalse(value['selected_tree_complete'])
        fixture=Volume(unit=1024);request=fixture.request();request['fault']=dict(call='2',kind='change');value,_=report(request)
        self.assertTrue(diagnostic(value,'fat_reader_overlap_changed'));self.assertFalse(value['reads']['overlap_equal'])

    def test_every_read_failure_preserves_established_chain_dimensions(self):
        fixture=Volume(32);fixture.chain([3,5]);item=short(cluster=3,size=700);name,_=slots(code_units('Retained name.txt'),item)
        fixture.directory([name,bytes(item)]);baseline,calls=report(fixture.request())
        self.assertTrue(baseline['selected_tree_complete'])
        for number in range(1,len(calls)+1):
            request=fixture.request();request['fault']=dict(call=str(number),kind='short');value,_=report(request)
            self.assertFalse(value['selected_tree_complete']);self.assertTrue(diagnostic(value,'fat_reader_short'))
            for node in value['nodes']:
                if node['chain_complete']:self.assertIn(node['chain'],('end','empty','fixed_root'))

    def test_real_file_reread_and_metadata_faults_do_not_qualify_stability(self):
        self.assertIsNotNone(FAULT_PROBE)
        root=fixture_parent()
        self.assertTrue(root.resolve().is_relative_to(Path(os.environ['DISKED_WORK_ROOT']).resolve()))
        with managed_directory(prefix='fatfault-') as folder:
            self.assertTrue(Path(folder).resolve().is_relative_to(root.resolve()))
            fixture=Volume();path=Path(folder)/'source.img';fixture.write(path)
            request=dict(op='file',path=str(path),offset='0',length=str(fixture.length),copy='0')
            before=hashlib.sha256(path.read_bytes()).hexdigest()
            for fault in ('DISKED_FAT_TEST_VERIFY_CHANGED','DISKED_FAT_TEST_VERIFY_ERROR','DISKED_FAT_TEST_METADATA_CHANGED'):
                env=os.environ.copy();env[fault]='1'
                failed=run([request],probe=FAULT_PROBE,environment=env)[0]['result']['capture']
                normal=run([request],environment=env)[0]['result']['capture']
                self.assertFalse(failed['observed_stable']);self.assertTrue(normal['observed_stable'])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)

    def test_ordinary_image_capture_and_preservation(self):
        root=fixture_parent()
        self.assertTrue(root.resolve().is_relative_to(Path(os.environ['DISKED_WORK_ROOT']).resolve()))
        with managed_directory(prefix='fatvol-') as folder:
            self.assertTrue(Path(folder).resolve().is_relative_to(root.resolve()))
            for bits in (12,16,32):
                fixture=Volume(bits,offset=512);fixture.chain([3]);fixture.directory([bytes(short(cluster=3,size=50))])
                path=Path(folder)/f'{bits}.img';fixture.write(path);before=hashlib.sha256(path.read_bytes()).hexdigest()
                request=dict(op='file',path=str(path),offset=str(fixture.offset),length=str(fixture.length),copy='0')
                row=run([request])[0];self.assertIn('result',row,row);v=row['result'];self.assertTrue(v['capture']['observed_stable'])
                self.assertFalse(v['capture']['atomic_snapshot']);self.assertFalse(v['capture']['whole_file_hashed'])
                self.assertEqual(v['capture']['source_before'],v['capture']['source_after'])
                self.assertTrue(all(r['matches'] for r in v['capture']['regions']));self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)
                self.assertEqual([p.name for p in Path(folder).iterdir()], [f'{n}.img' for n in (12,16,32) if n<=bits])

    def test_ordinary_directory_and_hardlink_refusals(self):
        root=fixture_parent()
        self.assertTrue(root.resolve().is_relative_to(Path(os.environ['DISKED_WORK_ROOT']).resolve()))
        with managed_directory(prefix='fatbad-') as folder:
            self.assertTrue(Path(folder).resolve().is_relative_to(root.resolve()))
            request=dict(op='file',path=str(Path(folder)),offset='0',length='512',copy='0')
            self.assertIn('error',run([request])[0])
            fixture=Volume();path=Path(folder)/'source.img';fixture.write(path);alias=Path(folder)/'alias.img';os.link(path,alias)
            request.update(path=str(path),length=str(fixture.length));row=run([request])[0];self.assertIn('error',row)


def main():
    global PROBE,FAULT_PROBE
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--probe',type=Path,required=True);parser.add_argument('--fault-probe',type=Path,required=True);parser.add_argument('--output',type=Path)
    args=parser.parse_args();PROBE=args.probe.resolve();FAULT_PROBE=args.fault_probe.resolve()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FatCaptureTests))
    if args.output:args.output.write_text(json.dumps(dict(tests_run=result.testsRun,passed=result.wasSuccessful(),cases=sum(r['cases'] for r in RECEIPTS),batches=RECEIPTS),indent=2)+'\n',encoding='utf-8')
    print('FAT capture cases executed: '+str(sum(r['cases'] for r in RECEIPTS)),flush=True)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__=='__main__':main()
