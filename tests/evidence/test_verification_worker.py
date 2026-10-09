"""Actual contained ordinary-file readers; private contract, no device access.

Expected behaviours are fixed in verification-worker-prototype.json before
evaluation. Fault hooks exist only in the separately compiled test executable.
"""
import argparse,copy,ctypes as C,hashlib,itertools,json,os,subprocess,sys,time
from ctypes import wintypes as W
from pathlib import Path
from test_report_worker import report_process
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
from test_acquisition_worker import canonical,digest,source_bytes,fixture_directory,owned_process,JobLimits,K

def main():
    p=argparse.ArgumentParser()
    for n in ('probe','fault','product','collection'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--evidence',type=Path);a=p.parse_args()
    root=a.root.resolve();probe=a.probe.resolve();fault=a.fault.resolve();product=a.product.resolve();collection=a.collection.resolve()
    env={k:v for k,v in os.environ.items() if not k.startswith(('DISKED_REPORT_','DISKED_ACQ_','DISKED_TEST_','DISKED_VERIFICATION_'))}
    checks=[];samples=[]
    def check(name,value,**extra):assert value,(name,extra);checks.append(dict(name=name,passed=True,**extra))
    def call(value,exe=probe,extra=None,refusal=None):
        result=subprocess.run([str(exe)],input=canonical(value),capture_output=True,cwd=root,env=dict(env,**(extra or {})),timeout=12)
        assert result.returncode==(3 if refusal else 0) and not result.stderr,(result.returncode,result.stdout,result.stderr)
        out=json.loads(result.stdout)
        if refusal:check('typed-refusal',refusal in out['refusal'],expected=refusal)
        return out
    def cli(args):
        r=subprocess.run([str(product),'--json',*args],capture_output=True,cwd=root,env=env,timeout=15)
        assert r.returncode in (0,5) and not r.stderr,(r.returncode,r.stdout,r.stderr);return json.loads(r.stdout)
    def grant(d,**changes):
        g=dict(definition_digest=d['definition_digest'],case_read=True,image_read=True,map_read=True,store_write=True,host_effects=True,private_metadata=True);g.update(changes);return g
    def start(d,exe=probe,extra=None,g=None):return call(dict(mode='start',definition=d['definition'],grant=g or grant(d)),exe,extra)
    def observe(id,store,exe=probe,mode='inspect'):return call(dict(mode=mode,operation_id=id,state_directory=str(store)),exe)
    def wait(id,store,exe=probe,terminal=True):
        end=time.monotonic()+18;last=None
        while time.monotonic()<end:
            last=observe(id,store,exe);s=last.get('value',{}).get('state')
            if s and ((terminal and s['phase']=='finished') or (not terminal and last['value']['worker_observation']!='running')):
                h=report_process(s,exe)
                if h:
                    try:assert K.WaitForSingleObject(h,3000)==0,('retain live verification dependencies',last)
                    finally:K.CloseHandle(h)
                return last
            time.sleep(.025)
        raise AssertionError(('retain unresolved verification operation',last))
    def independent(store):
        h=json.loads((store/'verification.request').read_bytes());raw=(store/'verification.records').read_bytes();rows=[];previous='0'*64
        for ordinal,line in enumerate(raw.splitlines(),1):
            row=json.loads(line);assert canonical(row)==line and len(line)<=65536 and ordinal<=32
            assert row['schema']=='org.disked.verification-worker-record-prototype/1' and row['previous']==previous
            unsigned=copy.deepcopy(row);previous=unsigned.pop('digest');assert hashlib.sha256(canonical(unsigned)).hexdigest()==previous
            s=row['state'];b=s['binding'];assert s['sequence']==str(ordinal) and int(s['observed_filetime'])>0
            for n in ('operation_id','attempt_id','worker_epoch','capture_epoch','definition_digest'):assert b[n]==h[n]
            assert b['host_id']==h['definition']['host_id'] and b['verifier']==h['definition']['verifier']
            assert 0<int(b['process_id'])<2**32 and 0<int(b['process_created'])<2**64
            if rows:
                assert b==rows[-1]['state']['binding'] and rows[-1]['state']['phase']!='finished'
                for n,v in s['progress'].items():assert int(v)>=int(rows[-1]['state']['progress'][n])
            rows.append(row)
        check('independent-progress-chain',rows and rows[0]['state']['phase']=='prepared' and raw.endswith(b'\n'))
        return h,raw,rows
    scratch=root/'.aide-local';scratch.mkdir(exist_ok=True)
    with fixture_directory(scratch) as owned:
        original_dir=owned/'original';original_dir.mkdir();case_store=original_dir/'state';case_store.mkdir()
        source=original_dir/'source.img';image=original_dir/'copy.img';mapping=original_dir/'copy.map';expected=source_bytes(262145);source.write_bytes(expected)
        d=cli(['image','acquire','prepare',str(source),str(image),'--map',str(mapping),'--state-dir',str(case_store)])['result']
        result=cli(['image','acquire','execute','--definition-json',canonical(d['definition']).decode(),'--definition-digest',d['definition_digest'],
            '--allow-source-read','--allow-destination-write','--allow-map-write','--allow-host-effects']);case_id=result['operation_id'];end=time.monotonic()+20
        while True:
            state=cli(['operation','inspect',case_id,'--state-dir',str(case_store)])['result']['state']
            if state['phase']=='finished':break
            assert time.monotonic()<end,('retain acquisition',state);time.sleep(.025)
        handle=owned_process(state,str(product))
        if handle:
            try:assert K.WaitForSingleObject(handle,3000)==0
            finally:K.CloseHandle(handle)
        original={f.name:f.read_bytes() for f in case_store.iterdir() if f.is_file()}
        def prepare(name,exe=probe,selected=image,map_path=mapping):
            store=owned/name;store.mkdir()
            d=call(dict(mode='prepare',operation_id=case_id,case_directory=str(case_store),image=str(selected),map=str(map_path),state_directory=str(store)),exe)
            check('preparation-no-output',not list(store.iterdir()) and original=={f.name:f.read_bytes() for f in case_store.iterdir() if f.is_file()})
            check('exact-code-and-wrapper',d['definition_digest']==digest(canonical(d['definition'])) and d['definition']['verifier']['image_digest']==digest(exe.read_bytes()))
            return d,store
        def finish(d,store,result,exe=probe,expected_status='matched'):
            check('operation-identity-always-retained',result['operation_id'] and result['status'] in ('accepted_running','completed','unknown'))
            end=wait(result['operation_id'],store,exe);h,raw,rows=independent(store);s=rows[-1]['state']
            check('typed-history-agrees',call(dict(mode='history',records=raw.decode(),header=h),exe)['state']==s==end['value']['state'])
            check('actual-verdict-preserved',s['phase']=='finished' and s['quiescent'] and s['outcome']['status']==expected_status)
            check('collection-fully-validated',s['retention']['state']=='verified' and end['value']['collection_validation']=='passed')
            saved=(store/'verification.collection').read_bytes();c=json.loads(saved);check('actual-retention-digest',digest(saved)==s['retention']['digest'] and len(saved)==int(s['retention']['bytes']))
            assert len(c['records'])==1;row=c['records'][0];observation=row['observation']
            check('actual-observer-binding',row['observer']=={n:s['binding'][n] for n in ('attempt_id','worker_epoch','capture_epoch','process_id','process_created')})
            check('case-keeps-original-claims',c['original_case']['claims']['current_image_verification']=='not_performed')
            check('separate-verdict-and-code',observation['outcome']==s['outcome'] and observation['verifier']==d['definition']['verifier'])
            check('independent-collection-hash',digest(canonical(c))==s['retention']['collection_revision'] and digest(canonical(observation))==s['retention']['observation_revision'])
            restored=call(dict(mode='restore',retention_bytes=saved.decode()),collection)
            check('independent-typed-collection-restore',restored['collection']==c)
            samples.append(dict(header=h,state=s,history_sha256=digest(raw),collection_sha256=digest(saved)))
            return end,h,raw,rows
        d,store=prepare('normal')
        for flags in itertools.product((False,True),repeat=6):
            if all(flags):continue
            g=grant(d,**dict(zip(('case_read','image_read','map_read','store_write','host_effects','private_metadata'),flags)))
            out=start(d,g=g);check('missing-authority-before-effects',out['status']=='refused' and out['operation_id'] is None and not list(store.iterdir()))
        for bad in ('sha256:'+'f'*64,d['definition']['verification_digest']):
            out=start(d,g=grant(d,definition_digest=bad));check('wrong-or-inner-grant-refused',out['status']=='refused' and not list(store.iterdir()))
        for mutate in (
            lambda x:x.update(unexpected=True),lambda x:x['verifier'].update(image_digest='sha256:'+'f'*64),
            lambda x:x['case_source'].update(case_revision='sha256:'+'f'*64),lambda x:x['store'].update(failure_domain='unbound'),
            lambda x:x['image_binding']['image']['metadata'].update(bytes='18446744073709551616')):
            changed=copy.deepcopy(d);mutate(changed['definition']);changed['definition_digest']=digest(canonical(changed['definition']))
            out=start(changed);check('changed-contract-before-effects',out['status']=='refused' and not list(store.iterdir()))
        aliased=copy.deepcopy(d);aliased['definition']['store']['generation']=copy.deepcopy(aliased['definition']['case_source']['store']['generation'])
        aliased['definition']['store']['ancestors']=copy.deepcopy(aliased['definition']['case_source']['ancestors'])
        aliased['definition']['store']['failure_domain']=aliased['definition']['case_source']['store']['failure_domain'];aliased['definition_digest']=digest(canonical(aliased['definition']))
        rejected=start(aliased);check('case-store-alias-refused',rejected['status']=='refused' and not list(store.iterdir()))
        reserved=copy.deepcopy(d);reserved['definition']['store']['children'][-1]='other-output'
        reserved['definition_digest']=digest(canonical(reserved['definition']));check('fixed-store-names-enforced',start(reserved)['status']=='refused' and not list(store.iterdir()))
        out=start(d);normal,h,raw,rows=finish(d,store,out)
        check('checkpoint-progress-sampled',1<=sum(r['state']['phase']=='verifying' and int(r['state']['progress']['covered_bytes'])>0 for r in rows)<=12)
        check('exact-byte-counters',normal['value']['state']['outcome']['matched_bytes']==str(len(expected)))
        again=start(d);check('repeat-start-is-observation',again['operation_id']==out['operation_id'] and (store/'verification.records').read_bytes()==raw)
        cancelled=observe(out['operation_id'],store,mode='cancel');check('finished-cancellation-too-late',cancelled['value']['cancellation_request']=='too_late' and (store/'verification.cancel').read_bytes()==b'0')
        watch=dict(mode='watch',operation_id=out['operation_id'],state_directory=str(store),after_sequence='0',after_digest='0'*64,worker_epoch='')
        seen=call(watch)['value'];check('private-watch-full-history',seen['records']==rows and seen['last_sequence']==str(len(rows)))
        watch.update(after_sequence=seen['last_sequence'],after_digest=seen['last_digest'],worker_epoch=seen['worker_epoch'])
        check('private-watch-resume-no-duplicates',call(watch)['value']['records']==[])
        for n,v in (('after_digest','f'*64),('worker_epoch','worker:'+'f'*32),('after_sequence','18446744073709551616')):
            bad=dict(watch,**{n:v});call(bad,refusal='verification_watch_cursor')
        check('watch-has-no-effects',(store/'verification.records').read_bytes()==raw)
        torn=call(dict(mode='history',header=h,records=raw.decode()+'torn'))
        check('torn-tail-retains-last-state',not torn['complete'] and torn['state']==rows[-1]['state'])
        for mutate,reason in (
            (lambda x:x[-1]['state']['outcome'].update(matched_bytes='1'),'image_observation_counters'),
            (lambda x:x[-1]['state']['retention'].update(bytes='0'),'verification_worker_retention'),
            (lambda x:x[-1]['state']['binding'].update(capture_epoch='capture:'+'f'*32),'verification_worker_binding'),
            (lambda x:x[1]['state'].update(quiescent=True),'verification_worker_quiescence'),
            (lambda x:x[-1]['state'].update(phase='verifying'),'verification_worker_quiescence'),
            (lambda x:x[-1]['state']['progress'].update(covered_bytes='0'),'verification_worker_counters')):
            changed=copy.deepcopy(rows);mutate(changed);previous='0'*64
            for row in changed:
                row['previous']=previous;row.pop('digest');previous=hashlib.sha256(canonical(row)).hexdigest();row['digest']=previous
            call(dict(mode='history',header=h,records=b''.join(canonical(r)+b'\n' for r in changed).decode()),refusal=reason)
        for name,value,reason in (('sequence','18446744073709551616','verification_worker_integer'),('observed_filetime','0','verification_worker_sequence')):
            row=copy.deepcopy(rows[0]);row['state'][name]=value;row.pop('digest');row['digest']=hashlib.sha256(canonical(row)).hexdigest()
            call(dict(mode='history',header=h,records=(canonical(row)+b'\n').decode()),refusal=reason)
        call(dict(mode='history',header=h,records=raw.decode()+'x'*65537),refusal='verification_worker_history_limit')
        call(dict(mode='history',header=h,records=raw.decode()+'x'*2097153),refusal='verification_worker_history_limit')
        synthetic=[];previous='0'*64
        for n in range(1,34):
            row=copy.deepcopy(rows[0]);row['state']['sequence']=str(n);row['previous']=previous;row.pop('digest');previous=hashlib.sha256(canonical(row)).hexdigest();row['digest']=previous;synthetic.append(row)
        call(dict(mode='history',header=h,records=b''.join(canonical(r)+b'\n' for r in synthetic).decode()),refusal='verification_worker_history_limit')
        # A byte mismatch retains the recorded ordinary-file creation identity.
        with image.open('r+b') as f:f.seek(65536);f.write(bytes([expected[65536]^1]))
        md,ms=prepare('mismatch');end,_,_,_=finish(md,ms,start(md),expected_status='mismatch')
        check('mismatch-stops-at-confirmed-prefix',end['value']['state']['outcome']['covered_bytes']=='65536')
        image.write_bytes(expected)
        replacement=owned/'replacement.img';replacement.write_bytes(expected)
        rd,rs=prepare('replacement',selected=replacement);end,_,_,_=finish(rd,rs,start(rd),expected_status='refused')
        check('replacement-never-borrows-recorded-identity',end['value']['state']['outcome']['diagnostic']=='verification_recorded_identity' and end['value']['state']['outcome']['read_bytes']=='0')
        map_bytes=mapping.read_bytes();mapping.write_bytes(b''.join(map_bytes.splitlines(keepends=True)[:-1]))
        td,ts=prepare('unsealed-map');end,_,_,_=finish(td,ts,start(td),expected_status='incomplete')
        check('unsealed-map-not-success',not end['value']['state']['outcome']['sealed'] and end['value']['state']['outcome']['covered_bytes']==str(len(expected)))
        mapping.write_bytes(map_bytes)
        stale=owned/'stale.img';stale.write_bytes(expected);sd,ss=prepare('stale',selected=stale);stale.write_bytes(b'x'+expected[1:])
        refused=start(sd);check('fresh-image-binding-required',refused['status']=='refused' and not list(ss.iterdir()))
        for name,key,status in (
            ('cancel-before','DISKED_VERIFICATION_WORKER_TEST_EFFECT_DELAY','cancelled'),
            ('cancel-during','DISKED_VERIFICATION_WORKER_TEST_PROGRESS_DELAY','cancelled'),
            ('cancel-late','DISKED_VERIFICATION_WORKER_TEST_RETENTION_DELAY','matched')):
            cd,cs=prepare(name,fault);started=start(cd,fault,{key:'1'});id=started['operation_id'];endtime=time.monotonic()+10
            while True:
                observed=observe(id,cs,fault);s=observed['value'].get('state')
                if s and ((name=='cancel-before' and s['phase']=='prepared') or (name=='cancel-during' and int(s['progress']['covered_bytes'])>0) or (name=='cancel-late' and s['phase']=='persisting')):break
                assert time.monotonic()<endtime,(name,observed);time.sleep(.025)
            handle=report_process(s,fault)
            assert handle
            job=K.OpenJobObjectW(4,False,'Local\\DiskEd.Fake.Workers.v1.'+cd['definition']['host_id']);assert job
            try:
                member=W.BOOL();limits=JobLimits();assert K.IsProcessInJob(handle,job,C.byref(member)) and member.value
                assert K.QueryInformationJobObject(job,9,C.byref(limits),C.sizeof(limits),None)
                check('native-aggregate-budget',limits.basic.flags==0x308 and limits.basic.process_limit==4 and limits.process_memory==128*1024*1024 and limits.job_memory==512*1024*1024)
            finally:K.CloseHandle(job);K.CloseHandle(handle)
            requested=observe(id,cs,fault,'cancel');check('cancel-request-separate',requested['value']['cancellation_request']=='requested')
            end,_,_,_=finish(cd,cs,started,fault,status);s=end['value']['state']
            check('cancellation-observation-truth',s['cancellation_observation']==('not_observed' if name=='cancel-late' else 'observed'))
            if name=='cancel-during':check('partial-prefix-retained',0<int(s['outcome']['covered_bytes'])<len(expected))
        ad,ast=prepare('admission-timeout',fault);t=time.monotonic();started=start(ad,fault,{'DISKED_VERIFICATION_WORKER_TEST_ADMISSION_DELAY':'1'})
        check('admission-wait-bounded',3<=time.monotonic()-t<4.5 and started['status']=='unknown' and started['operation_id'])
        repeated=start(ad,fault);check('timeout-no-replacement',repeated['operation_id']==started['operation_id'])
        cancelled=observe(started['operation_id'],ast,fault,'cancel');check('timeout-cancel-request-persists',cancelled['value']['cancellation_request']=='requested')
        ended=wait(started['operation_id'],ast,fault);s=ended['value']['state'];check('pre-provider-cancel-no-fabricated-outcome',s['disposition']=='cancelled' and s['outcome'] is None and s['retention']['state']=='empty')
        for mode in ('full','short','flush'):
            fd,fs=prepare('collection-'+mode,fault);started=start(fd,fault,{'DISKED_TEST_STORE_FAULT':'verification_collection.'+mode});end=wait(started['operation_id'],fs,fault)
            s=end['value']['state'];check('retention-failure-keeps-verdict',s['outcome']['status']=='matched' and s['disposition']=='unknown' and s['retention']['state']=='uncertain' and s['quiescent'])
            check('retention-failure-no-auto-retry',start(fd,fault)['operation_id']==started['operation_id'])
        for mode in ('full','short','flush'):
            fd,fs=prepare('terminal-'+mode,fault);started=start(fd,fault,{'DISKED_TEST_STORE_FAULT':'verification_finished.'+mode});end=wait(started['operation_id'],fs,fault,terminal=False)
            s=end['value']['state'];check('terminal-fault-retains-actual-verdict',s['outcome']['status']=='matched' and (fs/'verification.collection').stat().st_size>0)
            if mode!='flush':check('missing-terminal-is-unresolved',end['status']=='unknown' and s['phase']=='persisting' and not s['quiescent'])
            check('terminal-fault-no-replacement',start(fd,fault)['operation_id']==started['operation_id'])
        # Completed private reads follow no retained image/case paths.
        original_dir.rename(owned/'retired-original');again=observe(out['operation_id'],store)
        check('historical-inspection-without-original-resources',again['status']=='completed' and again['value']['state']==normal['value']['state'] and again['value']['collection_validation']=='passed')
        saved=(store/'verification.collection').read_bytes();(store/'verification.collection').write_bytes(saved[:-1])
        changed=observe(out['operation_id'],store);check('changed-retention-not-authoritative',changed['status']=='unknown' and changed['value']['state']['outcome']['status']=='matched')
        registry=cli(['commands'])['result']
        check('product-selects-proposed-verification',any(c['id']=='image.verify' and c['availability']=='available' and c['contract_status']=='planned' for c in registry['commands']) and sum(c['availability']=='available' for c in registry['commands'])==20)
    report=dict(schema='org.disked.verification-worker-validation/1',status='passed',checks=checks,count=len(checks),samples=samples,
        binaries={n:digest(v.read_bytes()) for n,v in [('probe',probe),('fault',fault),('product',product),('collection',collection)]},
        limitations=['private Windows prototype only','public command/frontend and caller latency unqualified','no physical media/elevation/customer data','no authenticated custody or power-loss persistence'])
    if a.evidence:a.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='passed',checks=len(checks),native_samples=len(samples))))

if __name__=='__main__':main()
