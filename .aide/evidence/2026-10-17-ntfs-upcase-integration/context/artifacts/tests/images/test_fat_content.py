"""Independent logical-byte oracles for the private FAT content-window reader."""
import argparse
import copy
import hashlib
import json
import random
import subprocess
import unittest
from pathlib import Path

from test_fat_capture import Volume, short, MASKS

PROBE = None
RECEIPTS = []
CASES = []

def fixture(bits=12, offset=37, unit=512, per=1, chain=(3, 8, 5), size=None):
    volume = Volume(bits, offset=offset, unit=unit, per=per)
    cluster_bytes = unit * per
    size = len(chain) * cluster_bytes - 19 if size is None else size
    volume.chain(list(chain))
    volume.directory([bytes(short(name=b'CONTENT BIN', cluster=chain[0] if chain else 0, size=size))])
    content = bytearray()
    for ordinal, cluster in enumerate(chain):
        raw = bytes((ordinal * 71 + n * 29 + n // 256) % 256 for n in range(cluster_bytes))
        volume.regions[volume.cluster_offset(cluster)] = raw
        content.extend(raw)
    return volume, bytes(content[:size])

def request(volume, offset=0, count=196608, **extra):
    return dict(source=volume.request(), node='1', offset=str(offset), count=str(count), **extra)

def change(path, value):
    return dict(path=[str(p) for p in path], value=value)

def run(requests):
    data=b''.join(json.dumps(v,sort_keys=True,separators=(',',':')).encode()+b'\n' for v in requests)
    result=subprocess.run([str(PROBE)],input=data,capture_output=True,timeout=90)
    assert result.returncode==0 and not result.stderr, result.stderr.decode(errors='replace')
    rows=[json.loads(line) for line in result.stdout.splitlines()]
    assert len(rows)==len(requests)
    RECEIPTS.append(dict(cases=len(requests), input_sha256=hashlib.sha256(data).hexdigest(),
                         output_sha256=hashlib.sha256(result.stdout).hexdigest()))
    for q,row in zip(requests,rows):
        assert row['inputs_unchanged'],row
        CASES.append(dict(input_sha256=hashlib.sha256(json.dumps(q,sort_keys=True).encode()).hexdigest(),
                          calls=row['calls'],error=row.get('error'),
                          outcome=row.get('result',{}).get('outcome'),
                          data_sha256=hashlib.sha256(bytes.fromhex(row.get('result',{}).get('data',''))).hexdigest()))
    return rows

class FatContentTests(unittest.TestCase):
    def assert_window(self, row, content, offset, count):
        self.assertNotIn('error',row,row)
        value=row['result'];expected=content[offset:offset+count]
        self.assertEqual(value['outcome'],'complete')
        self.assertEqual(bytes.fromhex(value['data']),expected)
        self.assertEqual(int(value['returned_bytes']),len(expected))
        self.assertEqual(int(value['available_bytes']),len(expected))
        self.assertEqual(int(value['next_offset']),offset+len(expected))
        self.assertEqual(value['eof'],offset+len(expected)==len(content))
        self.assertFalse(value['authorizes_effects']);self.assertFalse(value['source_freshness_verified'])
        self.assertFalse(value['filesystem_health_qualified']);self.assertFalse(value['product_dispatch_admitted'])
        for read in value['reads']:
            self.assertLessEqual(int(read['requested_bytes']),4096)
            self.assertEqual(read['returned_bytes'],read['reported_bytes'])
        for call,read in zip(row['calls'],value['reads']):
            self.assertEqual(call['offset'],read['source_offset'])
            self.assertEqual(call['bytes'],read['requested_bytes'])

    def test_fragmented_file_windows_and_units(self):
        queries=[];expected=[]
        for bits in (12,16,32):
            for unit,per in ((512,1),(1024,2),(4096,1)):
                v,content=fixture(bits,unit=unit,per=per)
                for offset,count in ((0,1),(0,196608),(unit*per-1,3),(unit*per+7,99),(len(content)-1,4096),(len(content),17)):
                    queries.append(request(v,offset,count));expected.append((content,offset,count))
        for row,ex in zip(run(queries),expected): self.assert_window(row,*ex)

    def test_random_logical_windows_have_exact_physical_ranges(self):
        rng=random.Random(450013)
        v,content=fixture(32,chain=(3,10,4,19,6,12,8),unit=1024,per=2)
        queries=[request(v,rng.randrange(len(content)+1),rng.randrange(1,30000)) for _ in range(60)]
        for q,row in zip(queries,run(queries)):
            self.assert_window(row,content,int(q['offset']),int(q['count']))
            for read in row['result']['reads']:
                logical=int(read['file_offset']);index,within=divmod(logical,2048)
                physical=v.offset+v.cluster_offset((3,10,4,19,6,12,8)[index])+within
                self.assertEqual(int(read['source_offset']),physical)
                self.assertLessEqual(within+int(read['requested_bytes']),2048)

    def test_empty_and_slack_never_reach_the_reader(self):
        queries=[];expect=[]
        for bits in (12,16,32):
            v,content=fixture(bits,chain=(),size=0)
            queries.append(request(v,no_reader=True));expect.append(content)
            v,content=fixture(bits,chain=(3,8,5),size=17)
            queries.append(request(v));expect.append(content)
        for row,content in zip(run(queries),expect):
            self.assert_window(row,content,0,196608)
            self.assertEqual(len(row['calls']),int(bool(content)))
            self.assertEqual(row['result']['excess_allocation'],bool(content))

    def test_binding_refusals_before_callbacks(self):
        v,_=fixture()
        overrides=[{'source_id':'other'},{'epoch':'2'},{'epoch':'0'}, {'fat_copy':'1'},
                   {'source_bytes':'20'},{'volume_offset':'38'}, {'volume_bytes':str(v.length-1)},
                   {'volume_offset':str((1<<64)-1)}]
        for row in run([request(v,binding=x) for x in overrides]):
            self.assertIn('error',row);self.assertEqual(row['calls'],[])

    def test_geometry_and_raw_record_contradictions_before_callbacks(self):
        v,_=fixture()
        items=[change(['geometry','bits'],'16'),change(['geometry','cluster_bytes'],'513'),
               change(['geometry','raw_boot'],'00'*512),change(['geometry','usable_layout'],False),
               change(['nodes',1,'raw'],'00'*32),change(['nodes',1,'file_bytes'],'1'),
               change(['nodes',1,'cluster'],'4'),change(['nodes',1,'raw_cluster'],'4'),
               change(['nodes',1,'attributes'],'16'),change(['nodes',1,'kind'],'directory'),
               change(['nodes',1,'volume_record_offset'],str(v.length-16)),
               change(['nodes',1,'source_record_offset'],'0'),
               change(['reads','overlap_equal'],False),change(['nodes',1,'id'],'2'),
               change(['nodes',1,'file_bytes'],'18446744073709551616')]
        for row in run([request(v,changes=[x]) for x in items]):
            self.assertIn('error',row);self.assertEqual(row['calls'],[])

    def test_extent_and_chain_contradictions_before_callbacks(self):
        v,_=fixture()
        items=[change(['nodes',1,'extents',0,key],val) for key,val in
               [('cluster','4'),('volume_offset','1'),('source_offset','1'),('allocated_bytes','513'),
                ('content_bytes','513'),('file_offset','1')]]
        items += [change(['nodes',1,'extents',1,'cluster'],'3'),change(['nodes',1,'cells',0,'index'],'4'),
                  change(['nodes',1,'cells',0,'value'],'5'),change(['nodes',1,'cells',0,'kind'],'6'),
                  change(['nodes',1,'cells'],[]),change(['nodes',1,'chain_complete'],False),
                  change(['nodes',1,'allocated_bytes'],'512'),change(['nodes',1,'chain'],'cycle'),
                  change(['nodes',1,'cells',0,'copies'],[['0','8']]),
                  change(['nodes',1,'cells',0,'copies'],[['0','8'],['0','8']]),
                  change(['nodes',1,'cells',0,'copies',1,1],'5')]
        for row in run([request(v,changes=[x]) for x in items]):
            self.assertIn('error',row);self.assertEqual(row['calls'],[])

    def test_real_damaged_and_copy_disagreeing_chains_refuse(self):
        queries=[]
        for bits in (12,16,32):
            for damage in ('free','bad','cycle','short','disagree'):
                v,_=fixture(bits)
                if damage=='free':v.link(8,0)
                if damage=='bad':v.link(8,MASKS[bits]-8)
                if damage=='cycle':v.link(8,3)
                if damage=='short':v.link(3,MASKS[bits])
                if damage=='disagree':v.link(3,4,copy_index=1)
                queries.append(request(v))
        for row in run(queries):self.assertIn('error',row);self.assertEqual(row['calls'],[])

    def test_fat32_high_bits_do_not_change_decoded_chain(self):
        v,content=fixture(32)
        v.link(3,0xa0000008,copy_index=1);v.link(8,0xb0000005,copy_index=1)
        v.link(5,0xcfffffff,copy_index=1)
        row=run([request(v)])[0];self.assert_window(row,content,0,196608)

    def test_cross_links_and_unrelated_partial_tree_remain_observations(self):
        v,content=fixture()
        v.directory([bytes(short(name=b'CONTENT BIN',cluster=3,size=len(content))),
                     bytes(short(name=b'OTHER   BIN',cluster=3,size=len(content)))])
        row=run([request(v)])[0];self.assert_window(row,content,0,196608)
        self.assertTrue(row['result']['known_cross_link'])
        v,content=fixture()
        row=run([request(v,changes=[change(['selected_tree_complete'],False),
                                   change(['observed_metadata_consistent'],False)])])[0]
        self.assert_window(row,content,0,196608)
        self.assertFalse(row['result']['selected_tree_complete'])
        self.assertFalse(row['result']['observed_metadata_consistent'])

    def test_reader_faults_keep_only_actual_prefix(self):
        v,content=fixture(32,unit=4096,per=2)
        queries=[request(v,count=14000,fault=fault,fault_at=str(at))
                 for fault in ('short','zero','throw','null','long') for at in (0,1,2)]
        for q,row in zip(queries,run(queries)):
            value=row['result'];at=int(q['fault_at']);fault=q['fault']
            prefix=at*4096+(4095 if fault=='short' else 0)
            self.assertEqual(bytes.fromhex(value['data']),content[:prefix])
            self.assertEqual(value['returned_bytes'],str(prefix))
            self.assertEqual(len(row['calls']),at+1)
            self.assertEqual(value['outcome'],'short_read' if fault in ('short','zero') else
                             'reader_error' if fault=='throw' else 'invalid_reader_view')
            self.assertNotIn('untrusted reader diagnostic',json.dumps(value))
            self.assertFalse(value['eof'])
            self.assertEqual(value['reads'][-1]['reported_bytes'],None if fault=='throw' else
                             '4095' if fault=='short' else '0' if fault=='zero' else
                             '4096' if fault=='null' else '4097')

    def test_limits_and_ranges_preflight_all_reads(self):
        v,_=fixture(32,unit=4096,per=2)
        queries=[request(v,0,0),request(v,0,196609),request(v,(1<<64)-1,1),request(v,no_reader=True),
                 request(v,0,9000,limits={'read_requests':'2'}),request(v,0,30,limits={'read_chunk':'1','read_requests':'29'})]
        queries += [request(v,limits={key:str(n)}) for key,n in
                    [('bytes',0),('bytes',196609),('read_requests',0),('read_requests',513),
                     ('read_chunk',0),('read_chunk',4097)]]
        for row in run(queries):self.assertIn('error',row);self.assertEqual(row['calls'],[])

    def test_maximum_bytes_and_chunk_budget(self):
        v,content=fixture(16,unit=4096,per=16,chain=(3,10,4,19))
        for chunk in (4096,1024):
            row=run([request(v,0,196608,limits={'read_chunk':str(chunk)})])[0]
            self.assert_window(row,content,0,196608)
            self.assertEqual(len(row['calls']),196608//chunk)

    def test_source_offsets_near_u64_maximum(self):
        v,content=fixture(32)
        v.offset=(1<<64)-1-v.length
        row=run([request(v,491,700)])[0];self.assert_window(row,content,491,700)
        self.assertTrue(all(int(c['offset'])>1<<63 for c in row['calls']))
        self.assertTrue(all(int(c['offset'])+int(c['bytes']) <= (1<<64)-1 for c in row['calls']))

    def test_large_logical_offset_without_loading_whole_file(self):
        v=Volume(32,offset=7,unit=4096,per=128)
        v.chain(list(range(3,1027)));size=1024*4096*128-17
        v.directory([bytes(short(name=b'CONTENT BIN',cluster=3,size=size))])
        data=bytes((n*17+3)%256 for n in range(8192))
        v.regions[v.cluster_offset(1026)+4096*128-8192]=data
        offset=size-4000
        row=run([request(v,offset,196608)])[0]
        self.assertNotIn('error',row,row)
        self.assertEqual(bytes.fromhex(row['result']['data']),data[-4017:-17])
        self.assertEqual(row['result']['next_offset'],str(size))
        self.assertTrue(row['result']['eof'])

def main():
    global PROBE
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();PROBE=args.probe.resolve()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FatContentTests))
    args.output.write_text(json.dumps(dict(passed=result.wasSuccessful(),test_methods=result.testsRun,
                                          cases=len(CASES),batches=RECEIPTS,records=CASES,
                                          scope='Generated supplied-reader payload maps/windows; no native source/worker/public extraction admission'),indent=2)+'\n',encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)

if __name__=='__main__': main()
