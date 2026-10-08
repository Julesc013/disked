"""Contract fixtures for the closed fake-memory journal/effect model.

No host media, file writer, process-liveness probe or physical flush is used.
Resource-state expectations and crash fates are chosen before running native code.
"""
import argparse,copy,json,subprocess
from pathlib import Path
from test_definitions import fixture,ledger,canonical,sha,h,MAX,resource

CONFIG=dict(entries_limit='512',bytes_limit='1048576',attempts_limit='4',qualified_fake_flush=True)
class Case:
    def __init__(self,name,plan=None,config=None):
        self.name=name;self.plan=copy.deepcopy(plan or fixture());self.receipts=ledger(self.plan)[:3];self.config=copy.deepcopy(config or CONFIG)
        self.context={k:self.receipts[2][k] for k in ('operation_id','attempt_id','worker_identity','worker_epoch')}
        self.rows=[dict(resource=r['id'],identity_digest=r['identity_digest'],state_digest=r['state_digest'],epoch=r['epoch'],available=True) for r in self.plan['resources']]
        self.actions=[];self.checks=[];self.epoch=0;self.final={};self.root_error=None
    def add(self,op,expect=None,error=None,**data):
        self.actions.append(dict(op=op,**self.context,**data));self.checks.append(dict(expect=expect or {},error=error));return self
    def capture(self,expect=None,error=None,epoch=None):
        if epoch is None:self.epoch+=1;epoch=self.epoch
        return self.add('capture',expect,error,observer_id='fake:observer',capture_epoch=str(epoch),resources=copy.deepcopy(self.rows))
    def change(self,name,**changes):
        row=next(r for r in self.rows if r['resource']==name);row.update(changes)
        return self.add('change_resource',resource=name,**{k:row[k] for k in ('identity_digest','state_digest','epoch','available')})
    def result(self,step=0,outcome='after',expect=None,error=None):
        if not error and outcome!='before':
            for e in self.plan['steps'][step]['effects']:
                if e['access']=='write':next(r for r in self.rows if r['resource']==e['resource'])['state_digest']=e['after_digest'] if outcome=='after' else h('fake:mixed:'+e['resource'])
        return self.add('effect_result',expect,error,outcome=outcome)
    def start(self,step=0):
        self.add('journal_flush',dict(operation_status='active',worker_status='running'),fault='none').capture()
        return self.add('intention',dict(effect_certainty='not_started'),step_id=self.plan['steps'][step]['id'],fault='none').add('journal_flush',fault='none')
    def complete(self,step=0):
        return self.add('dispatch').result(step).add('target_flush',fault='none').capture().add('verify',capture_epoch=str(self.epoch)).add('completion',fault='none').add('journal_flush',dict(completed_steps=str(step+1)),fault='none')
    def recovery_capture(self):
        return self.capture().add('recovery_flush',fault='none').capture()
    def reconcile(self,observed):
        return self.add('reconcile',observed=observed,capture_epoch=str(self.epoch),fault='none').add('journal_flush',fault='none')
    def replace(self,new_id='fake:attempt2',new_worker='fake:worker2',epoch='8',expect=None,error=None):
        self.add('replace',expect,error,new_attempt_id=new_id,new_worker_identity=new_worker,new_worker_epoch=epoch,fault='none')
        if not error:self.context.update(attempt_id=new_id,worker_identity=new_worker,worker_epoch=epoch)
        return self
    def request(self):return dict(plan=self.plan,receipts=self.receipts,configuration=self.config,actions=self.actions)

def frame_history(output,plan):
    for journal in output['history']:
        previous=sha(canonical(plan));encoded=[]
        assert int(journal['stable_entries'])<=len(journal['events'])
        sealed=False
        for index,event in enumerate(journal['events'],1):
            assert not sealed and event['sequence']==str(index) and event['previous']==previous
            body={k:v for k,v in event.items() if k not in ('digest','previous')}
            expected=sha(b'DiskEd.fake.guard.log/1\n'+previous.encode()+canonical(body));assert event['digest']==expected
            previous=expected;encoded.append(canonical(event)+b'\n');sealed=event['kind']=='9'
        assert journal['digest']==sha(b''.join(encoded)+journal['tail'].encode())

def matches(snapshot,expected):return all(snapshot.get(k)==v for k,v in expected.items())
def bootstrap_bytes(c):
    previous=sha(canonical(c.plan));total=0
    for i,data in enumerate([c.plan]+c.receipts,1):
        body=dict(kind=str(i),sequence=str(i),**c.context,publisher_identity='fake:publisher',publisher_epoch='1',step_id='',data=data)
        digest=sha(b'DiskEd.fake.guard.log/1\n'+previous.encode()+canonical(body));event=dict(body,previous=previous,digest=digest);total+=len(canonical(event));previous=digest
    return total
