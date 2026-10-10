"""Native ordinary-file report creation plus independent Python byte verification.

API fault seams and owned-process termination are not physical power-loss tests.
"""
import argparse,copy,ctypes,hashlib,itertools,json,os,queue,subprocess,tempfile,threading
from pathlib import Path
from test_case import encode
def digest(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def grant():return dict(definition_digest='$prepared',report_write=True,host_effects=True)
def policy(flags):return dict(zip(('identifiers','raw_values','interpretations','customer_data'),flags))
def main():
    p=argparse.ArgumentParser();p.add_argument('--probe',required=True,type=Path);p.add_argument('--fault',required=True,type=Path);p.add_argument('--root',required=True,type=Path);p.add_argument('--evidence',type=Path);a=p.parse_args()
    profile=json.loads((a.root/'spec/catalog/report-export-prototype.json').read_bytes());assert profile['windows'] and profile['limits']['producer_bytes']==16777216
    probes=[a.probe.resolve(),a.fault.resolve()];env={k:v for k,v in os.environ.items() if not k.startswith('DISKED_REPORT_TEST_')};records=[];process_records=[]
    scratch=a.root.resolve()/'.aide-local';scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='disked-report-',dir=scratch) as tmp:
        owned=Path(tmp).resolve();assert owned.is_relative_to(scratch) and scratch.is_relative_to(a.root.resolve())
        def request(name,**extra):
            folder=owned/name;folder.mkdir();v=dict(mode='execute',destination=str(folder/'support.json'),grant=grant());v.update(extra);return v
        def inspect(v):
            assert v['definition_digest']==digest(encode(v['definition']))
            payload=encode(v['artifact_preview'])+b'\n';d=v['definition'];assert d['artifact']['digest']==digest(payload) and int(d['artifact']['bytes'])==len(payload)
            assert d['resources']['producer']['digest']==digest(Path(d['resources']['producer']['location']).read_bytes())
            assert b'OWNED-SECRET' not in payload and b'534543524554' not in payload;return payload
        def run(name,v,fault=False,injected=None,refusal=None):
            ce=dict(env);ce.update({'DISKED_REPORT_TEST_'+k:str(s) for k,s in (injected or {}).items()});raw=encode(v)
            r=subprocess.run([str(probes[int(fault)])],input=raw,capture_output=True,timeout=25,cwd=a.root,env=ce)
            assert r.returncode==(3 if refusal else 0) and not r.stderr,(name,r.returncode,r.stdout,r.stderr)
            o=json.loads(r.stdout.splitlines()[-1]);path=Path(v['destination']);existing=path.read_bytes() if path.is_file() else None
            if refusal:assert o['refusal']==refusal,(name,o)
            else:
                payload=inspect(o)
                if 'outcome' in o:
                    assert not o['outcome']['physical_backing_qualified'] and o['outcome']['worker_exit']=='unobserved'
                    assert not o['receipt']['routing_metadata_is_support_export']
                    if o['outcome']['status']=='completed':
                        assert existing==payload and digest(existing)==o['receipt']['artifact_digest'] and o['outcome']['flush']=='api_confirmed'
                        assert all(int(o['outcome'][k])==len(payload) for k in ('submitted_bytes','written_bytes','read_bytes','verified_bytes'))
                else:assert existing is None
            records.append(dict(name=name,input_sha256=digest(raw),output_sha256=digest(r.stdout),returncode=r.returncode,status=o.get('outcome',{}).get('status'),diagnostic=o.get('refusal') or o.get('outcome',{}).get('diagnostic'),file_bytes=None if existing is None else len(existing),file_sha256=None if existing is None else digest(existing)))
            return o,existing
        v=request('prepare',mode='prepare');prepared,_=run('prepare-no-output',v);assert not Path(v['destination']).exists()
        v['mode']='execute';v['reviewed_definition']=prepared['definition'];v['grant']['definition_digest']=prepared['definition_digest'];o,data=run('exact-review-execute',v);assert o['outcome']['status']=='completed'
        run('existing-no-clobber',v,refusal='export_output_exists');assert Path(v['destination']).read_bytes()==data
        for flags in itertools.product((False,True),repeat=4):
            name='policy-'+''.join(str(int(f)) for f in flags);v=request(name,policy=policy(flags));o,data=run(name,v);assert o['outcome']['status']=='completed'
            ids,raw,interpret,customer=flags;assert (b'OWNED-SERIAL' in data)==(ids and interpret) and (b'OWNED-CUSTOMER' in data)==(customer and interpret)
            assert (b'"hex":"23"' in data)==raw
        for variant in ('large','controls'):
            o,data=run(variant,request(variant,**{variant:True},policy=policy((True,True,True,True))));assert o['outcome']['status']=='completed'
            if variant=='large':assert len(data)>65536
            else:assert b'\\u001b[31m' in data and b'\\u000a' in data
        for key in ('definition_digest','report_write','host_effects'):
            v=request('grant-'+key);v['grant'][key]='sha256:'+'0'*64 if key=='definition_digest' else False
            o,data=run('grant-'+key,v);assert o['outcome']['diagnostic']=='export_grant' and o['outcome']['output_state']=='not_created' and data is None
        v=request('repeat',repeat=True);o,_=run('single-use-session',v);assert o['repeat']=='export_session_used'
        o,data=run('ordinary-port-cancel-before-create',request('ordinary-cancel',cancel=True));assert o['outcome']['status']=='cancelled' and data is None
        for changed in ('policy','definition','destination'):
            v=request('review-'+changed,mode='prepare');o,_=run('review-prepare-'+changed,v);v['mode']='execute';v['reviewed_definition']=o['definition']
            if changed=='policy':v['policy']=policy((True,False,False,False))
            elif changed=='definition':v['reviewed_definition']['artifact']['digest']='sha256:'+'0'*64
            else:v['destination']=str(Path(v['destination']).with_name('other.json'))
            run('review-change-'+changed,v,refusal='export_reviewed_definition_changed');assert not Path(v['destination']).exists()
        faults={
            'NO_CAPACITY':('refused','export_capacity',None),
            'WRITE_ERROR':('failed','export_file_write',0),
            'SHORT_WRITE':('failed','export_short_write','partial'),
            'LOST_WRITE_ACK':('failed','export_write_ack_lost','full'),
            'FLUSH_ERROR':('failed','export_file_flush','full'),
            'SHORT_READ':('failed','export_short_read','full'),
            'CORRUPT_READ':('failed','export_readback_mismatch','full')}
        for fault,(status,error,length) in faults.items():
            o,data=run(fault,request(fault),fault=True,injected={fault:1});assert (o['outcome']['status'],o['outcome']['diagnostic'])==(status,error),(fault,o)
            n=int(o['definition']['artifact']['bytes']);assert data is None if length is None else len(data)==(0 if length==0 else n//2 if length=='partial' else n)
            if fault in ('WRITE_ERROR','LOST_WRITE_ACK'):assert o['outcome']['written_bytes'] is None
            if fault=='FLUSH_ERROR':assert o['outcome']['flush']=='uncertain'
            if length is not None:assert o['outcome']['uncertain_effect'] and o['receipt']['output_created_observed']
        for phase,length in [('cancel-before-create',None),('cancel-after-create',0),('cancel-after-write','full'),('cancel-after-flush','full')]:
            o,data=run(phase,request(phase),fault=True,injected={'EVENT':phase});assert o['outcome']['status']=='cancelled' and o['outcome']['verified_bytes']=='0'
            assert data is None if length is None else len(data)==(0 if length==0 else int(o['definition']['artifact']['bytes']))
        for path in ('NUL','CON','COM1.txt','\\\\.\\PhysicalDrive0','\\\\server\\share\\report.json',str(owned/'file.json:stream'),str(owned/'trailing.')):
            v=request('badpath-'+str(len(records)));v['destination']=path;run('denied-path-'+str(len(records)),v,refusal='image_path_profile')
        v=request('directory');Path(v['destination']).mkdir();run('directory-is-not-output',v,refusal='export_output_exists')
        v=request('hardlink');original=Path(v['destination']).with_name('owned-original.json');original.write_bytes(b'keep');os.link(original,v['destination']);run('hardlink-no-clobber',v,refusal='export_output_exists');assert original.read_bytes()==b'keep'
        # Coordinate a real CREATE_NEW race and owned-child cut; the same paused
        # process continues when a release file arrives. Never restart on timeout.
        def paused(name,phase,action,kill=False):
            v=request(name);release=Path(v['destination']).with_name('release');ce=dict(env)
            ce.update({'DISKED_REPORT_TEST_EVENT':phase,'DISKED_REPORT_TEST_PAUSE':'1','DISKED_REPORT_TEST_RELEASE_FILE':str(release)})
            proc=subprocess.Popen([str(probes[1])],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=a.root,env=ce);proc.stdin.write(encode(v));proc.stdin.close();q=queue.Queue()
            threading.Thread(target=lambda:q.put(proc.stdout.readline()),daemon=True).start();line=q.get(timeout=10);assert json.loads(line)['event']==phase
            action(v)
            if kill:proc.kill()
            else:release.write_bytes(b'release')
            # Drain while waiting: the result can exceed a Windows pipe buffer.
            # stdin has already been closed after the exact fixture bytes.
            proc.stdin=None;out,err=proc.communicate(timeout=20);assert not err
            path=Path(v['destination']);data=path.read_bytes() if path.is_file() else None
            process_records.append(dict(name=name,pid=proc.pid,event=phase,exit_code=proc.returncode,owned_child_terminated=kill,file_bytes=None if data is None else len(data),file_sha256=None if data is None else digest(data),output_sha256=digest(line+out)))
            if not kill:return json.loads(out.splitlines()[-1]),data
            assert data is not None
        o,data=paused('creation-race','before-create',lambda v:Path(v['destination']).write_bytes(b'concurrent-owned'))
        assert o['outcome']['status']=='refused' and o['outcome']['output_state']=='not_created' and data==b'concurrent-owned'
        paused('owned-child-after-write','written',lambda v:None,kill=True)
        # The paused native session owns ancestor and producer handles. Ordinary
        # rename/write attempts must fail while those bindings are held.
        def try_rename(v):
            parent=Path(v['destination']).parent;renamed=parent.with_name(parent.name+'-moved')
            assert parent.resolve().is_relative_to(owned) and renamed.resolve().is_relative_to(owned)
            try:parent.rename(renamed)
            except PermissionError:return
            renamed.rename(parent)
            raise AssertionError('Pinned output ancestor was renamed')
        o,data=paused('ancestor-held','before-create',try_rename);assert o['outcome']['status']=='completed' and data is not None
        def try_write_producer(v):
            kernel=ctypes.WinDLL('kernel32',use_last_error=True);create=kernel.CreateFileW;create.argtypes=[ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p];create.restype=ctypes.c_void_p
            handle=create(str(probes[1]),0x40000000,7,None,3,0,None)
            assert handle==ctypes.c_void_p(-1).value and ctypes.get_last_error()==32,'Producer write access was not rejected by sharing'
        o,data=paused('producer-held','before-create',try_write_producer);assert o['outcome']['status']=='completed' and data is not None
        # A junction points only at another owned directory. No symlink privilege.
        target=owned/'junction-target';target.mkdir();link=owned/'junction';r=subprocess.run(['cmd','/c','mklink','/J',str(link),str(target)],capture_output=True);assert r.returncode==0
        try:
            v=request('junction-test');v['destination']=str(link/'report.json');run('reparse-parent-denied',v,refusal='image_reparse_source');assert not (target/'report.json').exists()
        finally:os.rmdir(link)
    evidence=dict(passed=True,cases=len(records),observations=records,process_observations=process_records,ordinary_file_io=True,physical_io=False,public_command=False,worker_containment_qualified=False,power_loss_tested=False)
    if a.evidence:a.evidence.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(str(len(records))+' native file-export cases and '+str(len(process_records))+' owned-process/race observations passed; no physical qualification')
if __name__=='__main__':main()
