"""Independent acquired-image/map checks, actual owned files and read-only guards."""
import argparse,copy,ctypes as C,json,os,queue,subprocess,sys,threading,time
from ctypes import wintypes as W
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
from test_acquisition_worker import canonical,digest,source_bytes,map_check,fixture_directory,owned_process,K

def main():
    p=argparse.ArgumentParser()
    for name in ('probe','product'):p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--evidence',type=Path);a=p.parse_args()
    root=a.root.resolve();probe=a.probe.resolve();product=a.product.resolve();observations=[];samples=[]
    env={k:v for k,v in os.environ.items() if not k.startswith(('DISKED_ACQ_','DISKED_TEST_'))}
    def check(name,value,**extra):assert value,(name,extra);observations.append(dict(name=name,passed=True,**extra))
    def call(value,status=None,refusal=None):
        r=subprocess.run([str(probe)],input=canonical(value),capture_output=True,cwd=root,env=env,timeout=20)
        assert not r.stderr,(r.returncode,r.stderr);out=json.loads(r.stdout)
        if refusal:assert r.returncode==3 and refusal in out['refusal'],out
        else:
            assert r.returncode==0 and out['outcome']['status']==status,(r.returncode,out)
            assert out['definition_digest']==digest(canonical(out['definition'])) or value.get('tamper'),out
            assert out['outcome']['claims']==dict(source_preservation='not_established',authenticity='not_established',point_in_time_acquisition='not_established',worker_exit='not_observed',physical_admission=False,mutation_authority=False)
        return out
    def cli(args):
        r=subprocess.run([str(product),'--json',*args],capture_output=True,cwd=root,env=env,timeout=20)
        assert r.returncode in (0,5) and not r.stderr,(r.returncode,r.stdout,r.stderr);return json.loads(r.stdout)
    def acquire(folder,size):
        folder.mkdir();state_dir=folder/'state';state_dir.mkdir();src=folder/'source.img';dst=folder/'copy.img';mapping=folder/'acquisition.map'
        expected=source_bytes(size);src.write_bytes(expected)
        review=cli(['image','acquire','prepare',str(src),str(dst),'--map',str(mapping),'--state-dir',str(state_dir)])['result']
        first=cli(['image','acquire','execute','--definition-json',canonical(review['definition']).decode(),'--definition-digest',review['definition_digest'],
            '--allow-source-read','--allow-destination-write','--allow-map-write','--allow-host-effects'])
        deadline=time.monotonic()+30
        while True:
            value=cli(['operation','inspect',first['operation_id'],'--state-dir',str(state_dir)]);state=value['result']['state']
            if state['phase']=='finished':break
            assert time.monotonic()<deadline,('retain unresolved dependencies',state);time.sleep(.02)
        handle=owned_process(state,str(product))
        if handle:
            try:assert K.WaitForSingleObject(handle,3000)==0
            finally:K.CloseHandle(handle)
        assert state['outcome']['status']=='completed' and state['quiescent']
        check('actual-generated-source-copy',src.read_bytes()==dst.read_bytes()==expected,bytes=size)
        rows=map_check(mapping,expected);native=dict(operation_id=first['operation_id'],state_directory=str(state_dir),image=str(dst),map=str(mapping))
        return native,expected,rows
    def rechain(rows):
        previous='sha256:'+'0'*64;raw=[]
        for seq,row in enumerate(rows):
            row['sequence']=str(seq);row['previous']=previous
            if row['type']=='header':row['payload']['plan_digest']=digest(canonical(row['payload']['plan']))
            body=canonical(row);previous=digest(body);raw.append(body+b'\n')
        return b''.join(raw).decode()
    scratch=root/'.aide-local';scratch.mkdir(exist_ok=True)
    with fixture_directory(scratch) as owned:
        native,expected,rows=acquire(owned/'normal',262145);dst=Path(native['image']);mapping=Path(native['map']);map_raw=mapping.read_bytes()
        file_set={str(f.relative_to(owned)):digest(f.read_bytes()) for f in owned.rglob('*') if f.is_file()}
        actual=call(native,'matched');out=actual['outcome'];samples.append(actual)
        check('native-full-before-after-current-bytes',out['matched_bytes']==str(len(expected)) and out['covered_bytes']==str(len(expected)) and out['source_bytes']==str(len(expected)) and out['substituted_bytes']=='0' and out['sealed'] and not out['pending'])
        check('native-resources-stable',out['before']==out['after'] and out['resource_revalidation']=='passed' and actual['before_binding']==actual['after_binding'] and actual['case_revalidation']=='passed')
        check('actual-verifier-writes-nothing',file_set=={str(f.relative_to(owned)):digest(f.read_bytes()) for f in owned.rglob('*') if f.is_file()})
        altered=bytearray(expected);altered[65536]^=1;dst.write_bytes(altered)
        damaged=call(native,'mismatch')['outcome'];check('actual-current-byte-mismatch-retains-prefix',damaged['matched_bytes']=='65536' and damaged['read_bytes']=='131072' and damaged['resource_revalidation']=='passed')
        dst.write_bytes(expected);check('actual-restored-image-new-definition',call(native,'matched')['definition_digest']!=actual['definition_digest'])
        mapping.write_bytes(b''.join(canonical(r)+b'\n' for r in rows[:-1]));incomplete=call(native,'incomplete')['outcome']
        check('actual-missing-seal-not-complete',incomplete['matched_bytes']==str(len(expected)) and not incomplete['sealed'])
        mapping.write_bytes(map_raw+b'{');call(native,'refused');check('actual-after-seal-tail-retained',mapping.read_bytes()==map_raw+b'{')
        mapping.write_bytes(map_raw)
        copied=owned/'byte-identical-copy.img';copied.write_bytes(expected)
        refused=call(dict(native,image=str(copied)),'refused');check('actual-copy-does-not-invent-generation',refused['outcome']['diagnostic']=='verification_recorded_identity' and refused['outcome']['read_bytes']=='0')
        call(dict(native,image=str(mapping)),refusal='verification_alias')
        # Native held resources deny byte writes and rename. Creation-time-only
        # modification is tested separately because such metadata access can
        # remain possible despite data sharing restrictions on this host.
        K.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,W.LPVOID,W.DWORD,W.DWORD,W.HANDLE];K.CreateFileW.restype=W.HANDLE
        K.GetFileTime.argtypes=[W.HANDLE,C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME)]
        K.SetFileTime.argtypes=[W.HANDLE,C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME)]
        def held(action,status,case_status='passed'):
            child=subprocess.Popen([str(probe),'--hold'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root,env=env)
            child.stdin.write(canonical(native)+b'\n');child.stdin.flush();q=queue.Queue();threading.Thread(target=lambda:q.put(child.stdout.readline()),daemon=True).start()
            ready=json.loads(q.get(timeout=12));assert ready['event']=='verification-held' and int(ready['pid'])==child.pid and child.poll() is None
            try:action()
            finally:
                child.stdin.write(b'x\n');child.stdin.flush();child.stdin.close();child.stdin=None
                stdout,stderr=child.communicate(timeout=20)
            check('same-owned-reader-terminal',child.returncode==0 and not stderr and json.loads(stdout)['outcome']['status']==status and json.loads(stdout)['case_revalidation']==case_status)
            return json.loads(stdout)
        def sharing():
            for path in (dst,mapping):
                try:path.rename(path.with_name(path.name+'-moved'));raise AssertionError('reader rename succeeded')
                except PermissionError as error:check('actual-held-rename-refused',error.winerror in (5,32),file=path.name)
                h=K.CreateFileW(str(path),0x40000000,7,None,3,0x200000,None);code=C.get_last_error()
                if h and h!=W.HANDLE(-1).value:K.CloseHandle(h);raise AssertionError('reader byte-write handle succeeded')
                check('actual-held-byte-write-refused',code in (5,32),file=path.name,platform_code=code)
        held(sharing,'matched')
        metadata=K.CreateFileW(str(dst),0x100,7,None,3,0x200000,None);assert metadata and metadata!=W.HANDLE(-1).value,C.get_last_error()
        original=W.FILETIME();assert K.GetFileTime(metadata,C.byref(original),None,None)
        changed=(original.dwHighDateTime<<32 | original.dwLowDateTime)+10000000;stamp=W.FILETIME(changed&0xffffffff,changed>>32)
        try:
            stale=held(lambda:check('actual-metadata-change',bool(K.SetFileTime(metadata,C.byref(stamp),None,None))),'unknown')
            check('changed-resource-after-observation-unavailable',stale['outcome']['matched_bytes']=='0' and stale['after_binding_status']=='unavailable')
        finally:assert K.SetFileTime(metadata,C.byref(original),None,None);K.CloseHandle(metadata)
        check('metadata-restored-current-bytes-match',call(native,'matched')['outcome']['matched_bytes']==str(len(expected)))
        # A later case-metadata observation cannot erase the separately observed
        # image result. This receipt becomes inapplicable to the changed case.
        request_file=Path(native['state_directory'])/'acquisition.request'
        metadata=K.CreateFileW(str(request_file),0x100,7,None,3,0x200000,None);assert metadata and metadata!=W.HANDLE(-1).value,C.get_last_error()
        original=W.FILETIME();assert K.GetFileTime(metadata,C.byref(original),None,None)
        changed=(original.dwHighDateTime<<32 | original.dwLowDateTime)+10000000;stamp=W.FILETIME(changed&0xffffffff,changed>>32)
        try:
            stale=held(lambda:check('actual-case-metadata-change',bool(K.SetFileTime(metadata,C.byref(stamp),None,None))),'matched','unavailable')
            check('image-facts-retained-case-applicability-separate',stale['outcome']['matched_bytes']==str(len(expected)) and stale['case_binding_after'] is None and stale['case_binding_before'])
        finally:assert K.SetFileTime(metadata,C.byref(original),None,None);K.CloseHandle(metadata)
        empty,_,_=acquire(owned/'empty',0);check('actual-empty-image-seal',call(empty,'matched')['outcome']['matched_bytes']=='0')

        base=dict(plan=copy.deepcopy(rows[0]['payload']['plan']),resources=copy.deepcopy(actual['definition']['resources']),records=map_raw.decode(),image_hex=expected.hex())
        def model(name,value,status,diagnostic=None):
            value=copy.deepcopy(value);value['resources']['map']['bytes']=str(len(value['records'].encode()))
            result=call(value,status);check(name,diagnostic is None or result['outcome']['diagnostic']==diagnostic);return result
        normal=model('independent-model-full-match',base,'matched');definition=normal['definition_digest']
        for flag in ('image_read','map_read'):
            value=copy.deepcopy(base);value['grant']=dict(definition_digest=definition,image_read=True,map_read=True);value['grant'][flag]=False
            result=model('false-read-grant-'+flag,value,'refused','verification_grant');check('false-grant-zero-ports',all(v=='0' for v in result['calls'].values()))
        value=copy.deepcopy(base);value['grant']=dict(definition_digest='sha256:'+'0'*64,image_read=True,map_read=True)
        result=model('wrong-digest-grant',value,'refused','verification_grant');check('wrong-grant-zero-ports',all(v=='0' for v in result['calls'].values()))
        value=copy.deepcopy(base);value['tamper']=True
        result=model('tampered-definition',value,'refused','verification_grant');check('tampered-definition-zero-ports',all(v=='0' for v in result['calls'].values()))
        for fault,status in [('short','unknown'),('error','unknown'),('throw','unknown'),('overread','unknown'),('changed','unknown'),('changed_once','unknown'),('cancel','cancelled'),('cancel_after_read','cancelled')]:
            value=copy.deepcopy(base);value['fault']=fault;result=model('scoped-port-fault-'+fault,value,status)
            if fault=='changed_once':check('transient-resource-change-never-forgotten',result['outcome']['resource_revalidation']=='changed')
            if fault=='overread':check('oversized-read-return-count-retained',result['outcome']['read_bytes']=='65537' and result['outcome']['matched_bytes']=='0')
        mutations=[('wrong-sequence',lambda r:r[1].update(sequence='9'),'verification_map_chain'),
            ('bad-predecessor',lambda r:r[1].update(previous='sha256:'+'f'*64),'verification_map_chain')]
        for name,mutate,code in mutations:
            changed_rows=copy.deepcopy(rows);mutate(changed_rows);value=copy.deepcopy(base);value['records']=''.join(canonical(r).decode()+'\n' for r in changed_rows);model(name,value,'refused',code)
        def altered_rows(name,mutate,code):
            r=copy.deepcopy(rows);mutate(r);value=copy.deepcopy(base);value['records']=rechain(r);return model(name,value,'refused',code)
        altered_rows('rebound-geometry',lambda r:r[1]['payload'].update(length='1'),'verification_chunk_geometry')
        altered_rows('checkpoint-without-pending',lambda r:r.pop(1),'verification_checkpoint')
        altered_rows('contradictory-checkpoint',lambda r:r[2]['payload'].update(read_bytes='1'),'verification_checkpoint')
        altered_rows('bad-seal-totals',lambda r:r[-1]['payload'].update(source_bytes='0'),'verification_seal')
        altered_rows('record-after-seal',lambda r:r.append(copy.deepcopy(r[1])),'verification_after_seal')
        altered_rows('wrong-original-generation',lambda r:r[0]['payload']['resources']['destination'].update(epoch='other'),'verification_recorded_identity')
        failure=dict(schema=rows[1]['schema'],type='read_failure',sequence='0',previous='',payload=dict(offset='0',length='65536',read_bytes='0',retries='0',read_error='fixture_read_error'))
        value=copy.deepcopy(base);r=copy.deepcopy(rows);r.insert(1,failure);value['records']=rechain(r)
        model('recorded-read-failure-before-later-checkpoint',value,'matched')
        r=copy.deepcopy(rows);r.insert(2,copy.deepcopy(failure));value['records']=rechain(r)
        model('read-failure-with-pending-refuses',value,'refused','verification_read_failure')
        substituted=copy.deepcopy(base);substituted['plan']['substitution']='zero-fill';r=copy.deepcopy(rows);r[0]['payload']['plan']=copy.deepcopy(substituted['plan'])
        zeros=bytes(65536)
        for i in (1,2):r[i]['payload'].update(state='substituted',read_bytes='0',read_error='fixture_read_error',sha256=digest(zeros))
        r[-1]['payload'].update(source_bytes=str(len(expected)-65536),substituted_bytes='65536')
        substituted['records']=rechain(r);substituted['image_hex']=(zeros+expected[65536:]).hex()
        result=model('substituted-bytes-match-without-source-claim',substituted,'matched')
        check('substitution-counts-separate',result['outcome']['substituted_bytes']=='65536' and result['outcome']['source_bytes']==str(len(expected)-65536))
        r[1]['payload']['sha256']=digest(expected[:65536]);substituted['records']=rechain(r)
        model('substitution-requires-zero-digest',substituted,'refused','verification_substitution_digest')
        value=copy.deepcopy(base);value['records']=''.join(canonical(r).decode()+'\n' for r in rows[:-1]);model('no-seal',value,'incomplete')
        value=copy.deepcopy(base);value['records']=canonical(rows[0]).decode()+'\n'+canonical(rows[1]).decode()+'\n';result=model('pending-not-replayed',value,'incomplete');check('pending-no-image-read',result['calls']['reads']=='0' and result['outcome']['pending'])
        value=copy.deepcopy(base);value['records']=canonical(rows[0]).decode()+'\n{';model('torn-tail-not-repaired',value,'incomplete','verification_torn_map')
        value=copy.deepcopy(base);value['records']=' '+value['records'];model('alternate-record-whitespace-refused',value,'refused','verification_map_encoding')
        value=copy.deepcopy(base);value['records']='{broken}\n';model('malformed-record-is-not-verification',value,'refused','verification_map_json')
        value=copy.deepcopy(base);value['records']='x'*16385+'\n';model('oversized-record-refuses',value,'refused','verification_map_limit')
        value=copy.deepcopy(base);value['records']=value['records'].replace('\n','\r\n');model('alternate-crlf-records-refused',value,'refused','verification_map_encoding')
        value=copy.deepcopy(base);value['image_hex']=expected[:-1].hex();model('short-current-image',value,'unknown','verification_image_read')
        value=copy.deepcopy(base);value['resources']['image']['bytes']=str(len(expected)+1);model('extra-current-image-tail',value,'mismatch','verification_image_size')
        for field,new in [('bytes',str(2**64)),('bytes','01'),('access','write')]:
            value=copy.deepcopy(base);value['resources']['image'][field]=new;call(value,refusal='verification_');check('invalid-resource-'+field+new,True)
        value=copy.deepcopy(base);value['resources']['map']['bytes']=str(1048576*16385+1);call(value,refusal='verification_size');check('map-budget-refuses-before-ports',True)
        check('final-original-source-copy-map-unchanged',Path(native['state_directory']).is_dir() and dst.read_bytes()==expected and mapping.read_bytes()==map_raw)
    result=dict(passed=True,checks=len(observations),observations=observations,samples=samples,
        source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        source_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=root)),
        probe_sha256=digest(probe.read_bytes()),product_sha256=digest(product.read_bytes()),
        scope='Private independent map/image verifier, two actual generated acquisitions, real current-byte/metadata/holding checks and separately scoped synthetic records/ports; no source-preservation/authenticated custody/physical/worker containment qualification')
    if a.evidence:a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('observations','samples')}))
if __name__=='__main__':main()
