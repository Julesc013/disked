"""Actual private joined-report child qualification on an owned native fixture.

Invoked by test_verification_case after acquisition, verification and retention.
Original image paths have been moved; only explicitly selected metadata is read.
Fault controls exist only in the separate fault executable. Never kill/restart
an uncertain worker or remove its dependencies before observing actual exit.
"""
import copy,ctypes as C,hashlib,itertools,json,subprocess,sys,time
from ctypes import wintypes as W
from test_acquisition_worker import canonical,digest,JobLimits,K
from test_report_worker import report_process,history_check
from test_image_observation import POLICIES

def exercise(root,owned,probe,fault,product,env,operation,case,collection,collection_bytes,acq,coll,check,samples,exports):
    from test_verification_case import combined_support
    sys.path.insert(0,str(root/'spec/tools'))
    from specctl import Bundle,SpecError
    bundle=Bundle(root/'spec');prefix=owned/'joined-workers';prefix.mkdir()
    original={p.name:p.read_bytes() for p in case.iterdir() if p.is_file()}
    def call(v,exe=probe,extra=None,refusal=None):
        r=subprocess.run([str(exe)],input=canonical(v),capture_output=True,cwd=root,env=dict(env,**(extra or {})),timeout=18)
        assert r.returncode==(3 if refusal else 0) and not r.stderr,(r.returncode,r.stdout,r.stderr)
        out=json.loads(r.stdout)
        if refusal:check('joined-native-refusal',refusal in out['refusal'],diagnostic=out['refusal'])
        if 'definition' in out:
            bundle.validate('urn:disked:schema:report-worker-definition:2',out['definition'])
            check('joined-automatic-producer-schema',out['definition_digest']==digest(canonical(out['definition'])))
        return out
    def prepare(name,exe=probe,p=POLICIES[0]):
        folder=prefix/name;folder.mkdir();store=folder/'state';store.mkdir();output=folder/'support.json'
        d=call(dict(mode='prepare-joined',operation_id=operation,case_directory=str(case),collection_path=str(collection),collection_digest=digest(collection_bytes),policy=p,destination=str(output),state_directory=str(store)),exe)
        check('joined-preparation-zero-effects',not output.exists() and not list(store.iterdir()) and collection.read_bytes()==collection_bytes and original=={p.name:p.read_bytes() for p in case.iterdir() if p.is_file()},case=name)
        check('joined-current-producer-and-source-bound',d['definition']['image_digest']==digest(exe.read_bytes())[7:] and d['definition']['export']['sources']['collection']['digest']==digest(collection_bytes),case=name)
        return d,store,output
    def grant(d,**changes):
        g=dict(definition_digest=d['definition_digest'],case_read=True,collection_read=True,report_write=True,store_write=True,host_effects=True);g.update(changes);return g
    def start(d,g=None,exe=probe,extra=None):return call(dict(mode='start',definition=d['definition'],grant=grant(d) if g is None else g),exe,extra)
    def inspect(id,store,exe=probe,cancel=False):return call(dict(mode='cancel' if cancel else 'inspect',operation_id=id,state_directory=str(store)),exe)
    def wait(id,store,exe,terminal=True):
        deadline=time.monotonic()+22;last=None
        while time.monotonic()<deadline:
            last=inspect(id,store,exe);s=last.get('value',{}).get('state')
            if s and (s['phase']=='finished' if terminal else last['value'].get('worker_observation')!='running'):
                handle=report_process(s,exe)
                if handle:
                    try:assert K.WaitForSingleObject(handle,3000)==0,('retain actual live joined worker',s)
                    finally:K.CloseHandle(handle)
                return last
            time.sleep(.025)
        raise AssertionError(('retain unresolved joined fixture',last))
    def finish(name,d,store,output,exe,result,terminal=True):
        observed=wait(result['operation_id'],store,exe,terminal);header=json.loads((store/'report.request').read_bytes());raw,rows=history_check(store/'report.records',header);s=rows[-1]['state']
        check('joined-exact-persisted-header',header['definition']==d['definition'] and header['definition_digest']==d['definition_digest'] and header['grant']==grant(d) and len(canonical(header))<=65536)
        decoded=call(dict(mode='history',header=header,records=raw.decode()),exe)
        check('joined-independent-native-history',decoded['complete'] and decoded['state']==s==observed['value']['state'])
        for row in rows:bundle.validate('urn:disked:schema:report-worker-record:2',row)
        if terminal:
            bundle.validate('urn:disked:schema:acquisition-verification-export-outcome:1',s['outcome'])
            check('joined-terminal-handles-released',s['quiescent'] and s['phase']=='finished')
        body=output.read_bytes() if output.exists() else None
        if terminal and s['outcome']['status']=='completed':
            expected=canonical(combined_support(acq,coll,d['definition']['export']['effect']['artifact']['policy']))+b'\n'
            check('joined-independent-selected-output',body==expected and digest(body)==d['definition']['export']['effect']['artifact']['digest'])
            checks=int(s['outcome']['source_checks']);sources=s['outcome']['source_observations']
            check('joined-independent-final-source-pair',checks>=4 and checks%2==0 and sources['case']==dict(state='matched',check_sequence=str(checks-1)) and sources['collection']==dict(state='matched',check_sequence=str(checks)))
        samples.append(dict(kind='actual-joined-worker-'+name,definition=d,header=header,records=rows,observation=observed,artifact_bytes=None if body is None else body.decode()))
        exports.append(dict(name='joined-worker-'+name,outcome=s['outcome'],receipt=s['receipt'],bytes=None if body is None else len(body),sha256=None if body is None else digest(body)))
        return observed,header,raw,rows
    d,store,output=prepare('normal')
    flags=('case_read','collection_read','report_write','store_write','host_effects')
    for bits in itertools.product((False,True),repeat=5):
        if all(bits):continue
        r=start(d,grant(d,**dict(zip(flags,bits))))
        check('joined-31-false-grants-no-effects',r['status']=='refused' and r['operation_id'] is None and r['diagnostic']=='report_worker_grant' and not output.exists() and not list(store.iterdir()),flags=bits)
    for selected in ('sha256:'+'0'*64,digest(canonical(d['definition']['export'])),digest(canonical(d['definition']['export']['effect']))):
        r=start(d,grant(d,definition_digest=selected));check('joined-wrong-inner-digest-no-effects',r['status']=='refused' and r['operation_id'] is None and not list(store.iterdir()) and not output.exists())
    old=grant(d);old.pop('collection_read');r=start(d,old);check('joined-old-grant-no-effects',r['status']=='refused' and not list(store.iterdir()))
    for name,alter in (
        ('u64-metadata',lambda v:v['export']['sources']['collection']['metadata'].update(bytes=str(2**64))),
        ('collection-file-kind',lambda v:v['export']['sources']['collection']['metadata'].update(attributes='1024')),
        ('source-revision',lambda v:v['export']['report'].update(collection_revision='sha256:'+'f'*64)),
        ('source-file-alias',lambda v:v['export']['sources']['collection']['metadata'].update({k:v['export']['sources']['case']['files'][0]['metadata'][k] for k in ('file_id','volume_id')})),
        ('store-ancestry',lambda v:v['store']['ancestors'][-1].update(created='1')),
        ('producer-code',lambda v:v['export']['effect']['resources']['producer'].update(digest='sha256:'+'f'*64)),
        ('artifact-budget',lambda v:v['export']['effect']['artifact'].update(bytes='1048578')),
        ('legacy-version-confusion',lambda v:v.update(schema='org.disked.report-worker-definition-prototype/1')),
        ('critical-field',lambda v:v.update(unexpected=True))):
        changed=copy.deepcopy(d);alter(changed['definition']);changed['definition_digest']=digest(canonical(changed['definition']))
        try:bundle.validate('urn:disked:schema:report-worker-definition:2',changed['definition']);raise AssertionError(('contradictory producer permitted',name))
        except SpecError:check('joined-automatic-definition-contradiction-refused',True,case=name)
        r=start(changed);check('joined-native-definition-contradiction-no-effects',r['status']=='refused' and not list(store.iterdir()) and not output.exists(),case=name)
    for field,value in (('image_digest','f'*64),('host_id','f'*64),('source_revision','f'*40),('input_digest','sha256:'+'f'*64)):
        changed=copy.deepcopy(d);changed['definition'][field]=value;changed['definition_digest']=digest(canonical(changed['definition']));r=start(changed)
        check('joined-changed-execution-binding-no-effects',r['status']=='refused' and not list(store.iterdir()) and not output.exists(),field=field)
    r=start(d,exe=fault);check('joined-different-code-cannot-admit',r['status']=='refused' and r['diagnostic']=='report_worker_definition_changed' and not list(store.iterdir()))
    changed=copy.deepcopy(d);changed['definition']['export']['effect']['artifact']['policy']['raw_values']=True;changed['definition_digest']=digest(canonical(changed['definition']));r=start(changed)
    check('joined-selected-content-reconstructed',r['status']=='refused' and r['diagnostic']=='verification_case_reviewed_definition_changed' and not list(store.iterdir()))
    r=start(d);observed,h,raw,rows=finish('normal',d,store,output,probe,r)
    check('joined-actual-durable-operation',r['operation_id'].startswith('report-op:') and observed['status']=='completed')
    for action in ('inspect','watch','cancel'):
        public=subprocess.run([str(product),'--json','operation',action,r['operation_id'],'--state-dir',str(store)],capture_output=True,cwd=root,env=env,timeout=12)
        envelope=json.loads(public.stdout)
        check('joined-public-profile-gate-refuses',public.returncode==3 and not public.stderr and envelope['status']=='refused' and any(x['code']=='report_worker_profile_unavailable' for x in envelope['diagnostics']) and (store/'report.records').read_bytes()==raw and (store/'report.cancel').read_bytes()==b'0',action=action,diagnostics=envelope['diagnostics'],exit_code=public.returncode,response_sha256=digest(public.stdout))
    again=start(d);check('joined-repeat-does-not-restart',again['operation_id']==r['operation_id'] and (store/'report.records').read_bytes()==raw)
    reader=inspect(r['operation_id'],store,fault);check('joined-compatible-read-not-writer-grant',reader['value']['state']==rows[-1]['state'] and reader['value']['definition']==d['definition'])
    late=inspect(r['operation_id'],store,cancel=True);check('joined-late-cancel-is-too-late',late['value']['cancellation_request']=='too_late' and (store/'report.cancel').read_bytes()==b'0')
    def forge(records):
        previous='0'*64;parts=[]
        for row in records:
            row=copy.deepcopy(row);row['previous']=previous;row.pop('digest',None);previous=hashlib.sha256(canonical(row)).hexdigest();row['digest']=previous;parts.append(canonical(row))
        return (b'\n'.join(parts)+b'\n').decode()
    for name,alter in (
        ('u64-overflow',lambda s:s['outcome'].update(source_checks=str(2**64))),
        ('visit-budget',lambda s:s['outcome'].update(source_checks='258')),
        ('changed-source',lambda s:s['outcome']['source_observations']['case'].update(state='changed')),
        ('missing-visit',lambda s:s['outcome']['source_observations']['case'].update(check_sequence='1')),
        ('wrong-role-position',lambda s:s['outcome']['source_observations']['case'].update(check_sequence=s['outcome']['source_checks'])),
        ('zero-completion',lambda s:s['outcome']['output'].update(submitted_bytes='0',written_bytes='0',read_bytes='0',verified_bytes='0')),
        ('unknown-without-uncertainty',lambda s:s['outcome'].update(status='unknown')),
        ('completion-with-diagnostic',lambda s:s['outcome'].update(diagnostic='unresolved')),
        ('output-completion-with-diagnostic',lambda s:s['outcome']['output'].update(diagnostic='unresolved')),
        ('false-quiet',lambda s:s.update(quiescent=False)),
        ('wrong-output-receipt',lambda s:s['receipt']['output_receipt'].update(artifact_digest='sha256:'+'f'*64)),
        ('wrong-case-scope',lambda s:s['outcome'].update(scope='recorded-acquisition-case-support-export'))):
        changed=copy.deepcopy(rows);alter(changed[-1]['state']);call(dict(mode='history',header=h,records=forge(changed)),refusal='report_worker_');check('joined-rehashed-contradiction-refused',True,case=name)
    torn=call(dict(mode='history',header=h,records=raw.decode()+'{"torn":'));check('joined-torn-keeps-prior-state',not torn['complete'] and torn['state']==rows[-1]['state'])
    for n,p in enumerate(POLICIES):
        d,store,output=prepare('policy-'+str(n),p=p);r=start(d);finish('policy-'+str(n),d,store,output,probe,r);check('joined-sixteen-worker-selected-policies',True,policy=p)
    d,store,output=prepare('delayed-admission',fault);begin=time.monotonic();r=start(d,exe=fault,extra=dict(DISKED_REPORT_WORKER_TEST_ADMISSION_DELAY='1'))
    check('joined-admission-timeout-is-uncertain',r['status']=='unknown' and r['operation_id'] and 2.8<time.monotonic()-begin<8 and not output.exists())
    interim=inspect(r['operation_id'],store,fault);before=(store/'report.records').read_bytes();again=start(d,exe=fault)
    check('joined-late-worker-no-replacement',interim['value']['worker_observation']=='running' and again['operation_id']==r['operation_id'] and (store/'report.records').read_bytes()==before)
    process=report_process(interim['value']['state'],fault);assert process
    job=K.OpenJobObjectW(4,False,'Local\\DiskEd.Fake.Workers.v1.'+d['definition']['host_id']);assert job
    try:
        member=W.BOOL();limits=JobLimits();assert K.IsProcessInJob(process,job,C.byref(member)) and member.value and K.QueryInformationJobObject(job,9,C.byref(limits),C.sizeof(limits),None)
        check('joined-independent-job-limits',limits.basic.flags==0x308 and limits.basic.process_limit==4 and limits.process_memory==128*1024*1024 and limits.job_memory==512*1024*1024)
    finally:K.CloseHandle(job);K.CloseHandle(process)
    finish('delayed-admission',d,store,output,fault,r)
    d,store,output=prepare('cancel-before-create',fault);r=start(d,exe=fault,extra=dict(DISKED_REPORT_WORKER_TEST_EFFECT_DELAY='1'));cancel=inspect(r['operation_id'],store,fault,True)
    check('joined-cancel-request-not-completion',cancel['value']['cancellation_request']=='requested' and not output.exists())
    observed,_,_,_=finish('cancel-before-create',d,store,output,fault,r);s=observed['value']['state'];check('joined-cancel-before-create-observed',s['cancellation_observation']=='observed' and s['outcome']['status']=='cancelled' and not output.exists())
    d,store,output=prepare('cancel-created',fault);release=store.parent/'release';r=start(d,exe=fault,extra=dict(DISKED_REPORT_TEST_EVENT='created',DISKED_REPORT_TEST_PAUSE='1',DISKED_REPORT_TEST_RELEASE_FILE=str(release)))
    deadline=time.monotonic()+5
    while not output.exists():assert time.monotonic()<deadline;time.sleep(.01)
    inspect(r['operation_id'],store,fault,True);release.write_bytes(b'1');observed,_,_,_=finish('cancel-created',d,store,output,fault,r);s=observed['value']['state']
    check('joined-cancel-keeps-created-file',s['outcome']['status']=='cancelled' and s['cancellation_observation']=='observed' and s['receipt']['output_receipt']['output_created_observed'] and output.read_bytes()==b'')
    # Each start's client has exited before inspection; a late receipt remains
    # the same owned child, and late cancellation cannot undo a completed effect.
    d,store,output=prepare('late-receipt',fault);r=start(d,exe=fault,extra=dict(DISKED_REPORT_WORKER_TEST_RECEIPT_DELAY='1'));deadline=time.monotonic()+5
    while True:
        try:body=output.read_bytes();break
        except (FileNotFoundError,PermissionError):assert time.monotonic()<deadline;time.sleep(.01)
    interim=inspect(r['operation_id'],store,fault);check('joined-client-departure-does-not-cancel',interim['value']['worker_observation']=='running' and digest(body)==d['definition']['export']['effect']['artifact']['digest'])
    inspect(r['operation_id'],store,fault,True);observed,_,_,_=finish('late-receipt',d,store,output,fault,r);s=observed['value']['state'];check('joined-late-cancel-keeps-completed-effect',s['outcome']['status']=='completed' and s['cancellation_observation']=='not_observed' and output.read_bytes()==body)
    for phase in ('created','written','flushed','read'):
        d,store,output=prepare('fault-'+phase,fault);r=start(d,exe=fault,extra=dict(DISKED_REPORT_TEST_EVENT=phase));observed,_,_,_=finish('fault-'+phase,d,store,output,fault,r);s=observed['value']['state'];o=s['outcome']['output']
        check('joined-output-fault-keeps-observed-effects',s['outcome']['status']=='failed' and output.exists() and s['receipt']['output_receipt']['output_created_observed'],phase=phase)
        check('joined-output-fault-bytes',output.read_bytes()==(b'' if phase=='created' else canonical(combined_support(acq,coll,POLICIES[0]))+b'\n'),phase=phase)
        if phase=='written':check('joined-write-ack-uncertain',o['written_bytes'] is None)
        if phase=='flushed':check('joined-flush-ack-uncertain',o['flush']=='uncertain')
        if phase=='read':check('joined-read-ack-not-counted',o['read_bytes']=='0')
    d,store,output=prepare('lost-terminal',fault);r=start(d,exe=fault,extra=dict(DISKED_TEST_STORE_FAULT='report_finished.full'));observed,_,raw,rows=finish('lost-terminal',d,store,output,fault,r,False)
    check('joined-terminal-store-failure-not-success',observed['status']=='unknown' and rows[-1]['state']['phase']=='executing' and rows[-1]['state']['outcome'] is None and digest(output.read_bytes())==d['definition']['export']['effect']['artifact']['digest'])
    again=start(d,exe=fault);check('joined-lost-receipt-no-retry',again['operation_id']==r['operation_id'] and again['status']=='unknown' and (store/'report.records').read_bytes()==raw)
    d,store,output=prepare('recreated-source');collection.rename(collection.with_name(collection.name+'.old-generation'));collection.write_bytes(collection_bytes);r=start(d)
    check('joined-recreated-source-no-effects',r['status']=='refused' and r['diagnostic']=='verification_case_reviewed_definition_changed' and not output.exists() and not list(store.iterdir()))
    check('joined-only-selected-metadata-preserved',original=={p.name:p.read_bytes() for p in case.iterdir() if p.is_file()} and collection.read_bytes()==collection_bytes)
