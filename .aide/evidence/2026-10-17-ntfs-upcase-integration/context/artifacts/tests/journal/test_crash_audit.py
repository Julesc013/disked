"""Repeated-crash proof dependencies in the private closed journal model.

Expected resource fates, record cuts and forbidden admissions are chosen before
native evaluation. Model histories are encoded independently and never authorize
real storage effects, worker liveness, physical durability or retirement.
"""
import argparse,copy,json,subprocess
from pathlib import Path
from test_guarded import Case,frame_history,invariant,matches
from test_definitions import canonical,h
from test_producer import projection

def crash(c,prefix,state=None,context=None,**expected):
    c.add('crash',dict(operation_status='unresolved',retirement_eligible=False,**expected),prefix_entries=str(prefix),persist_after=[],torn_tail=False)
    if state is not None:next(r for r in c.rows if r['resource']=='r.target')['state_digest']=state
    if context is not None:c.context.update(context)
    return c

def finish(c,step=0):
    c.replace().add('journal_flush',fault='none').capture().add('intention',step_id=c.plan['steps'][step]['id'],fault='none').add('journal_flush',fault='none').complete(step)
    if step==0:c.capture().add('intention',step_id='s.write2',fault='none').add('journal_flush',fault='none').complete(1)
    return c.add('worker_exit').add('seal',fault='none').add('journal_flush',fault='none')

def cut_cases(traces):
    """Ledger coordinates and resource fates come from specified action semantics.

    No native snapshot chooses a prefix, expected state or permission. All cuts
    of successful recovery/cancellation/fork traces are considered, with both
    complete volatile fates, partial next records and dispatched unflushed writes.
    """
    out=[]
    for trace in traces:
        frames=[dict(kind=i,step='',context=trace.receipts[2]) for i in range(1,5)];stable=0;actual=durable=trace.plan['resources'][-1]['state_digest'];active=0;dispatched=False;pending=False
        for cut in range(len(trace.actions)+1):
            if cut:
                action=trace.actions[cut-1];op=action['op']
                if op=='intention':active=0 if action['step_id']=='s.write1' else 1;pending=True;dispatched=False
                if op=='dispatch':dispatched=True
                if op=='effect_result' and action['outcome']=='after':actual=trace.plan['steps'][active]['effects'][0]['after_digest']
                if op in ('target_flush','recovery_flush'):durable=actual
                if op in ('intention','completion','cancel_request','reconcile','replace','seal'):
                    kind=dict(intention=5,completion=6,cancel_request=7,reconcile=8,replace=4,seal=9)[op]
                    context={k:action[k] for k in ('operation_id','attempt_id','worker_identity','worker_epoch')}
                    if op=='replace':context.update(attempt_id=action['new_attempt_id'],worker_identity=action['new_worker_identity'],worker_epoch=action['new_worker_epoch']);pending=False;dispatched=False
                    frames.append(dict(kind=kind,step=action.get('step_id',trace.plan['steps'][active]['id']),context=context,observed=action.get('observed','')))
                if op=='journal_flush':
                    stable=len(frames)
                    if frames[-1]['kind'] in (6,8,4):pending=False
                if op=='crash':
                    frames=frames[:int(action['prefix_entries'])];stable=len(frames);actual=durable;pending=False;dispatched=False
                if op=='fork_journal':
                    frames=frames[:stable]
                    if frames[-1]['kind']==9:frames.pop()
                    stable=0
            for prefix in sorted({stable,len(frames)}):
                for tail in (False,True) if prefix<len(frames) else (False,):
                    for persists in (False,True) if pending and dispatched and actual!=durable else (False,):
                        c=Case(trace.name+':cut'+str(cut)+':prefix'+str(prefix)+':tail'+str(tail)+':after'+str(persists),trace.plan)
                        c.actions=copy.deepcopy(trace.actions[:cut]);c.checks=copy.deepcopy(trace.checks[:cut]);c.epoch=max([int(x['capture_epoch']) for x in c.actions if x['op']=='capture'] or [0])
                        for action in c.actions:
                            if action['op']=='replace':c.context.update(attempt_id=action['new_attempt_id'],worker_identity=action['new_worker_identity'],worker_epoch=action['new_worker_epoch'])
                        state=actual if persists else durable;next(r for r in c.rows if r['resource']=='r.target')['state_digest']=state
                        c.add('crash',dict(operation_status='unresolved',retirement_eligible=False),prefix_entries=str(prefix),persist_after=['r.target'] if persists else [],torn_tail=tail)
                        if prefix<4:
                            c.final=dict(recovery_status='unbound',retirement_eligible=False);out.append(c);continue
                        done=set();intended=False;restored=trace.receipts[2]
                        for frame in frames[:prefix]:
                            if frame['kind']==4:restored=frame['context'];intended=False
                            if frame['kind']==5:intended=True
                            if frame['kind']==6 or frame['kind']==8 and frame['observed']=='after':done.add(frame['step']);intended=False
                        c.context={k:restored[k] for k in ('operation_id','attempt_id','worker_identity','worker_epoch')}
                        c.checks[-1]['expect'].update(completed_steps=str(len(done)),stable_intention=intended,attempt_id=c.context['attempt_id'],worker_epoch=c.context['worker_epoch'])
                        c.recovery_capture()
                        if tail or frames[prefix-1]['kind']==9:c.add('fork_journal').add('journal_flush',fault='none')
                        step=0 if 's.write1' not in done else 1
                        observed='terminal' if len(done)==2 else 'after' if state==trace.plan['steps'][step]['effects'][0]['after_digest'] else 'before'
                        c.reconcile(observed);c.final=dict(operation_status='active' if observed=='after' else 'ready_to_seal' if observed=='terminal' else 'unresolved',completed_steps=str(len(done)+(observed=='after')),dispatches=str(sum(x['op']=='dispatch' for x in c.actions)),retirement_eligible=False)
                        out.append(c)
    return out

