"""Independent binary/JSON vectors for private fake journal declarations.

Framing, identities, records, captures and expected outcomes are chosen in Python
before calling native code. No storage effects, live evidence or authentication.
"""
import argparse,copy,json,subprocess
from pathlib import Path
from test_definitions import fixture,ledger,canonical,sha,h,digests,MAX,maximum_payload_fixture,resource
from test_codec import header,record,H,P,PUB

class Trace:
    def __init__(self,plan=None):
        self.plan=copy.deepcopy(plan or fixture());d=digests(self.plan)
        self.bindings=dict(journal=bytes(range(1,17)).hex(),plan=d['digest'][7:],targets=d['resources_digest'][7:],providers=d['providers_digest'][7:])
        self.records=[];self.receipts=ledger(self.plan)[:3];self.initial=self.receipts[-1];self.admission=sha(canonical(self.initial));self.basis=self.admission
        self.context={k:self.initial[k] for k in ('operation_id','attempt_id','worker_identity','worker_epoch')};self.event_seq=0;self.capture_epoch=0;self.done=[];self.pending='';self.recovery_ref='';self.cancelled=False;self.exit_epoch=None
        self.rows=[dict(resource=r['id'],identity_digest=r['identity_digest'],state_digest=r['state_digest'],epoch=r['epoch'],available=True) for r in self.plan['resources']]
    def add(self,kind,value,**extra):self.records.append(dict(kind=kind,payload=canonical(value) if not isinstance(value,bytes) else value,**extra));return self
    def bootstrap(self):
        self.add(1,self.plan)
        for kind,v in enumerate(self.receipts,2):self.add(kind,v)
        return self
    def parts(self):
        hdr=header(self.bindings);parts=[];previous=hdr[-32:]
        for index,r in enumerate(self.records,1):
            frame=record(hdr,index,previous,r['payload'],r['kind'],r.get('flags',0 if r['kind']>=32768 else 1),epoch=r.get('epoch',1),publisher=r.get('publisher',PUB));parts.append(frame);previous=frame[-32:]
        return hdr,parts
    def data(self):hdr,parts=self.parts();return hdr+b''.join(parts)
    def capture(self):self.capture_epoch+=1;return dict(observer_id='fake:observer',capture_epoch=str(self.capture_epoch),resources=copy.deepcopy(self.rows))
    def event(self,kind,name,step='',**details):
        self.event_seq+=1
        return self.add(kind,dict(schema='org.disked.journal-effect-prototype/1',id=self.context['attempt_id']+':event'+str(self.event_seq),plan_digest=sha(canonical(self.plan)),admission_digest=self.admission,**self.context,sequence=str(self.event_seq),step_id=step,event=name,details=details))
    def intention(self,index=0):
        self.pending=self.plan['steps'][index]['id'];return self.event(5,'intention',self.pending,capture=self.capture())
    def completion(self,index=0):
        step=self.plan['steps'][index];flush=self.capture_epoch
        for e in step['effects']:
            if e['access']=='write':next(r for r in self.rows if r['resource']==e['resource'])['state_digest']=e['after_digest']
        self.done.append(step['id']);self.pending=''
        return self.event(6,'verified_completion',step['id'],capture=self.capture(),target_flush_capture_epoch=str(flush),qualified_fake_flush=True)
    def cancel(self):self.cancelled=True;return self.event(7,'cancellation_request',self.pending,requested=True)
    def recovery(self,observed='before',index=0):
        if self.exit_epoch is None:self.exit_epoch=self.capture_epoch
        exit_epoch=self.exit_epoch;self.capture_epoch+=1;flush=self.capture_epoch
        if observed=='after':
            for e in self.plan['steps'][index]['effects']:
                if e['access']=='write':next(r for r in self.rows if r['resource']==e['resource'])['state_digest']=e['after_digest']
            self.done.append(self.plan['steps'][index]['id']);self.pending=''
        self.event(8,'recovery_observation','' if observed=='terminal' else self.plan['steps'][index]['id'],capture=self.capture(),flush_capture_epoch=str(flush),qualified_fake_flush=True,worker_exited=True,exit_capture_epoch=str(exit_epoch),observed=observed)
        self.recovery_ref='sha256:'+self.parts()[1][-1][-32:].hex();return self
    def checkpoint(self,name='fake:attempt2',epoch='8'):
        value=dict(schema='org.disked.journal-checkpoint-admission-prototype/1',id=name+':admission',plan_digest=sha(canonical(self.plan)),basis_admission_digest=self.basis,operation_id=self.context['operation_id'],attempt_id=name,worker_identity='fake:worker'+name[-1],worker_epoch=epoch,recovery_record_digest=self.recovery_ref,capture=self.capture())
        self.add(4,value);self.admission=sha(canonical(value));self.context={k:value[k] for k in self.context};self.event_seq=0;self.pending='';self.exit_epoch=None;return self
    def seal(self,outcome='completed'):
        exit_epoch=self.capture_epoch if self.exit_epoch is None else self.exit_epoch
        return self.event(9,'seal',capture=self.capture(),worker_exited=True,exit_capture_epoch=str(exit_epoch),outcome=outcome,cancel_acknowledged=outcome=='cancelled')
    def mutate(self,change,index=-1):
        value=json.loads(self.records[index]['payload']);change(value);self.records[index]['payload']=canonical(value);return self
    def request(self,**extra):return dict(expected_plan=copy.deepcopy(self.plan),bindings=copy.deepcopy(self.bindings),publisher=dict(identity=PUB,epoch='1'),bytes=self.data().hex(),**extra)

