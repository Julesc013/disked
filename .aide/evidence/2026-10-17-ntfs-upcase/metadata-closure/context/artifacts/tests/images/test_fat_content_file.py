"""Real held-source/owned-worker FAT payload windows and independent frame checks."""
import argparse
import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_fat_content import fixture

PROBE=None
FAULT=None
RECORDS=[]

def sha(data):return hashlib.sha256(data).hexdigest()
def content(size='auto',digest='auto',offset=0,count=196608,**fields):
    value=dict(reference_capture_epoch='1',node_id='1',expected_file_bytes=str(size),
               metadata_digest=digest,offset=str(offset),count=str(count),
               limits=dict(bytes='196608',read_requests='512',read_chunk='4096'))
    value.update(fields);return value
def request(path,v,**fields):
    q=dict(op='file',path=str(path),offset=str(v.offset),length=str(v.length));q.update(fields);return q
def run(rows,fault=False):
    data=b''.join(json.dumps(r,sort_keys=True,separators=(',',':')).encode()+b'\n' for r in rows)
    result=subprocess.run([str(FAULT if fault else PROBE)],input=data,capture_output=True,timeout=120)
    assert result.returncode==0 and not result.stderr,result.stderr.decode(errors='replace')
    values=[json.loads(s) for s in result.stdout.splitlines()];assert len(values)==len(rows)
    for q,v in zip(rows,values):
        RECORDS.append(dict(input_sha256=sha(json.dumps(q,sort_keys=True).encode()),
                            output_sha256=sha(json.dumps(v,sort_keys=True).encode()),fault=fault,
                            has_snapshot=v.get('has_snapshot'),error=v.get('error'),
                            outcome=v.get('result',{}).get('content',{}).get('window',{}).get('outcome')))
    return values