def cases():
    out=[]
    c=Case('repeated-crash-after-before-reconciliation');c.start().add('dispatch').add('worker_exit').recovery_capture().reconcile('before')
    crash(c,6).recovery_capture().reconcile('before');finish(c);c.final=dict(operation_status='completed',completed_steps='2',dispatches='3');out.append(c)
    c=Case('repeated-crash-after-after-reconciliation');c.start().add('dispatch').result().add('worker_exit').recovery_capture().reconcile('after')
    crash(c,6).recovery_capture().reconcile('before');finish(c,1);c.final=dict(operation_status='completed',completed_steps='2',dispatches='2');out.append(c)
    c=Case('repeated-crash-cancellation-before-reconciliation');c.start().add('dispatch').add('cancel_request',fault='none').add('journal_flush',fault='none').add('worker_exit').recovery_capture().reconcile('before')
    crash(c,7).recovery_capture().reconcile('before').add('cancel_checkpoint').add('seal',fault='none').add('journal_flush',fault='none');c.final=dict(operation_status='cancelled',completed_steps='0',dispatches='1');out.append(c)
    c=Case('repeated-crash-after-seal-fork-and-terminal-reconciliation');c.start().complete().capture().add('intention',step_id='s.write2',fault='none').add('journal_flush',fault='none').complete(1).add('worker_exit').add('seal',fault='none').add('journal_flush',fault='none')
    crash(c,9).recovery_capture().add('fork_journal').add('journal_flush',fault='none').reconcile('terminal')
    crash(c,9).recovery_capture().reconcile('terminal').add('seal',fault='none').add('journal_flush',fault='none');c.final=dict(operation_status='completed',completed_steps='2',dispatches='2');out.append(c)
    c=Case('crash-stable-new-attempt-has-no-inherited-intention');c.start().add('dispatch').add('worker_exit').recovery_capture().reconcile('before').replace().add('journal_flush',fault='none')
    crash(c,7).capture().change('r.target',state_digest=c.plan['steps'][0]['effects'][0]['after_digest']).recovery_capture().add('reconcile',error='model_recovery_intention',observed='after',capture_epoch=str(c.epoch),fault='none')
    c.final=dict(operation_status='unresolved',completed_steps='0',dispatches='1',stable_intention=False);out.append(c)
    matrix=cut_cases(out[:4])
    for fault in ('before','torn'):
        for survive in (False,True) if fault=='torn' else (False,):
            c=Case('repeated-recovery-append-'+fault+':tail'+str(survive));c.start().add('dispatch').add('worker_exit').recovery_capture().reconcile('before')
            crash(c,6).recovery_capture().add('reconcile',observed='before',capture_epoch=str(c.epoch),fault=fault)
            c.add('crash',dict(operation_status='unresolved'),prefix_entries='6',persist_after=[],torn_tail=survive).recovery_capture()
            if survive:c.add('fork_journal').add('journal_flush',fault='none')
            c.reconcile('before');finish(c);c.final=dict(operation_status='completed',dispatches='3',completed_steps='2');out.append(c)
            c=Case('crash-after-checkpoint-append-'+fault+':tail'+str(survive));c.start().add('dispatch').add('worker_exit').recovery_capture().reconcile('before')
            original=copy.deepcopy(c.context);c.replace();c.actions[-1]['fault']=fault
            c.add('crash',dict(operation_status='unresolved',attempt_id=original['attempt_id'],worker_epoch=original['worker_epoch'],stable_intention=True),prefix_entries='6',persist_after=[],torn_tail=survive);c.context=original
            c.recovery_capture()
            if survive:c.add('fork_journal').add('journal_flush',fault='none')
            c.reconcile('before').replace(error='model_attempt_limit_or_reuse').replace(new_id='fake:attempt3',new_worker='fake:worker3',epoch='9').add('journal_flush',fault='none').capture().add('intention',step_id='s.write1',fault='none').add('journal_flush',fault='none').complete().capture().add('intention',step_id='s.write2',fault='none').add('journal_flush',fault='none').complete(1).add('worker_exit').add('seal',fault='none').add('journal_flush',fault='none')
            c.final=dict(operation_status='completed',dispatches='3',completed_steps='2');out.append(c)
    for fault in ('error','unqualified'):
        c=Case('repeated-recovery-flush-'+fault);c.start().add('dispatch').add('worker_exit').recovery_capture().reconcile('before')
        crash(c,6).capture().add('recovery_flush',dict(operation_status='unresolved'),fault=fault).capture().add('reconcile',error='model_recovery_capture',observed='before',capture_epoch=str(c.epoch),fault='none');c.final=dict(completed_steps='0',dispatches='1',retirement_eligible=False);out.append(c)
        c=Case('checkpoint-journal-flush-'+fault);c.start().add('dispatch').add('worker_exit').recovery_capture().reconcile('before').replace().add('journal_flush',dict(operation_status='unresolved'),fault=fault)
        original={k:c.receipts[2][k] for k in c.context};crash(c,6,context=original).recovery_capture().reconcile('before');c.final=dict(completed_steps='0',dispatches='1',retirement_eligible=False);out.append(c)
    for name in ('r.target','r.code','r.provider','r.backup','r.journal'):
        for key in ('identity_digest','epoch','available','state_digest'):
            c=Case('repeated-crash-resource-'+name+':'+key);c.start().add('dispatch').add('worker_exit').recovery_capture().reconcile('before');crash(c,6)
            c.change(name,**{key:False if key=='available' else '4' if key=='epoch' else h('changed:'+name+':'+key)})
            error='model_resource_unavailable' if key=='available' else 'model_identity_mismatch' if key in ('identity_digest','epoch') else 'model_dependency_mismatch' if name!='r.target' else None
            c.capture(error=error)
            if error is None:c.add('recovery_flush',fault='none').capture().add('reconcile',error='model_recovery_state',observed='before',capture_epoch=str(c.epoch),fault='none').add('reconcile',error='model_recovery_state',observed='after',capture_epoch=str(c.epoch),fault='none')
            c.final=dict(completed_steps='0',dispatches='1',retirement_eligible=False);out.append(c)
    return out+matrix

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--probe',type=Path,required=True);ap.add_argument('--root',type=Path,default=Path('.'));ap.add_argument('--evidence',type=Path)
    a=ap.parse_args();suite=cases();p=subprocess.run([str(a.probe.resolve())],input=b''.join(canonical(c.request())+b'\n' for c in suite),capture_output=True,timeout=90)
    assert p.returncode==0 and not p.stderr;lines=p.stdout.splitlines();assert len(lines)==len(suite);observations=[];failed=[];generations=0
    for c,line in zip(suite,lines):
        out=json.loads(line);errors=[]
        if 'error' in out:errors.append('root:'+out['error'])
        else:
            assert len(out['results'])==len(c.actions)
            previous=out['initial']
            for index,(result,check) in enumerate(zip(out['results'],c.checks)):
                if result['accepted']!=(check['error'] is None) or result['error']!=(check['error'] or '') or not matches(result['snapshot'],check['expect']) or not invariant(result['snapshot']):errors.append(dict(action=index,op=c.actions[index]['op'],expected=check,actual_error=result['error'],actual_snapshot={k:result['snapshot'].get(k) for k in check['expect']}))
                if not result['accepted'] and result['snapshot']!=previous:errors.append('rejected-action-mutated-state:'+str(index))
                previous=result['snapshot']
            if not matches(out['final'],c.final):errors.append(dict(final_expected=c.final,final_actual={k:out['final'].get(k) for k in c.final}))
            try:
                frame_history(out,c.plan)
                for raw,produced in zip(out['history'],out['binary_history']):
                    generations+=1;expected,stable,*_=projection(c.plan,raw);assert bytes.fromhex(produced['bytes'])==expected and produced['stable_bytes']==str(stable)
                    if produced['disposition']!=('torn_tail' if raw['tail'] else 'valid_prefix'):errors.append(dict(binary_diagnostic=produced['semantic_diagnostic'] or produced['diagnostic'],accepted_records=produced['records'],retained_records=len(raw['events'])))
                    pr=produced['projection'];assert not any(pr[k] for k in ('authenticated','authorizes_effects','qualifies_durability','replay_authorized','retirement_authorized')) and pr['requires_live_reconciliation']
            except (AssertionError,KeyError,TypeError) as error:errors.append(str(error))
        row=dict(name=c.name,passed=not errors,errors=errors);observations.append(row)
        if errors:failed.append(row)
    evidence=dict(passed=not failed,cases=len(suite),actions=sum(len(c.actions) for c in suite),generations=generations,observations=observations,file_io=False,authorizes_effects=False,qualifies_durability=False)
    if a.evidence:a.evidence.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8',newline='\n')
    assert not failed,json.dumps(failed[:12],indent=2)
    print(f'{len(suite)} repeated-crash scenarios / {evidence["actions"]} actions / {generations} binary generations passed; fake declarations only')
if __name__=='__main__':main()