def cases():
    cases=[]
    def add(name,t,projection=None,semantic='',framing='',accepted=None,data=None,**extra):
        hdr,parts=t.parts();n=len(parts) if accepted is None else accepted;prefix=hdr+b''.join(parts[:n]);last=parts[n-1][-32:] if n else hdr[-32:]
        expected=dict(disposition='invalid' if semantic or framing else 'valid_prefix',diagnostic=framing or ('journal_semantic_rejected' if semantic else ''),semantic_diagnostic=semantic,records=str(n),verified_bytes=str(len(prefix)),last_digest=last.hex())
        if expected['disposition']=='invalid':expected['error_offset']=str(len(prefix))
        request=t.request(**extra)
        if data is not None:request['bytes']=data.hex()
        control=t.request();control['bytes']=prefix.hex()
        cases.append(dict(name=name,request=request,control=control,expected=expected,projection=projection or {}));return cases[-1]
    t=Trace();add('header-is-not-bootstrap',t,dict(bootstrap_complete=False,definition_observed=False))
    t=Trace().bootstrap();add('bound-bootstrap',t,dict(bootstrap_complete=True,events='0',worker_epoch='7',declared_completed_steps=[],pending_intention=''))
    t=Trace().bootstrap().intention().completion().intention(1).completion(1).seal();add('two-step-declared-completion',t,dict(events='5',event_sequence='5',declared_completed_steps=['s.write1','s.write2'],declared_terminal_outcome='completed',capture_epoch='5'))
    golden=copy.deepcopy(t)
    t=Trace().bootstrap().intention().recovery().checkpoint().intention().completion();add('fresh-replayable-attempt',t,dict(attempts='2',event_sequence='2',worker_epoch='8',declared_completed_steps=['s.write1'],pending_intention=''))
    t=Trace().bootstrap().recovery().checkpoint().intention();add('unstarted-step-checkpoint',t,dict(attempts='2',pending_intention='s.write1'))
    t=Trace().bootstrap().intention().recovery('after').checkpoint().intention(1).completion(1).seal();add('observed-after-continues-next-step',t,dict(declared_completed_steps=['s.write1','s.write2'],attempts='2',declared_terminal_outcome='completed'))
    t=Trace().bootstrap().cancel().seal('cancelled');add('cancel-before-intention',t,dict(cancellation_declared=True,declared_terminal_outcome='cancelled'))
    t=Trace().bootstrap().intention().cancel().recovery().seal('cancelled');add('cancel-after-before-reconciliation',t,dict(declared_completed_steps=[],declared_terminal_outcome='cancelled'))
    t=Trace().bootstrap().intention().cancel().recovery().seal('cancelled').mutate(lambda v:v['details'].update(exit_capture_epoch='3'));add('seal-cannot-redefine-declared-exit',t,semantic='semantic_seal_evidence',accepted=len(t.records)-1)
    t=Trace().bootstrap().recovery().recovery().mutate(lambda v:v['details'].update(exit_capture_epoch='3'));add('recovery-cannot-redefine-declared-exit',t,semantic='semantic_recovery_order',accepted=len(t.records)-1)
    t=Trace().bootstrap().intention().cancel().completion().seal('cancelled');add('cancel-after-checkpoint-completion',t,dict(declared_completed_steps=['s.write1'],declared_terminal_outcome='cancelled'))
    t=Trace().bootstrap().intention().completion().intention(1).completion(1).recovery('terminal').seal();add('terminal-reconciliation-still-needs-seal',t,dict(recovery_declaration='terminal',declared_terminal_outcome='completed'))
    t=Trace().bootstrap().intention().completion().intention(1).recovery(index=1);add('nonreplayable-before-state-is-useful-evidence',t,dict(pending_intention='s.write2',recovery_declaration='before',worker_exit_declared=True))
    t.checkpoint();add('nonreplayable-intention-cannot-admit-retry',t,semantic='semantic_replay_forbidden',accepted=len(t.records)-1,projection=dict(attempts='1',pending_intention='s.write2'))
    t=Trace().bootstrap().intention().completion().recovery('before',1).checkpoint().intention(1);add('nonreplayable-unstarted-step-can-be-admitted',t,dict(attempts='2',pending_intention='s.write2'))
    for name,build,code in [
        ('completion-without-intention',lambda:Trace().bootstrap().completion(),'semantic_completion_order'),
        ('second-intention-overlaps',lambda:Trace().bootstrap().intention().intention(),'semantic_intention_order'),
        ('predecessor-not-complete',lambda:Trace().bootstrap().intention(1),'semantic_predecessor'),
        ('intention-after-cancel',lambda:Trace().bootstrap().cancel().intention(),'semantic_intention_order'),
        ('completion-after-declared-exit',lambda:Trace().bootstrap().intention().recovery().completion(),'semantic_completion_order'),
        ('cancel-is-not-effect-resolution',lambda:Trace().bootstrap().intention().cancel().seal('cancelled'),'semantic_seal_scope'),
        ('incomplete-plan-cannot-complete-seal',lambda:Trace().bootstrap().seal(),'semantic_seal_scope'),
        ('cancelled-seal-needs-request',lambda:Trace().bootstrap().seal('cancelled'),'semantic_seal_scope'),
        ('noncheckpoint-step-cannot-cancel-seal',lambda:Trace().bootstrap().intention().completion().intention(1).completion(1).cancel().seal('cancelled'),'semantic_seal_scope'),
        ('checkpoint-needs-recovery',lambda:Trace().bootstrap().checkpoint(),'semantic_checkpoint_reference'),
        ('checkpoint-after-cancel-refuses',lambda:Trace().bootstrap().intention().recovery().cancel().checkpoint(),'semantic_checkpoint_reference')]:
        t=build();add(name,t,semantic=code,accepted=len(t.records)-1)
    t=Trace().add(2,ledger(fixture())[0]);add('receipt-before-plan',t,semantic='semantic_definition_missing',accepted=0)
    t=Trace().bootstrap().add(1,fixture());add('definition-repeated',t,semantic='semantic_definition_order',accepted=4)
    t=Trace().bootstrap().add(4,ledger(fixture())[2]);add('receipt-id-reused',t,semantic='semantic_id_reused',accepted=4)
    t=Trace().bootstrap().add(4,dict(ledger(fixture())[2],id='receipt.second',attempt_id='fake:other'));add('initial-admission-repeated',t,semantic='semantic_initial_admission_repeated',accepted=4)
    for kind in (2,3,4):
        t=Trace().bootstrap();t.records=t.records[:kind];t.add(kind,dict(ledger(fixture())[1 if kind==2 else 0],id='receipt.kind-mismatch'));add('record-kind-mismatch-'+str(kind),t,semantic='semantic_receipt_kind',accepted=len(t.records)-1)
    for field,value,code in [('review_id','receipt.absent','receipt_reference'),('grant_id','receipt.absent','receipt_reference'),('worker_epoch','0','definition_integer')]:
        t=Trace().bootstrap().mutate(lambda v,k=field,x=value:v.update({k:x}));add('initial-admission-'+field,t,semantic=code,accepted=3,projection=dict(bootstrap_complete=False))
    t=Trace().bootstrap().mutate(lambda v:v.update(step_ids=['s.write2']));t.mutate(lambda v:v.update(step_ids=['s.write2'],permissions=[r for r in v['permissions'] if r['resource']!='r.backup']),2);add('admission-predecessor-closure',t,semantic='semantic_admission_dependencies',accepted=3)
    def mutate_event(name,change,code,build=None):
        t=(build or (lambda:Trace().bootstrap().intention()))();t.mutate(change);add(name,t,semantic=code,accepted=len(t.records)-1)
    for field in ('operation_id','attempt_id','worker_identity','admission_digest'):
        mutate_event('wrong-event-'+field,lambda v,k=field:v.update({k:'fake:other'}),'semantic_attempt_mismatch')
    mutate_event('wrong-plan-digest',lambda v:v.update(plan_digest=h('other')),'semantic_plan_mismatch')
    mutate_event('wrong-kind-label',lambda v:v.update(event='verified_completion'),'semantic_event_kind')
    mutate_event('unknown-event-field',lambda v:v.update(force=True),'semantic_shape')
    mutate_event('unknown-details-field',lambda v:v['details'].update(force=True),'semantic_shape')
    mutate_event('unsupported-event-version',lambda v:v.update(schema='org.disked.journal-effect-prototype/9'),'semantic_version')
    for value,code in [('0','semantic_integer'),('01','semantic_integer'),(str(MAX+1),'semantic_integer'),('2','semantic_event_sequence'),(str(MAX),'semantic_event_sequence')]:
        mutate_event('event-sequence-'+value,lambda v,x=value:v.update(sequence=x),code)
    for value in ('0','01',str(MAX+1)):
        mutate_event('capture-epoch-'+value,lambda v,x=value:v['details']['capture'].update(capture_epoch=x),'semantic_integer')
    for field,value in [('identity_digest',h('wrong')),('state_digest',h('wrong')),('epoch','4'),('available',False)]:
        for index,r in enumerate(fixture()['resources']):
            mutate_event('capture-'+r['id']+'-'+field,lambda v,k=field,x=value,i=index:v['details']['capture']['resources'][i].update({k:x}),'semantic_capture_mismatch')
    mutate_event('capture-missing-resource',lambda v:v['details']['capture']['resources'].pop(),'semantic_capture_scope')
    mutate_event('capture-extra-resource',lambda v:v['details']['capture']['resources'].append(copy.deepcopy(v['details']['capture']['resources'][-1])),'semantic_capture_scope')
    mutate_event('capture-resource-order',lambda v:v['details']['capture']['resources'].reverse(),'semantic_capture_mismatch')
    mutate_event('capture-extra-field',lambda v:v['details']['capture'].update(force=True),'semantic_shape')
    for field,value in [('target_flush_capture_epoch','0'),('target_flush_capture_epoch','3'),('qualified_fake_flush',False)]:
        mutate_event('completion-'+field+'-'+str(value),lambda v,k=field,x=value:v['details'].update({k:x}),'semantic_integer' if value=='0' else 'semantic_completion_evidence',lambda:Trace().bootstrap().intention().completion())
    mutate_event('completion-stale-capture',lambda v:v['details']['capture'].update(capture_epoch='1'),'semantic_completion_evidence',lambda:Trace().bootstrap().intention().completion())
    for field,value,code in [('worker_exited',False,'semantic_recovery_evidence'),('qualified_fake_flush',False,'semantic_recovery_evidence'),('exit_capture_epoch','0','semantic_recovery_order'),('flush_capture_epoch','1','semantic_recovery_order'),('observed','mixed','semantic_recovery_state')]:
        mutate_event('recovery-'+field,lambda v,k=field,x=value:v['details'].update({k:x}),code,lambda:Trace().bootstrap().intention().recovery())
    mutate_event('after-state-without-intention',lambda v:v['details'].update(observed='after'),'semantic_recovery_scope',lambda:Trace().bootstrap().recovery())
    for field,value,code in [('basis_admission_digest',h('wrong'),'semantic_checkpoint_reference'),('recovery_record_digest',h('wrong'),'semantic_checkpoint_reference'),('attempt_id','fake:attempt1','semantic_attempt_reused_or_limit'),('worker_epoch','7','semantic_attempt_reused_or_limit'),('worker_epoch',str(MAX+1),'semantic_integer')]:
        t=Trace().bootstrap().intention().recovery().checkpoint().mutate(lambda v,k=field,x=value:v.update({k:x}));add('checkpoint-'+field,t,semantic=code,accepted=len(t.records)-1)
    t=Trace().bootstrap().intention().recovery().checkpoint().intention().mutate(lambda v:v.update(admission_digest=sha(canonical(ledger(fixture())[2]))));add('old-admission-after-checkpoint',t,semantic='semantic_attempt_mismatch',accepted=len(t.records)-1)
    t=Trace().bootstrap().intention().recovery().checkpoint().intention().mutate(lambda v:v.update(sequence='2'));add('new-attempt-sequence-restarts',t,semantic='semantic_event_sequence',accepted=len(t.records)-1)
    for field,value,code in [('worker_exited',False,'semantic_seal_evidence'),('exit_capture_epoch','3','semantic_seal_evidence'),('outcome','unknown','semantic_seal_outcome'),('cancel_acknowledged',True,'semantic_seal_scope')]:
        t=copy.deepcopy(golden).mutate(lambda v,k=field,x=value:v['details'].update({k:x}));add('seal-'+field,t,semantic=code,accepted=len(t.records)-1)
    t=copy.deepcopy(golden).add(32769,b'observation');add('observation-after-seal',t,framing='journal_after_terminal',accepted=len(t.records)-1)
    for raw in (b'',b'{}',b'null',b'\xff',b' {"id":"x"}',b'{"id":"x","id":"x"}'):
        t=Trace().bootstrap().add(5,raw);add('invalid-event-json-'+raw.hex(),t,semantic='semantic_json' if raw in (b'',b'\xff',b'{"id":"x","id":"x"}') else 'semantic_noncanonical' if raw.startswith(b' ') else 'semantic_shape',accepted=4)
    t=Trace().bootstrap().intention();t.records[-1]['payload']=t.records[-1]['payload']+b'\n';add('canonical-no-newline',t,semantic='semantic_noncanonical',accepted=4)
    t=Trace().bootstrap().intention();t.records[-1]['payload']=t.records[-1]['payload'].replace(b'fake:observer',b'fake:\\u006fbserver');add('canonical-no-alternate-escape',t,semantic='semantic_noncanonical',accepted=4)
    for kind in (32768,32769,32770,65535):
        t=Trace().add(kind,b'\xff\x00').bootstrap().intention().add(kind,b'opaque');add('compatible-opaque-observation-'+str(kind),t,dict(observational_records='2',pending_intention='s.write1'))
    for field,value in [('publisher','ff'*16),('epoch',2)]:
        t=Trace().bootstrap();t.records[-1][field]=value;add('publisher-mismatch-'+field,t,semantic='semantic_publisher_mismatch',accepted=3)
    for field in ('plan','targets','providers'):
        t=Trace().bootstrap();request=t.request();request['bindings'][field]='ff'*32;c=add('independent-expected-'+field,t,semantic='semantic_expected_binding',framing='journal_semantic_expected_binding',accepted=0);c['request']=request;c['expected'].update(verified_bytes='0',last_digest='00'*32,error_offset='0',read_calls='0');c['projection'].update(definition_observed=False)
    for field,value in [('identity','00'*16),('epoch','0')]:
        t=Trace().bootstrap();c=add('empty-publisher-'+field,t,semantic='semantic_expected_publisher',framing='journal_semantic_expected_publisher',accepted=0);c['request']['publisher'][field]=value;c['expected'].update(verified_bytes='0',last_digest='00'*32,error_offset='0',read_calls='0')
    for fault,code in [('size-throw','journal_source_observation_failed'),('throw','journal_source_observation_failed'),('short','journal_source_length'),('oversized','journal_source_length')]:
        t=Trace().bootstrap();c=add('source-'+fault,t,framing=code,accepted=0,fault=fault);c['expected'].update(verified_bytes='0',last_digest='00'*32,error_offset='0')
    t=Trace().bootstrap();c=add('source-budget',t,framing='journal_source_budget',accepted=0,announced='16777217');c['expected'].update(verified_bytes='0',last_digest='00'*32,error_offset='0')
    hdr,parts=golden.parts()
    for index,frame in enumerate(parts):
        prefix=hdr+b''.join(parts[:index]);t=copy.deepcopy(golden);t.records=t.records[:index]
        for cut in sorted(set([1,P-1,P,P+(len(frame)-P-32)//2,len(frame)-1])):
            c=add('torn-record-'+str(index)+'-'+str(cut),t,data=prefix+frame[:cut]);c['expected'].update(disposition='torn_tail',diagnostic='journal_final_prefix_incomplete' if cut<P else 'journal_final_record_incomplete',error_offset=str(len(prefix)))
    t=Trace().bootstrap();t.records[-1]['payload']=t.records[-1]['payload'].replace(b'receipt.review',b'receipt.absent');add('rehashed-missing-review',t,semantic='receipt_reference',accepted=3)
    t=Trace().bootstrap();raw=bytearray(t.data());raw[-33]^=1;add('unhashed-payload-corruption',t,framing='journal_payload_checksum',accepted=3,data=raw)
    for count in (127,128):
        t=Trace().add(1,fixture())
        for index in range(count):t.add(2,dict(ledger(fixture())[0],id='review.'+str(index)))
        add('receipt-count-'+str(count),t,dict(receipts=str(count)))
    t.add(2,dict(ledger(fixture())[0],id='review.extra'));add('receipt-count-over-limit',t,semantic='semantic_receipt_budget',accepted=len(t.records)-1)
    for count in (1024,1025):
        t=Trace().bootstrap()
        for _ in range(count):t.recovery()
        add('event-count-'+str(count),t,dict(events='1024'),semantic='semantic_event_budget' if count==1025 else '',accepted=len(t.records)-1 if count==1025 else None)
    t=Trace(maximum_payload_fixture()).bootstrap().intention().completion();add('exact-maximum-definition-binary-payload',t,dict(declared_completed_steps=['s.write1'],bootstrap_complete=True))
    t=Trace().bootstrap().intention().mutate(lambda v:v.update(id='receipt.review'));add('event-cannot-reuse-receipt-id',t,semantic='semantic_id_reused',accepted=4)
    t=Trace().bootstrap().intention().completion().mutate(lambda v:v.update(id='fake:attempt1:event1'));add('event-id-reused',t,semantic='semantic_id_reused',accepted=5)
    t=Trace().add(1,dict(fixture(),id='plan.other'));add('rehashed-definition-is-not-expected-plan',t,semantic='semantic_definition_mismatch',accepted=0)
    t=Trace().bootstrap().intention().recovery().checkpoint().intention().mutate(lambda v:v.update(attempt_id='fake:attempt1',worker_identity='fake:worker1',worker_epoch='7'));add('late-old-worker-event',t,semantic='semantic_attempt_mismatch',accepted=len(t.records)-1)
    t=Trace().bootstrap().intention().completion().intention(1).mutate(lambda v:v['details']['capture'].update(capture_epoch='2'));add('capture-epochs-do-not-restart-with-step',t,semantic='semantic_capture_order',accepted=6)
    t=Trace().bootstrap().intention().cancel().completion().intention(1);add('cancel-blocks-next-step-after-completion',t,semantic='semantic_intention_order',accepted=len(t.records)-1)
    t=Trace().bootstrap().intention().recovery('after').completion();add('recovered-completion-is-not-another-effect',t,semantic='semantic_completion_order',accepted=len(t.records)-1)
    t=Trace().bootstrap()
    for epoch in range(8,11):t.recovery().checkpoint(name='fake:attempt'+str(epoch-6),epoch=str(epoch))
    add('four-attempt-limit',t,dict(attempts='4',worker_epoch='10'))
    t.recovery().checkpoint(name='fake:attempt5',epoch='11');add('fifth-attempt-refuses',t,semantic='semantic_attempt_reused_or_limit',accepted=len(t.records)-1)
    for kind,flags,code in [(5,0,'journal_critical_bit'),(42,1,'journal_unknown_kind'),(32770,1,'journal_unknown_kind')]:
        t=Trace().bootstrap().add(kind,b'opaque',flags=flags);add('critical-compatibility-'+str(kind),t,framing=code,accepted=4)
    p=fixture();template=copy.deepcopy(p['steps'][0]);p['steps']=[]
    p['required_acknowledgements']=['ack.'+str(i).zfill(2)+':'+'x'*121 for i in range(16)]
    for i in range(32):
        s=copy.deepcopy(template);s['id']='s.'+str(i).zfill(2)+':'+'x'*75;s['depends_on']=[] if i==0 else [p['steps'][-1]['id']]
        s['effects'][0].update(before_digest=p['resources'][-1]['state_digest'] if i==0 else h('large-after'+str(i-1)),after_digest=h('large-after'+str(i)));p['steps'].append(s)
    for i in range(27):
        r=resource('r.scratch'+str(i).zfill(2)+':'+'x'*88,'scratch','read',4096,'fd.scratch'+str(i));p['resources'].append(r)
        p['steps'][0]['effects'].append(dict(resource=r['id'],access='read',begin='0',end='1024',before_digest=r['state_digest'],after_digest=r['state_digest']))
    p['resources'].sort(key=lambda r:r['id']);p['steps'][0]['effects'].sort(key=lambda e:e['resource']);assert len(canonical(p))<=65536
    t=Trace(p).add(1,p);grant=ledger(p)[1];retained=len(canonical(p));n=0
    while True:
        candidate=dict(grant,id='grant.'+str(n).zfill(3));size=len(canonical(candidate))
        if retained+size>1048576:break
        t.add(3,candidate);retained+=size;n+=1
    assert n<128
    add('retained-payload-byte-bound',t,dict(receipts=str(n),retained_payload_bytes=str(retained),bootstrap_complete=False))
    t.add(3,candidate);add('retained-payload-byte-over-bound',t,semantic='semantic_receipt_budget',accepted=len(t.records)-1,projection=dict(retained_payload_bytes=str(retained)))
    return cases

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--probe',type=Path,required=True);ap.add_argument('--root',type=Path,default=Path('.'));ap.add_argument('--evidence',type=Path);a=ap.parse_args()
    profile=json.loads((a.root/'spec/catalog/journal-semantics-prototype.json').read_bytes());assert profile['max_receipts']==128 and profile['max_retained_payload_bytes']==1048576 and profile['max_events']==1024 and profile['max_attempts']==4 and not any(profile[k] for k in ('authenticates','authorizes_effects','qualifies_durability'))
    suite=cases();requests=b''.join(canonical(v)+b'\n' for v in [c['request'] for c in suite]+[c['control'] for c in suite]);process=subprocess.run([str(a.probe.resolve())],input=requests,capture_output=True,timeout=90)
    assert process.returncode==0 and not process.stderr;lines=process.stdout.splitlines();assert len(lines)==2*len(suite);observations=[];failed=[]
    for c,line,control_line in zip(suite,lines[:len(suite)],lines[len(suite):]):
        result=json.loads(line);errors=[]
        if 'error' in result:errors.append('root:'+result['error'])
        else:
            for k,v in c['expected'].items():
                if result[k]!=v:errors.append(dict(field=k,expected=v,actual=result[k]))
            projection=result['projection'];control=json.loads(control_line)
            if control.get('disposition')!='valid_prefix' or control.get('semantic_diagnostic') or control.get('projection')!=projection:errors.append('projection-differs-from-valid-prefix-control')
            for k,v in c['projection'].items():
                if projection[k]!=v:errors.append(dict(field=k,expected=v,actual=projection[k]))
            if any(projection[k] for k in ('authenticated','authorizes_effects','qualifies_durability','replay_authorized','retirement_authorized')) or not projection['requires_live_reconciliation'] or int(result['largest_read'])>65536:errors.append('authority-or-boundary')
        observations.append(dict(name=c['name'],passed=not errors,input_sha256=sha(canonical(c['request'])),output_sha256=sha(line),control_input_sha256=sha(canonical(c['control'])),control_output_sha256=sha(control_line)))
        if errors:failed.append(dict(name=c['name'],errors=errors))
    evidence=dict(scope='private-fake-binary-journal-declarations',cases=len(suite),native_inspections=2*len(suite),passed=not failed,authorizes_effects=False,authenticates=False,qualifies_durability=False,observations=observations)
    if a.evidence:a.evidence.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8',newline='\n')
    assert not failed,json.dumps(failed[:12],indent=2)
    print(str(len(suite))+' semantic binary journal scenarios passed; declarations only, no live durability or replay authority')

if __name__=='__main__':main()