def invariant(s):
    return not any(s[k] for k in ('authenticated','authorizes_effects','physical_durability_qualified','file_io')) and s['dependencies_retained'] is True and int(s['journal']['stable_entries'])<=int(s['journal']['entries'])<=512 and (not s['retirement_eligible'] or (s['operation_status'] in ('completed','cancelled') and s['worker_status']=='exited' and s['capture_current']))

def cases():
    out=[]
    def keep(c):out.append(c);return c
    c=keep(Case('two-step-stable-completion'));c.start().complete().capture().add('intention',step_id='s.write2',fault='none').add('journal_flush',fault='none').complete(1)
    c.add('worker_exit').add('seal',fault='none').add('journal_flush',dict(operation_status='completed',retirement_eligible=False),fault='none').capture(dict(retirement_eligible=True))
    c.final=dict(operation_status='completed',completed_steps='2',dispatches='2',resource_writes='2',worker_status='exited',retirement_eligible=True)
    c=keep(Case('no-effect-before-stable-admission'));c.add('dispatch',error='model_worker_not_active').capture().add('intention',error='model_worker_not_active',step_id='s.write1',fault='none');c.final=dict(dispatches='0',resource_writes='0')
    c=keep(Case('intention-is-not-durable'));c.add('journal_flush',fault='none').capture().add('intention',step_id='s.write1',fault='none').add('dispatch',error='model_dispatch_order');c.final=dict(dispatches='0',resource_writes='0')
    c=keep(Case('no-completion-from-result'));c.start().add('dispatch').result().capture().add('completion',error='model_completion_order',fault='none');c.final=dict(completed_steps='0',effect_certainty='reported_after')
    c=keep(Case('no-verification-before-flush'));c.start().add('dispatch').result().capture().add('verify',error='model_verification_order',capture_epoch=str(c.epoch))
    c=keep(Case('no-verification-from-preflush-capture'));c.start().add('dispatch').result().capture().add('target_flush',fault='none').add('verify',error='model_verification_order',capture_epoch=str(c.epoch))
    c=keep(Case('no-completion-before-fresh-verification'));c.start().add('dispatch').result().add('target_flush',fault='none').add('completion',error='model_capture_stale',fault='none')
    c=keep(Case('completion-must-be-stable'));c.start().add('dispatch').result().add('target_flush',fault='none').capture().add('verify',capture_epoch=str(c.epoch)).add('completion',dict(completed_steps='0'),fault='none').add('intention',error='model_intention_order',step_id='s.write2',fault='none')
    c=keep(Case('predecessor-not-completed'));c.add('journal_flush',fault='none').capture().add('intention',error='model_predecessor_incomplete',step_id='s.write2',fault='none')
    c=keep(Case('client-loss-does-not-cancel'));c.start().add('dispatch').add('client_disconnect',dict(client_connected=False,cancellation_requested=False)).result().add('client_reconnect',dict(client_connected=True,dispatches='1',completed_steps='0'));c.final=dict(dispatches='1',effect_certainty='reported_after')
    c=keep(Case('duplicate-result-is-not-second-effect'));c.start().add('dispatch').result().result(error='model_effect_result_order');c.final=dict(resource_writes='1',dispatches='1')
    c=keep(Case('timeout-late-result-retains-quarantine'));c.start().add('dispatch').add('timeout',dict(worker_status='stalled',effect_certainty='uncertain')).result(expect=dict(operation_status='unresolved',completed_steps='0',worker_status='stalled')).add('target_flush',error='model_worker_not_active',fault='none').replace(error='model_replace_guard');c.final=dict(dispatches='1',retirement_eligible=False)
    c=keep(Case('timeout-is-not-worker-exit'));c.start().add('dispatch').add('timeout').capture().add('recovery_flush',error='model_recovery_guard',fault='none')
    c=keep(Case('worker-exit-is-not-postcondition'));c.start().add('dispatch').add('worker_exit').capture().replace(error='model_replace_guard');c.final=dict(effect_certainty='uncertain',completed_steps='0')
    for op in ('dispatch','intention','completion','seal'):
        c=keep(Case('early-'+op));params={'step_id':'s.write1','fault':'none'} if op=='intention' else {'fault':'none'} if op in ('completion','seal') else {}
        c.add(op,error='model_seal_guard' if op=='seal' else 'model_worker_not_active',**params)
    for step_phase in ('idle','prepared','dispatched','completed'):
        c=keep(Case('cancellation-'+step_phase));c.add('journal_flush',fault='none').capture()
        if step_phase!='idle':c.add('intention',step_id='s.write1',fault='none').add('journal_flush',fault='none')
        if step_phase in ('dispatched','completed'):c.add('dispatch')
        if step_phase=='completed':c.result().add('target_flush',fault='none').capture().add('verify',capture_epoch=str(c.epoch)).add('completion',fault='none').add('journal_flush',fault='none')
        c.add('cancel_request',dict(cancellation_requested=True,cancellation_acknowledged=False),fault='none').add('cancel_checkpoint',error='model_cancellation_order').add('journal_flush',fault='none')
        if step_phase=='dispatched':c.add('cancel_checkpoint',error='model_cancellation_order').result().add('target_flush',fault='none').capture().add('verify',capture_epoch=str(c.epoch)).add('completion',fault='none').add('journal_flush',fault='none')
        c.add('cancel_checkpoint',dict(cancellation_acknowledged=True)).add('worker_exit').add('seal',fault='none').add('journal_flush',dict(operation_status='cancelled'),fault='none').capture(dict(retirement_eligible=True))
        c.final=dict(operation_status='cancelled',cancellation_acknowledged=True,dispatches='1' if step_phase in ('dispatched','completed') else '0')
    c=keep(Case('cancel-blocks-another-dispatch'));c.start().add('cancel_request',fault='none').add('journal_flush',fault='none').add('dispatch',error='model_dispatch_order');c.final=dict(dispatches='0')
    c=keep(Case('no-seal-live-worker'));c.start().complete().capture().add('intention',step_id='s.write2',fault='none').add('journal_flush',fault='none').complete(1).add('seal',error='model_seal_guard',fault='none')
    c=keep(Case('noncheckpoint-step-cannot-acknowledge'));c.start().complete().capture().add('intention',step_id='s.write2',fault='none').add('journal_flush',fault='none').complete(1).add('cancel_request',fault='none').add('journal_flush',fault='none').add('cancel_checkpoint',error='model_cancellation_checkpoint')
    for boundary in ('intention','completion','seal'):
        for fault in ('before','torn'):
            c=keep(Case('append-'+boundary+'-'+fault));c.add('journal_flush',fault='none').capture()
            if boundary!='intention':c.add('intention',step_id='s.write1',fault='none').add('journal_flush',fault='none').add('dispatch').result().add('target_flush',fault='none').capture().add('verify',capture_epoch=str(c.epoch))
            if boundary=='seal':c.add('completion',fault='none').add('journal_flush',fault='none').add('cancel_request',fault='none').add('journal_flush',fault='none').add('cancel_checkpoint').add('worker_exit')
            params=dict(fault=fault);params.update({'step_id':'s.write1'} if boundary=='intention' else {})
            c.add(boundary,dict(operation_status='unresolved',diagnostic='model_append_'+('before_failure' if fault=='before' else 'torn')),**params).add('dispatch',error='model_worker_not_active')
            c.final=dict(completed_steps='1' if boundary=='seal' else '0',retirement_eligible=False)
    for fault in ('error','unqualified'):
        c=keep(Case('journal-flush-'+fault));c.add('journal_flush',dict(operation_status='unresolved',worker_status='prepared',dispatches='0'),fault=fault).add('dispatch',error='model_worker_not_active')
        c=keep(Case('target-flush-'+fault));c.start().add('dispatch').result().add('target_flush',dict(operation_status='unresolved'),fault=fault).capture().add('verify',error='model_worker_not_active',capture_epoch=str(c.epoch));c.final=dict(completed_steps='0',retirement_eligible=False)
    c=keep(Case('unqualified-provider-is-not-durability',config=dict(CONFIG,qualified_fake_flush=False)));c.add('journal_flush',dict(diagnostic='model_journal_flush_unqualified',dispatches='0'),fault='none')
    # Cut the complete healthy run at every action boundary. Crash fate choices
    # are an independent oracle: acknowledged flushes survive, an unacknowledged
    # complete log prefix and dispatched unflushed after-state may also survive.
    golden=out[0]
    for cut in range(len(golden.actions)+1):
        prefix_actions=golden.actions[:cut];frames=[('1',None),('2',None),('3',None),('4',None)];stable=0;active=0;dispatched=False;pending=False;durable_state=fixture()['resources'][-1]['state_digest'];flushed=False
        for action in prefix_actions:
            op=action['op']
            if op=='intention':active=0 if action['step_id']=='s.write1' else 1;pending=True;dispatched=False;flushed=False;frames.append(('5',active))
            if op=='dispatch':dispatched=True
            if op=='target_flush':durable_state=fixture()['steps'][active]['effects'][0]['after_digest'];flushed=True
            if op=='completion':frames.append(('6',active))
            if op=='seal':frames.append(('9',None))
            if op=='journal_flush':
                stable=len(frames)
                if frames[-1][0]=='6':pending=False
        prefixes=sorted({stable,len(frames)})
        fates=[False,True] if pending and dispatched and not flushed else [False]
        for persisted_prefix in prefixes:
            for persists in fates:
                c=keep(Case('crash-boundary-%02d-prefix-%d-after-%s'%(cut,persisted_prefix,persists)))
                c.actions=copy.deepcopy(prefix_actions);c.checks=copy.deepcopy(golden.checks[:cut]);c.epoch=max([int(x['capture_epoch']) for x in prefix_actions if x['op']=='capture'] or [0])
                after=fixture()['steps'][active]['effects'][0]['after_digest'];state=after if persists else durable_state
                next(r for r in c.rows if r['resource']=='r.target')['state_digest']=state
                c.add('crash',dict(operation_status='unresolved',retirement_eligible=False),prefix_entries=str(persisted_prefix),persist_after=['r.target'] if persists else [],torn_tail=False).capture()
                c.add('dispatch',error='model_worker_not_active').replace(error='model_replace_guard')
                if persisted_prefix<4:
                    c.add('recovery_flush',error='model_recovery_guard',fault='none');c.final=dict(recovery_status='unbound',dispatches='0',retirement_eligible=False);continue
                completed={s for kind,s in frames[:persisted_prefix] if kind=='6'}
                intention=[s for kind,s in frames[:persisted_prefix] if kind=='5' and s not in completed]
                recovery_step=intention[-1] if intention else (0 if 0 not in completed else 1)
                c.add('recovery_flush',fault='none').capture()
                if len(completed)==2:
                    if frames[persisted_prefix-1][0]=='9':c.add('fork_journal').add('journal_flush',fault='none')
                    c.reconcile('terminal').add('seal',fault='none').add('journal_flush',fault='none')
                    c.final=dict(operation_status='completed',completed_steps='2',retirement_eligible=True);continue
                is_after=state==c.plan['steps'][recovery_step]['effects'][0]['after_digest']
                c.reconcile('after' if is_after else 'before')
                if not is_after and recovery_step==1 and intention:
                    c.replace(error='model_replay_forbidden');c.final=dict(operation_status='unresolved',retirement_eligible=False,completed_steps='1');continue
                if is_after and recovery_step==1:
                    c.add('seal',fault='none').add('journal_flush',fault='none');c.final=dict(operation_status='completed',completed_steps='2');continue
                c.replace().add('journal_flush',fault='none').capture()
                if not is_after and recovery_step==0:
                    c.add('intention',step_id='s.write1',fault='none').add('journal_flush',fault='none').complete()
                    c.capture()
                c.add('intention',step_id='s.write2',fault='none').add('journal_flush',fault='none').complete(1)
                c.add('worker_exit').add('seal',fault='none').add('journal_flush',fault='none').capture()
                c.final=dict(operation_status='completed',completed_steps='2',retirement_eligible=True)
    # Stalled/exited old worker, fresh observation, exact after-state and a new
    # attempt for the remaining step; late old-context replies cannot act.
    c=keep(Case('late-result-observe-after-new-attempt'));c.start().add('dispatch').add('timeout').result().add('worker_exit').recovery_capture().reconcile('after')
    old=copy.deepcopy(c.context);c.replace().add('journal_flush',fault='none').capture();c.add('effect_result',error='model_context_mismatch',outcome='after');c.actions[-1].update(old)
    c.add('intention',step_id='s.write2',fault='none').add('journal_flush',fault='none').complete(1).add('worker_exit').add('seal',fault='none').add('journal_flush',fault='none').capture();c.final=dict(dispatches='2',completed_steps='2',operation_status='completed',retirement_eligible=True)
    c=keep(Case('recovery-before-new-attempt-does-not-blindly-replay'));c.start().add('dispatch').add('timeout').add('worker_exit').recovery_capture().reconcile('before').replace().add('dispatch',error='model_worker_not_active').add('journal_flush',fault='none').add('intention',error='model_capture_stale',step_id='s.write1',fault='none');c.final=dict(dispatches='1',completed_steps='0')
    c=keep(Case('cancel-after-quiescent-before-reconciliation'));c.start().add('dispatch').add('cancel_request',fault='none').add('journal_flush',fault='none').add('timeout').add('worker_exit').recovery_capture().reconcile('before').add('cancel_checkpoint').add('seal',fault='none').add('journal_flush',fault='none');c.final=dict(operation_status='cancelled',dispatches='1',retirement_eligible=True)
    for observed in ('before','after'):
        c=keep(Case('reconcile-'+observed+'-requires-exit-and-flush'));c.start().add('dispatch').add('timeout').capture().add('reconcile',error='model_recovery_guard',observed=observed,capture_epoch=str(c.epoch),fault='none').add('worker_exit').capture().add('reconcile',error='model_recovery_capture',observed=observed,capture_epoch=str(c.epoch),fault='none')
    c=keep(Case('old-capture-cannot-reconcile-exited-worker'));c.start().add('dispatch').add('timeout').capture().add('worker_exit').add('recovery_flush',error='model_capture_stale',fault='none')
    c=keep(Case('mixed-state-remains-unresolved'));c.start().add('dispatch').result(outcome='mixed').add('worker_exit').recovery_capture().add('reconcile',error='model_recovery_state',observed='before',capture_epoch=str(c.epoch),fault='none').add('reconcile',error='model_recovery_state',observed='after',capture_epoch=str(c.epoch),fault='none');c.final=dict(completed_steps='0',operation_status='unresolved',retirement_eligible=False)
    for field in ('identity_digest','epoch','state_digest','available'):
        for resource_name in ('r.target','r.code','r.provider','r.backup','r.journal'):
            c=keep(Case('changed-'+resource_name+'-'+field));c.start()
            value='4' if field=='epoch' else False if field=='available' else h('changed')
            c.change(resource_name,**{field:value}).add('dispatch',error='model_capture_stale')
            code='model_resource_unavailable' if field=='available' else 'model_identity_mismatch' if field in ('identity_digest','epoch') else 'model_dependency_mismatch' if resource_name!='r.target' else None
            c.capture(error=code)
            if code is None:c.add('dispatch',error='model_precondition')
            c.final=dict(dispatches='0',completed_steps='0',retirement_eligible=False)
    for key in ('operation_id','attempt_id','worker_identity','worker_epoch'):
        c=keep(Case('stale-context-'+key));c.start();c.add('dispatch',error='model_context_mismatch');c.actions[-1][key]='8' if key=='worker_epoch' else 'fake:other';c.final=dict(dispatches='0')
    for value in ('0','01',str(MAX+1)):
        c=keep(Case('invalid-worker-epoch-'+value));c.add('client_disconnect',error='model_integer');c.actions[-1]['worker_epoch']=value
        c=keep(Case('invalid-capture-epoch-'+value));c.add('capture',error='model_integer',observer_id='fake:observer',capture_epoch=value,resources=c.rows)
    c=keep(Case('maximum-worker-epoch'));c.receipts[-1]['worker_epoch']=str(MAX);c.context['worker_epoch']=str(MAX);c.start().add('dispatch');c.final=dict(dispatches='1',worker_epoch=str(MAX))
    c=keep(Case('maximum-capture-epoch'));c.add('journal_flush',fault='none').capture(epoch=MAX).capture(error='model_capture_epoch',epoch=MAX);c.final=dict(capture_epoch=str(MAX),dispatches='0')
    for mutation,code in [('extra','model_shape'),('missing','model_shape'),('unknown','model_action_unknown'),('bad-fault','model_enum')]:
        c=keep(Case('strict-action-'+mutation));c.add('journal_flush',error=code,fault='none')
        if mutation=='extra':c.actions[-1]['extra']=True
        if mutation=='missing':c.actions[-1].pop('fault')
        if mutation=='unknown':c.actions[-1]['op']='force'
        if mutation=='bad-fault':c.actions[-1]['fault']='force'
    for value in ('0','513',str(MAX+1),1):
        c=keep(Case('entry-budget-'+str(value),config=dict(CONFIG,entries_limit=value)));c.root_error='model_string' if not isinstance(value,str) else 'model_integer' if value in ('0',str(MAX+1)) else 'model_budget'
    c=keep(Case('bootstrap-entry-budget',config=dict(CONFIG,entries_limit='3')));c.root_error='model_bootstrap_budget'
    c=keep(Case('selected-entry-budget',config=dict(CONFIG,entries_limit='4')));c.add('journal_flush',fault='none').capture().add('intention',dict(operation_status='unresolved',diagnostic='model_journal_limit'),step_id='s.write1',fault='none');c.final=dict(dispatches='0')
    c=keep(Case('selected-attempt-budget',config=dict(CONFIG,attempts_limit='1')));c.start().add('dispatch').add('worker_exit').recovery_capture().reconcile('before').replace(error='model_attempt_limit_or_reuse')
    for epoch,new_id in [('7','fake:attempt2'),('8','fake:attempt1')]:
        c=keep(Case('attempt-reuse-or-epoch-'+epoch+'-'+new_id));c.start().add('dispatch').add('worker_exit').recovery_capture().reconcile('before').replace(new_id=new_id,epoch=epoch,error='model_attempt_limit_or_reuse')
    c=keep(Case('maximum-action-count'))
    for i in range(1024):c.add('client_disconnect' if i%2==0 else 'client_reconnect')
    c.final=dict(actions='1024',dispatches='0',operation_status='pending')
    c=keep(Case('action-count-over-limit'));c.actions=[dict(op='client_disconnect',**c.context)]*1025;c.root_error='probe_action_limit'
    c=keep(Case('admission-needs-predecessor-closure'));c.receipts[1]['step_ids']=['s.write2'];c.receipts[1]['permissions']=[r for r in c.receipts[1]['permissions'] if r['resource']!='r.backup'];c.receipts[2]['step_ids']=['s.write2'];c.root_error='model_admission_dependencies'
    p=fixture();r=copy.deepcopy(p['resources'][-1]);r.update(id='r.target2',identity='fake:r.target2',aliases=['fake:r.target2'],identity_digest=h('identity:r.target2'),state_digest=h('initial:r.target2'));p['resources'].append(r)
    p['steps'][1]['effects'][0].update(resource='r.target2',before_digest=r['state_digest'])
    c=keep(Case('future-target-change-invalidates-current-plan',p));c.start().change('r.target2',state_digest=h('changed')).capture().add('dispatch',error='model_precondition');c.final=dict(dispatches='0',resource_writes='0')
    for key,value,code in [('identity_digest',h('changed'),'model_identity_mismatch'),('epoch','4','model_identity_mismatch'),('available',False,'model_resource_unavailable'),('state_digest',h('changed'),'model_postcondition_failed')]:
        c=keep(Case('target-flush-reidentifies-'+key));c.start().add('dispatch').result().change('r.target',**{key:value}).add('target_flush',error=code,fault='none');c.final=dict(target_flushes='0',completed_steps='0')
        c=keep(Case('journal-flush-reidentifies-'+key));c.start().change('r.journal',**{key:value}).add('journal_flush',dict(operation_status='unresolved',diagnostic='model_journal_dependency'),fault='none');c.final=dict(journal_flushes='2',retirement_eligible=False)
    c=keep(Case('unstarted-nonreplayable-step-new-admission'));c.start().complete().add('worker_exit').recovery_capture().reconcile('before').replace().add('journal_flush',fault='none').capture().add('intention',step_id='s.write2',fault='none').add('journal_flush',fault='none').complete(1).add('worker_exit').add('seal',fault='none').add('journal_flush',fault='none').capture();c.final=dict(completed_steps='2',dispatches='2',operation_status='completed')
    c=keep(Case('torn-tail-preserved-explicit-new-generation'));c.add('journal_flush',fault='none').capture().add('intention',dict(operation_status='unresolved'),step_id='s.write1',fault='torn').add('worker_exit').recovery_capture().add('reconcile',dict(diagnostic='model_journal_unwritable'),observed='before',capture_epoch=str(c.epoch),fault='none')
    c.add('fork_journal').add('dispatch',error='model_worker_not_active').add('journal_flush',fault='none').reconcile('before').replace().add('journal_flush',fault='none').capture().add('intention',step_id='s.write1',fault='none').add('journal_flush',fault='none').complete().capture().add('intention',step_id='s.write2',fault='none').add('journal_flush',fault='none').complete(1).add('worker_exit').add('seal',fault='none').add('journal_flush',fault='none').capture();c.final=dict(operation_status='completed',dispatches='2',retirement_eligible=True)
    c=keep(Case('torn-tail-cannot-fork-live-worker'));c.add('journal_flush',fault='none').capture().add('intention',step_id='s.write1',fault='torn').add('fork_journal',error='model_fork_guard').add('worker_exit').add('fork_journal',error='model_capture_stale');c.final=dict(dispatches='0')
    c=keep(Case('new-generation-count-bounded'));c.add('journal_flush',fault='none').capture().add('intention',step_id='s.write1',fault='torn').add('worker_exit').recovery_capture()
    for i in range(3):
        c.add('fork_journal').add('journal_flush',fault='none').add('reconcile',observed='before',capture_epoch=str(c.epoch),fault='torn')
    c.add('fork_journal',error='model_generation_limit');c.final=dict(dispatches='0',retirement_eligible=False,operation_status='unresolved')
    c=keep(Case('crash-retains-partial-unacknowledged-intention'));c.add('journal_flush',fault='none').capture().add('intention',step_id='s.write1',fault='none').add('crash',prefix_entries='4',persist_after=[],torn_tail=True).recovery_capture().add('reconcile',dict(diagnostic='model_journal_unwritable'),observed='before',capture_epoch=str(c.epoch),fault='none').add('fork_journal').add('journal_flush',fault='none').reconcile('before');c.final=dict(dispatches='0',completed_steps='0',operation_status='unresolved')
    for prefix,code in [('3','model_crash_prefix'),('6','model_crash_prefix'),(str(MAX+1),'model_integer')]:
        c=keep(Case('invalid-crash-prefix-'+prefix));c.start().add('crash',error=code,prefix_entries=prefix,persist_after=[],torn_tail=False)
    c=keep(Case('crash-cannot-invent-after-state-before-dispatch'));c.start().add('crash',error='model_crash_resources',prefix_entries='5',persist_after=['r.target'],torn_tail=False)
    c=keep(Case('crash-tail-needs-unacknowledged-data'));c.start().add('crash',error='model_crash_tail',prefix_entries='5',persist_after=[],torn_tail=True)
    for fault in ('before','torn'):
        c=keep(Case('replacement-admission-failure-'+fault));c.start().add('dispatch').add('worker_exit').recovery_capture().reconcile('before')
        c.replace();c.actions[-1]['fault']=fault;c.add('dispatch',error='model_worker_not_active');c.final=dict(completed_steps='0',dispatches='1',operation_status='unresolved')
    for fault in ('error','unqualified'):
        c=keep(Case('recovery-flush-'+fault));c.start().add('dispatch').add('worker_exit').capture().add('recovery_flush',dict(operation_status='unresolved'),fault=fault).capture().add('reconcile',error='model_recovery_capture',observed='before',capture_epoch=str(c.epoch),fault='none')
    c=keep(Case('bootstrap-byte-limit-exact'));limit=bootstrap_bytes(c);c.config['bytes_limit']=str(limit);c.add('journal_flush',fault='none').capture().add('intention',dict(diagnostic='model_journal_limit',dispatches='0'),step_id='s.write1',fault='none')
    c=keep(Case('bootstrap-byte-limit-one-less'));c.config['bytes_limit']=str(bootstrap_bytes(c)-1);c.root_error='model_bootstrap_budget'
    for key,value,code in [('bytes_limit','1048577','model_budget'),('attempts_limit','5','model_budget'),('attempts_limit','0','model_integer'),('bytes_limit','01','model_integer'),('qualified_fake_flush','yes','model_boolean')]:
        c=keep(Case('configuration-'+key+'-'+value));c.config[key]=value;c.root_error=code
    c=keep(Case('configuration-extra-field'));c.config['force']=True;c.root_error='model_shape'
    c=keep(Case('capture-repeated-epoch'));c.add('journal_flush',fault='none').capture().capture(error='model_capture_epoch',epoch=1)
    c=keep(Case('capture-incomplete-resource-set'));c.add('capture',error='model_capture_scope',observer_id='fake:observer',capture_epoch='1',resources=c.rows[:-1])
    c=keep(Case('capture-out-of-order'));c.add('capture',error='model_capture_mismatch',observer_id='fake:observer',capture_epoch='1',resources=list(reversed(c.rows)))
    c=keep(Case('capture-invents-resource-state'));rows=copy.deepcopy(c.rows);rows[-1]['state_digest']=h('wrong');c.add('capture',error='model_capture_mismatch',observer_id='fake:observer',capture_epoch='1',resources=rows)
    c=keep(Case('resource-change-bad-identifier'));c.add('change_resource',error='model_resource',resource='r.absent',identity_digest=h('other'),state_digest=h('other'),epoch='1',available=True)
    c=keep(Case('crash-fate-error-is-atomic'));c.start().add('dispatch').add('crash',error='model_crash_resources',prefix_entries='5',persist_after=['r.target','r.zzabsent'],torn_tail=False);c.final=dict(resource_writes='0',effect_certainty='in_flight')
    for key,value in [('identity_digest',h('new-target')),('epoch','4'),('available',False)]:
        c=keep(Case('late-result-does-not-write-replacement-'+key));c.start().add('dispatch').change('r.target',**{key:value}).add('effect_result',dict(diagnostic='model_effect_target_changed',operation_status='unresolved',resource_writes='0',effect_certainty='uncertain'),outcome='after');c.final=dict(resource_writes='0',completed_steps='0',retirement_eligible=False)
    p=fixture()
    for index in range(27):
        r=resource('r.scratch'+str(index).zfill(2),'scratch','read',4096,'fd.scratch'+str(index).zfill(2));p['resources'].append(r)
        p['steps'][0]['effects'].append(dict(resource=r['id'],access='read',begin='0',end='1024',before_digest=r['state_digest'],after_digest=r['state_digest']))
    p['resources'].sort(key=lambda r:r['id']);p['steps'][0]['effects'].sort(key=lambda e:e['resource'])
    for r in p['resources']:r['aliases']=sorted([r['identity']]+[r['identity']+':alias'+str(i).zfill(2) for i in range(15)])
    for r in p['resources']:
        for index,alias in enumerate(r['aliases']):
            if alias==r['identity']:continue
            padding=min(128-len(alias),65536-len(canonical(p)));r['aliases'][index]+='x'*padding
    assert len(canonical(p))==65536
    c=keep(Case('maximum-plan-payload-wrapped-history',p));c.start().complete().add('crash',prefix_entries='6',persist_after=[],torn_tail=False).recovery_capture().reconcile('before');c.final=dict(completed_steps='1',dispatches='1',operation_status='unresolved')
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--probe',type=Path,required=True);ap.add_argument('--root',type=Path,default=Path('.'));ap.add_argument('--evidence',type=Path)
    a=ap.parse_args();suite=cases();profile=json.loads((a.root/'spec/catalog/guarded-journal-prototype.json').read_bytes())
    assert set(CONFIG)==set(profile['configuration_fields']) and profile['max_actions']==1024 and profile['max_entries']==512 and profile['max_attempts']==profile['max_generations']==4 and profile['max_journal_bytes']==1048576
    assert not any(profile[k] for k in ('authenticates','authorizes_effects','physical_durability_qualified'))
    assert profile['max_event_bytes']==131072 and profile['max_action_bytes']==65536
    for c in suite:
        for i,action in enumerate(c.actions):
            if c.root_error or c.checks[i]['error'] in ('model_shape','model_action_unknown'):continue
            assert set(action)==set(profile['common_action_fields']+profile['action_fields'][action['op']])
    encoded=b''.join(canonical(c.request())+b'\n' for c in suite);p=subprocess.run([str(a.probe.resolve())],input=encoded,capture_output=True,timeout=90)
    assert p.returncode==0 and not p.stderr,(p.returncode,p.stderr);lines=p.stdout.splitlines();assert len(lines)==len(suite)
    failed=[];observations=[]
    for c,line in zip(suite,lines):
        result=json.loads(line);errors=[]
        if c.root_error:
            if result.get('error')!=c.root_error:errors.append('root:'+repr(result))
        elif 'error' in result:errors.append('root:'+result['error'])
        else:
            if len(result['results'])!=len(c.actions):errors.append('action-count')
            previous=result['initial']
            for i,(action,check,row) in enumerate(zip(c.actions,c.checks,result['results'])):
                snapshot=row['snapshot'];code=check['error']
                if (code is None and not row['accepted']) or (code is not None and (row['accepted'] or row['error']!=code or snapshot!=previous)) or not matches(snapshot,check['expect']) or not invariant(snapshot):errors.append(dict(index=i,op=action['op'],error=row['error'],expected=check,snapshot=snapshot))
                if action['op'] not in ('effect_result','crash','change_resource') and [(x['resource'],x['state_digest']) for x in snapshot['resources']]!=[(x['resource'],x['state_digest']) for x in previous['resources']]:errors.append('state-changed-without-effect-or-fixture-event')
                previous=snapshot
            if not matches(result['final'],c.final):errors.append(dict(final_expected=c.final,final=result['final']))
            try:frame_history(result,c.plan)
            except (AssertionError,KeyError,TypeError):errors.append('history-chain-or-seal')
        observations.append(dict(name=c.name,passed=not errors,actions=len(c.actions),input_sha256=sha(canonical(c.request())),output_sha256=sha(line),refusals=sum(x['error'] is not None for x in c.checks)))
        if errors:failed.append(dict(name=c.name,errors=errors[:4]))
    evidence=dict(scope='closed-fake-memory-guarded-journal-model',cases=len(suite),actions=sum(len(c.actions) for c in suite),passed=not failed,physical_durability_qualified=False,authenticated=False,authorizes_effects=False,file_io=False,observations=observations)
    if a.evidence:a.evidence.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8',newline='\n')
    assert not failed,json.dumps(failed[:8],indent=2)
    print(str(len(suite))+' guarded fake-memory scenarios passed ('+str(evidence['actions'])+' actions); no physical durability or writer admission')

if __name__=='__main__':main()