class ContentFileTests(unittest.TestCase):
    def setUp(self):
        scratch=Path(__file__).resolve().parents[2]/'.aide-local';scratch.mkdir(exist_ok=True)
        self.folder=tempfile.TemporaryDirectory(prefix='fatcontent-',dir=scratch);self.addCleanup(self.folder.cleanup)
        self.root=Path(self.folder.name)
    def make(self,bits=12,unit=512,per=1,chain=(3,8,5),size=None):
        v,data=fixture(bits,unit=unit,per=per,chain=chain,size=size)
        path=self.root/f'内容-{bits}-{len(list(self.root.iterdir()))}.img';v.write(path)
        return path,v,data
    def expect(self,value,data,offset,count):
        self.assertTrue(value['has_snapshot'],value)
        self.assertTrue(value['retained_unchanged'])
        result=value['result'];c=result['content'];w=c['window']
        self.assertEqual(bytes.fromhex(w['data']),data[offset:offset+count])
        self.assertEqual(w['outcome'],'complete');self.assertTrue(c['observed_stable'])
        self.assertTrue(c['metadata_equal']);self.assertTrue(c['payload_equal']);self.assertTrue(c['source_equal'])
        self.assertFalse(c['atomic_snapshot']);self.assertFalse(c['source_freshness_verified'])
        self.assertFalse(w['product_dispatch_admitted']);self.assertFalse(w['authorizes_effects'])
        self.assertNotEqual(w['source_id'],'generated-content-source')
        self.assertEqual(w['source_id'],result['observation']['source_id'])
        self.assertEqual(w['capture_epoch'],result['observation']['capture_epoch'])
    def test_actual_native_files_and_fragmented_windows(self):
        rows=[];oracles=[]
        for bits in (12,16,32):
            path,v,data=self.make(bits)
            before=sha(path.read_bytes())
            for offset,count in ((0,1),(501,30),(0,196608),(len(data),1)):
                rows.append(request(path,v,content=content(offset=offset,count=count)))
                oracles.append((path,before,data,offset,count))
        for row,ex in zip(run(rows),oracles):
            path,before,data,offset,count=ex;self.expect(row,data,offset,count)
            self.assertEqual(sha(path.read_bytes()),before)
            self.assertEqual(len(row['result']['content']['metadata_rereads']),len(row['result']['capture']['regions']))
    def test_empty_and_excess_allocation(self):
        rows=[];expected=[]
        for bits in (12,16,32):
            for chain,size in (((),0),((3,8,5),19)):
                path,v,data=self.make(bits,chain=chain,size=size)
                rows.append(request(path,v,content=content()));expected.append(data)
        for row,data in zip(run(rows),expected):
            self.expect(row,data,0,196608)
            self.assertEqual(len(row['result']['content']['payload_rereads']),int(bool(data)))
    def test_maximum_window_in_actual_owned_child(self):
        path,v,data=self.make(16,unit=4096,per=16,chain=(3,8,5,11))
        row=run([request(path,v,content=content())])[0]
        self.expect(row,data,0,196608)
        self.assertEqual(len(row['result']['content']['window']['data']),393216)
        self.assertEqual(len(row['result']['content']['payload_rereads']),48)
    def test_static_request_refusals_and_generation_binding(self):
        path,v,data=self.make()
        baseline=run([request(path,v,mode='frame')])[0]['frame']
        source=baseline['result']['capture']['source_before']
        rows=[]
        for override in ({'count':'0'},{'count':'196609'},{'reference_capture_epoch':'0'},
                         {'offset':str(len(data)+1)},{'expected_file_bytes':'4294967296'},
                         {'node_id':'128'},{'metadata_digest':'sha256:bad'}):
            c=content(size=len(data),digest='sha256:'+'0'*64);c.update(override)
            rows.append(request(self.root/'does-not-exist.img',v,expected_source=source,content=c))
        for row in run(rows):self.assertIn('error',row)
        wrong=copy.deepcopy(source);wrong['bytes']=str(int(source['bytes'])+1)
        row=run([request(path,v,expected_source=wrong,content=content(size=len(data),digest='sha256:'+'0'*64))])[0]
        self.assertFalse(row['has_snapshot'],row)
    def test_metadata_digest_size_and_dynamic_budget_refusals(self):
        path,v,data=self.make()
        good=run([request(path,v,content=content(),mode='frame')])[0]['frame']
        bound=good['result']['content']['request']
        rows=[]
        for key,val in (('metadata_digest','sha256:'+'0'*64),('expected_file_bytes',str(len(data)-1)),
                        ('node_id','0')):
            c=copy.deepcopy(bound);c[key]=val;rows.append(request(path,v,content=c))
        c=copy.deepcopy(bound);c['limits']['read_requests']='1';rows.append(request(path,v,content=c))
        for row in run(rows):self.assertFalse(row['has_snapshot'],row)
    def test_short_error_and_recapture_disagreement_keep_actual_prefix(self):
        path,v,data=self.make(32)
        names=('content_short','content_error','content_verify_changed','content_metadata_changed','content_source_changed')
        rows=run([request(path,v,content=content(),fixture={'capture_fault':n}) for n in names],fault=True)
        for name,row in zip(names,rows):
            self.assertTrue(row['has_snapshot'],row)
            c=row['result']['content'];w=c['window'];self.assertFalse(c['observed_stable'])
            expected=data[:511] if name=='content_short' else b'' if name=='content_error' else data
            self.assertEqual(bytes.fromhex(w['data']),expected)
            self.assertEqual(w['outcome'],'short_read' if name=='content_short' else 'reader_error' if name=='content_error' else 'complete')
            self.assertFalse(c['source_freshness_verified'])
    def test_changed_initial_metadata_never_admits_payload(self):
        path,v,data=self.make()
        row=run([request(path,v,content=content(),fixture={'capture_fault':'verify_changed'})],fault=True)[0]
        self.assertFalse(row['has_snapshot'],row)
    def test_tampered_frames_fail_independent_reconstruction(self):
        path,v,data=self.make()
        frame=run([request(path,v,content=content(),mode='frame')])[0]['frame']
        bound=frame['result']['content']['request']
        changes=[(['content_regions',0,'offset'],'1'),(['content_regions',0,'bytes'],'00'),
                 (['content_regions',0,'error'],'5'),(['result','content','window','data'],'00'),
                 (['result','content','metadata_digest'],'sha256:'+'0'*64),
                 (['result','content','request','reference_capture_epoch'],'2'),
                 (['result','content','observed_stable'],False),
                 (['result','content','payload_rereads',0,'reread_sha256'],'sha256:'+'0'*64),
                 (['result','content','metadata_rereads',0,'matches'],False),
                 (['result','content','source_freshness_verified'],True),
                 (['result','content','source_after','bytes'],'1'),
                 (['content_regions'],[])]
        rows=[]
        for chain,val in changes:
            f=copy.deepcopy(frame);at=f
            for key in chain[:-1]:at=at[key]
            at[chain[-1]]=val;rows.append(request(path,v,content=bound,mode='verify',replace=f))
        for row in run(rows):self.assertIn('error',row)
    def test_legacy_mode_and_normal_fixture_controls(self):
        path,v,data=self.make()
        old=run([request(path,v)])[0];self.assertTrue(old['has_snapshot']);self.assertNotIn('content',old['result'])
        row=run([request(path,v,content=content(),fixture={'capture_fault':'content_short'})])[0]
        self.assertIn('error',row)
    def test_actual_fault_workers_cannot_publish_altered_content(self):
        path,v,data=self.make()
        names=('content_changed','content_region_changed','content_receipt_changed','process_changed')
        rows=run([request(path,v,content=content(),fixture={'worker_fault':n}) for n in names],fault=True)
        for row in rows:self.assertFalse(row['has_snapshot'],row)
    def test_held_source_denies_write_delete_until_actual_retirement(self):
        path,v,data=self.make()
        before=sha(path.read_bytes())
        row=run([request(path,v,content=content(),mode='held-content',fixture={'capture_fault':'content_hold'})],fault=True)[0]
        self.assertEqual(row['write_error'],'32',row);self.assertEqual(row['delete_error'],'32',row)
        self.assertFalse(row['has_snapshot'],row)
        self.assertEqual(row['retirement']['worker']['observation'],'exited',row)
        self.assertEqual(sha(path.read_bytes()),before)

def main():
    global PROBE,FAULT
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path,required=True)
    p.add_argument('--fault',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();PROBE=args.probe.resolve();FAULT=args.fault.resolve()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ContentFileTests))
    args.output.write_text(json.dumps(dict(passed=result.wasSuccessful(),test_methods=result.testsRun,cases=len(RECORDS),records=RECORDS,
                                          scope='Actual generated-file native payload workers and copied-region reconstruction; no public extraction'),indent=2)+'\n',encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
if __name__=='__main__':main()
