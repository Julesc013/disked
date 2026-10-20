"""Independent complete mapped FAT file/destination/checkpoint/native-worker oracles."""
import argparse,copy,hashlib,json,os,subprocess,time,unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from support.tempdir import managed_directory
from test_fat_content import fixture
from test_acquisition_worker import map_check,owned_process,K

FILE=None;FAULT=None;WORKER=None;WORKER_FAULT=None;FAT=None
RECORDS=[]
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sha(v):return 'sha256:'+hashlib.sha256(v).hexdigest()
def invoke(probe,q,env=None):
    data=canonical(q);p=subprocess.run([str(probe)],input=data,capture_output=True,timeout=120,env=env)
    assert p.returncode in (0,3) and not p.stderr,(p.returncode,p.stderr.decode(errors='replace'))
    v=json.loads(p.stdout);RECORDS.append(dict(input_sha256=sha(data),output_sha256=sha(p.stdout),exit_code=p.returncode,
                                            mode=q['mode'],outcome=v.get('outcome',{}).get('status'),refusal=v.get('refusal')))
    return v
def options(chunk=65536):return dict(chunk_bytes=str(chunk),retry_limit='0',read_policy='ordinary',substitution='stop')

class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.folder=managed_directory(prefix='fatextract-');self.addCleanup(self.folder.cleanup);self.root=Path(self.folder.name)
    def make(self,bits=12,unit=512,per=1,chain=(3,8,5),size=None):
        v,data=fixture(bits,unit=unit,per=per,chain=chain,size=size)
        path=self.root/f'源-{bits}-{len(list(self.root.iterdir()))}.img';v.write(path)
        raw=canonical(dict(op='file',path=str(path),offset=str(v.offset),length=str(v.length),mode='frame'))+b'\n'
        p=subprocess.run([str(FAT)],input=raw,capture_output=True,timeout=30)
        assert p.returncode==0 and not p.stderr,p.stderr
        observed=json.loads(p.stdout)['frame']['result']['observation'];observed['capture_epoch']='0'
        selector=dict(kind='fat-file',volume_offset=str(v.offset),volume_bytes=str(v.length),fat_copy='0',node_id='1',
                      expected_file_bytes=str(len(data)),metadata_digest=sha(canonical(observed)))
        return path,v,data,selector
    def request(self,path,selector,mode='start',chunk=65536):
        stem=str(len(list(self.root.iterdir())))
        return dict(mode=mode,source=str(path),destination=str(self.root/('输出-'+stem+'.bin')),
                    map=str(self.root/('copy-'+stem+'.map')),logical_source=selector,options=options(chunk))
    def verify(self,q,value,data):
        self.assertNotIn('refusal',value,value);self.assertEqual(value['outcome']['status'],'completed',value)
        self.assertEqual(Path(q['destination']).read_bytes(),data)
        self.assertEqual(value['outcome']['checkpoint_bytes'],str(len(data)))
        plan=value['plan'];self.assertEqual(plan['schema'],'org.disked.acquisition-plan-prototype/2')
        self.assertEqual(plan['bytes'],str(len(data)));self.assertEqual(plan['resources']['source']['end'],str(len(data)))
        self.assertEqual(plan['resources']['backing']['end'],str(Path(q['source']).stat().st_size))
        self.assertEqual(plan['resources']['backing']['access'],'read')
        self.assertEqual(plan['logical_source'],q['logical_source'])
        map_check(Path(q['map']),data)
    def test_complete_fragmented_files_all_variants(self):
        for bits in (12,16,32):
            path,v,data,sel=self.make(bits);before=sha(path.read_bytes())
            for chunk in (4096,65536,1048576):
                q=self.request(path,sel,chunk=chunk);out=invoke(FILE,q);self.verify(q,out,data)
                self.assertEqual(sha(path.read_bytes()),before)
    def test_multiple_content_windows_and_acquisition_chunks(self):
        path,v,data,sel=self.make(16,unit=4096,per=16,chain=(3,8,5,11,7,15,4,20,9,24,6,28,10,32,12,35,13,39))
        self.assertGreater(len(data),1048576)
        for chunk in (65536,1048576):
            q=self.request(path,sel,chunk=chunk);self.verify(q,invoke(FILE,q),data)
    def test_empty_files_and_slack(self):
        for bits in (12,16,32):
            for chain,size in (((),0),((3,8,5),17)):
                path,v,data,sel=self.make(bits,chain=chain,size=size);q=self.request(path,sel)
                self.verify(q,invoke(FILE,q),data)
    def test_prepare_and_bad_selection_have_no_outputs(self):
        path,v,data,sel=self.make();q=self.request(path,sel,mode='prepare')
        value=invoke(FILE,q);self.assertNotIn('refusal',value,value)
        self.assertFalse(Path(q['destination']).exists());self.assertFalse(Path(q['map']).exists())
        for key,val in (('metadata_digest','sha256:'+'0'*64),('expected_file_bytes','1'),('node_id','0'),('fat_copy','1'),('volume_offset','0')):
            bad=copy.deepcopy(sel);bad[key]=val;q=self.request(path,bad)
            out=invoke(FILE,q);self.assertIn('refusal',out);self.assertFalse(Path(q['destination']).exists());self.assertFalse(Path(q['map']).exists())
    def test_destination_alias_no_clobber_and_grants(self):
        path,v,data,sel=self.make();before=sha(path.read_bytes())
        q=self.request(path,sel);q['destination']=str(path);self.assertIn('refusal',invoke(FILE,q))
        q=self.request(path,sel);Path(q['destination']).write_bytes(b'existing')
        self.assertIn('refusal',invoke(FILE,q));self.assertEqual(Path(q['destination']).read_bytes(),b'existing')
        q=self.request(path,sel);q['map']=str(path);self.assertIn('refusal',invoke(FILE,q))
        for flag in ('source_read','destination_write','map_write','host_effects'):
            q=self.request(path,sel);q['grant']=dict(plan_digest='$prepared',source_read=True,destination_write=True,map_write=True,host_effects=True)
            q['grant'][flag]=False;value=invoke(FILE,q)
            self.assertEqual(value['outcome']['status'],'refused',value)
            self.assertFalse(Path(q['destination']).exists());self.assertFalse(Path(q['map']).exists())
        self.assertEqual(sha(path.read_bytes()),before)
    def test_fault_partial_write_and_resume_complete_file(self):
        path,v,data,sel=self.make(16,unit=4096,per=16,chain=(3,8,5,11,7));q=self.request(path,sel)
        env=os.environ.copy();env['DISKED_ACQ_TEST_PARTIAL_WRITE']='1'
        bad=invoke(FAULT,q,env);self.assertNotEqual(bad['outcome']['status'],'completed',bad)
        self.assertTrue(Path(q['map']).exists());q['mode']='resume'
        self.verify(q,invoke(FAULT,q),data)
    def test_source_and_destination_changes_refuse_resume(self):
        for change in ('source','destination'):
            path,v,data,sel=self.make(16,unit=4096,per=16);q=self.request(path,sel,chunk=4096)
            env=os.environ.copy();env['DISKED_ACQ_TEST_STOP_AFTER']='4096';setup=invoke(FAULT,q,env)
            self.assertEqual(setup['outcome']['status'],'paused',setup)
            target=Path(q[change])
            # Preserve the fixture's holes: this case changes exactly one byte,
            # not the allocation of its entire potentially large source image.
            with target.open('r+b') as stream:
                original=stream.read(1);self.assertEqual(len(original),1)
                stream.seek(0);stream.write(bytes([original[0]^1]))
            protected={k:Path(q[k]).read_bytes() for k in ('destination','map')}
            q['mode']='resume';out=invoke(FAULT,q)
            self.assertTrue('refusal' in out or out['outcome']['status']!='completed',out)
            for key,raw in protected.items():self.assertEqual(Path(q[key]).read_bytes(),raw)
    def test_fabricated_byte_policies_are_not_admitted(self):
        path,v,data,sel=self.make()
        for policy,substitution,retries in (('failing-read-mostly','stop','0'),('ordinary','zero-fill','0'),('ordinary','stop','1')):
            q=self.request(path,sel);q['options'].update(read_policy=policy,substitution=substitution,retry_limit=retries)
            self.assertIn('refusal',invoke(FILE,q));self.assertFalse(Path(q['destination']).exists())
    def test_actual_contained_worker_preparation_and_execution(self):
        path,v,data,sel=self.make(16,unit=4096,per=16,chain=(3,8,5,11,7))
        q=self.request(path,sel);state=self.root/'state';state.mkdir()
        prepared=invoke(WORKER,dict(mode='prepare',source=q['source'],destination=q['destination'],map=q['map'],state_directory=str(state),logical_source=sel))
        self.assertNotIn('refusal',prepared,prepared)
        self.assertFalse(Path(q['destination']).exists());self.assertFalse(Path(q['map']).exists())
        grant=dict(definition_digest=prepared['definition_digest'],source_read=True,destination_write=True,map_write=True,host_effects=True)
        started=invoke(WORKER,dict(mode='start',definition=prepared['definition'],grant=grant))
        self.assertNotIn('refusal',started,started)
        operation=started['operation_id'];deadline=time.monotonic()+15
        while True:
            out=invoke(WORKER,dict(mode='inspect',operation_id=operation,state_directory=str(state)))
            if out.get('value',{}).get('state',{}).get('phase')=='finished':break
            self.assertLess(time.monotonic(),deadline,out);time.sleep(.02)
        handle=owned_process(out['value']['state'],WORKER)
        if handle:
            try:self.assertEqual(K.WaitForSingleObject(handle,2000),0,out)
            finally:K.CloseHandle(handle)
        self.assertEqual(out['value']['state']['outcome']['status'],'completed',out)
        self.assertEqual(Path(q['destination']).read_bytes(),data);map_check(Path(q['map']),data)

def main():
    global FILE,FAULT,WORKER,WORKER_FAULT,FAT
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('file','fault','worker','worker-fault','fat','output'):p.add_argument('--'+arg,required=True,type=Path)
    a=p.parse_args();FILE=a.file;FAULT=a.fault;WORKER=a.worker;WORKER_FAULT=a.worker_fault;FAT=a.fat
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ExtractionTests))
    a.output.write_text(json.dumps(dict(passed=result.wasSuccessful(),test_methods=result.testsRun,cases=len(RECORDS),records=RECORDS,
                                      scope='Complete mapped logical FAT files through ordinary destinations and private contained acquisition workers; no public extraction'),indent=2)+'\n',encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
if __name__=='__main__':main()
