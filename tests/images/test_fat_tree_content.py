"""Actual held-source content selection from native traversal records."""
import argparse,hashlib,json,subprocess,tempfile,unittest
from pathlib import Path
from test_fat_content_stream import fixture
PROBE=None;FAULT=None;RECORDS=[]

def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def image(request,path):
    with path.open('xb') as f:
        f.truncate(int(request['source_bytes']))
        for pattern in request['patterns']:
            offset=int(pattern['offset']);count=int(pattern['bytes']);salt=int(pattern['salt']);at=0
            while at<count:
                n=min(65536,count-at);data=bytes((x*37+(x>>8)*11+salt)%256 for x in range(at,at+n));f.seek(offset+at);f.write(data);at+=n
        for region in request['regions']:f.seek(int(region['offset']));f.write(bytes.fromhex(region['hex']))

def run(request,path,fault=False,extra=None):
    value=dict(path=str(path),offset=request['offset'],length=request['length'],copy=request['copy']);value.update(extra or {})
    r=subprocess.run([str(FAULT if fault else PROBE)],input=json.dumps(value).encode(),capture_output=True,timeout=120)
    assert r.returncode==0 and not r.stderr,r.stderr.decode(errors='replace')
    rows=[json.loads(x) for x in r.stdout.splitlines()];assert rows[-1]['kind']=='summary'
    tree=[x for x in rows if x['kind']=='tree'];content=[x for x in rows if x['kind']=='content'];assert tree
    records={e['key']:e for t in tree for e in t['frame']['page']['events'] if e['type']=='record' and e['kind']=='3'}
    original=path.read_bytes();data=bytearray();previous=None
    for row in content:
        frame=row['frame'];p=frame['page'];assert frame['schema']=='org.disked.fat-tree-content-frame/1' and frame['directory_membership']=='held-source-traversal'
        assert frame['record']==records[row['key']] and p['selection']['raw_record']==frame['record']['raw']
        assert p['selection']['source_id']==tree[0]['frame']['page']['binding']['source_id'] and p['selection']['capture_id']==tree[0]['frame']['page']['binding']['capture_id']
        assert p['file_offset']==str(len(data));part=bytes.fromhex(p['data']);assert sha(part)==p['data_sha256'];data.extend(part)
        body=dict(p);digest=body.pop('page_digest');assert sha(b'disked:fat-content-stream-page:1\n'+json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())==digest
        assert p['previous_page_digest']==previous;previous=digest
        for region in frame['regions']:
            first=int(region['offset']);count=int(region['requested']);raw=original[first:first+count]
            assert bytes.fromhex(region['bytes'])==raw and bytes.fromhex(region['reread_bytes'])==raw and region['matches']
        for check in frame['checks']:
            expected=not check['cancelled'] and check['read_consistent'] and check['code'] is None and check['metadata']==frame['source_before']
            assert check['applicable']==expected
        assert not p['authorizes_effects']
    RECORDS.append(dict(content_pages=len(content),bytes=len(data),data_sha256=sha(data),files=int(rows[-1]['files']),status=content[-1]['frame']['page']['status'] if content else 'not_admitted',extra=extra))
    return bytes(data),content

class NativeTreeContent(unittest.TestCase):
    def test_actual_fat_variants_and_membership(self):
        for bits,clusters in ((12,2847),(16,12000),(32,65525)):
            request,expected,_,_=fixture(bits,clusters)
            folder=Path(tempfile.mkdtemp(prefix='disked-tree-content-'));path=folder/'source.img';image(request,path);before=sha(path.read_bytes())
            data,content=run(request,path);self.assertEqual(expected,data);self.assertEqual('complete',content[-1]['frame']['page']['status']);self.assertEqual(before,sha(path.read_bytes()))
    def test_actual_large_chain_same_handle(self):
        request,expected,_,_=fixture(16,40000,nodes=list(range(3,33003)))
        folder=Path(tempfile.mkdtemp(prefix='disked-tree-content-large-'));path=folder/'source.img';image(request,path);before=sha(path.read_bytes())
        data,content=run(request,path);self.assertEqual(expected,data);self.assertGreater(len(content),128);self.assertEqual(before,sha(path.read_bytes()))
    def test_cancel_preserves_historical_prefix(self):
        request,expected,_,_=fixture(16,40000,nodes=list(range(3,33003)))
        folder=Path(tempfile.mkdtemp(prefix='disked-tree-content-cancel-'));path=folder/'source.img';image(request,path);before=sha(path.read_bytes())
        data,content=run(request,path,extra=dict(cancel_after='1'));self.assertEqual(expected[:len(data)],data)
        self.assertEqual('partial',content[-1]['frame']['page']['status']);self.assertFalse(content[-1]['frame']['page']['applicable']);self.assertEqual(before,sha(path.read_bytes()))
    def test_source_disagreement_cannot_admit_content(self):
        request,_,_,_=fixture();folder=Path(tempfile.mkdtemp(prefix='disked-tree-content-fault-'));path=folder/'source.img';image(request,path);before=sha(path.read_bytes())
        for fault in ('verify_changed','metadata_changed','short_read'):
            data,content=run(request,path,True,dict(fixture=dict(file_fault=fault)));self.assertFalse(data);self.assertFalse(content)
        self.assertEqual(before,sha(path.read_bytes()))

def main():
    global PROBE,FAULT
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('probe','fault','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();PROBE=a.probe.resolve();FAULT=a.fault.resolve()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NativeTreeContent))
    a.output.write_text(json.dumps(dict(passed=result.wasSuccessful(),test_methods=result.testsRun,cases=len(RECORDS),records=RECORDS),indent=2)+'\n',encoding='utf-8',newline='\n')
    return 0 if result.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
