"""Independent canonical bytes, resource/recovery and receipt-binding fixtures.

Only fake declarations cross the probe. No file/target/authority/effect ports.
Expected digests use Python's JSON encoder and hashlib, not native output.
"""
import argparse, copy, hashlib, json, subprocess
from pathlib import Path

MAX=18446744073709551615
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
def sha(v):return 'sha256:'+hashlib.sha256(v).hexdigest()
def h(v):return sha(v.encode('ascii'))
def resource(name,purpose,access,end,domain):
    return dict(id=name,identity='fake:'+name,identity_digest=h('identity:'+name),state_digest=h('initial:'+name),epoch='3',
                purpose=purpose,access=access,begin='0',end=str(end),aliases=['fake:'+name],failure_domains=[domain],
                verification='readback-sha256',persistent=True)
def fixture():
    resources=[resource('r.backup','backup','read',4096,'fd.backup'),resource('r.code','executable','read',0,'fd.code'),
               resource('r.journal','journal','write',65536,'fd.journal'),resource('r.provider','provider','read',0,'fd.code'),
               resource('r.target','target','write',4096,'fd.target')]
    recovery=dict(replayable=True,resumable=True,rollback_before_boundary=True,rollback_after_boundary=False,
                  external_backup_required=True,cancellable_at_checkpoint=True,irreversible_after=True,
                  forensic_best_effort=False,reconstruction_resources=['r.backup'])
    steps=[]
    for i in (1,2):
        steps.append(dict(id='s.write'+str(i),operation='fake.range-transition',provider='r.provider',executor='r.code',
            depends_on=[] if i==1 else ['s.write1'],preconditions_digest=h('pre'+str(i)),postconditions_digest=h('post'+str(i)),
            effects=[dict(resource='r.target',access='write',begin=str((i-1)*1024),end=str(i*1024),
                          before_digest=resources[-1]['state_digest'] if i==1 else h('after1'),after_digest=h('after'+str(i)))],
            recovery=copy.deepcopy(recovery)))
    steps[1]['recovery'].update(replayable=False,rollback_before_boundary=False,external_backup_required=False,
        cancellable_at_checkpoint=False,irreversible_after=False,forensic_best_effort=True,reconstruction_resources=[])
    return dict(schema='org.disked.plan-definition-prototype/1',id='plan.fixture',basis_digest=h('basis'),policy_digest=h('policy'),
                environment='fake-model',required_acknowledgements=['ack.loss'],journal_resource='r.journal',resources=resources,steps=steps)
def digests(plan):
    providers=[r for r in plan['resources'] if r['purpose'] in ('provider','executable')]
    return dict(digest=sha(canonical(plan)),resources_digest=sha(b'DiskEd.plan.resources/1\n'+canonical(plan['resources'])),
                providers_digest=sha(b'DiskEd.plan.providers/1\n'+canonical(providers)))
def maximum_payload_fixture():
    p=fixture()
    for index in range(27):
        r=resource('r.scratch'+str(index).zfill(2),'scratch','read',4096,'fd.scratch'+str(index).zfill(2));p['resources'].append(r)
        p['steps'][0]['effects'].append(dict(resource=r['id'],access='read',begin='0',end='1024',before_digest=r['state_digest'],after_digest=r['state_digest']))
    p['resources'].sort(key=lambda r:r['id']);p['steps'][0]['effects'].sort(key=lambda e:e['resource'])
    for r in p['resources']:r['aliases']=sorted([r['identity']]+[r['identity']+':alias'+str(i).zfill(2) for i in range(15)])
    for r in p['resources']:
        for index,alias in enumerate(r['aliases']):
            if alias!=r['identity']:r['aliases'][index]+='x'*min(128-len(alias),65536-len(canonical(p)))
    assert len(canonical(p))==65536
    return p
def receipt(plan,name,kind,**extra):
    return dict(schema='org.disked.plan-receipt-prototype/1',id=name,kind=kind,plan_digest=digests(plan)['digest'],
                issuer='fixture.reviewer',evidence_digest=h('evidence:'+name),**extra)
def ledger(plan):
    steps=[s['id'] for s in plan['steps']]
    review=receipt(plan,'receipt.review','review',step_ids=steps,decision='reviewed')
    grant=receipt(plan,'receipt.grant','grant',step_ids=steps,acknowledgements=plan['required_acknowledgements'],host_effects=True,
                  permissions=[dict(resource=r['id'],access='write' if r['purpose'] in ('target','journal') else 'read') for r in plan['resources']])
    admission=receipt(plan,'receipt.admission','admission',step_ids=steps,operation_id='fake:operation1',attempt_id='fake:attempt1',
        worker_identity='fake:worker1',worker_epoch='7',review_id=review['id'],grant_id=grant['id'],policy_digest=plan['policy_digest'],
        provider_closure_digest=digests(plan)['providers_digest'],observations=[{k:r[k] for k in ('epoch','identity_digest','state_digest')} | dict(resource=r['id']) for r in plan['resources']])
    events=[receipt(plan,'receipt.execution'+str(i),'execution',operation_id=admission['operation_id'],attempt_id=admission['attempt_id'],
                   worker_identity=admission['worker_identity'],worker_epoch=admission['worker_epoch'],admission_id=admission['id'],sequence=str(i),
                   step_id='s.write1',event=event,observation_digest=plan['steps'][0][key])
            for i,event,key in [(1,'intention','preconditions_digest'),(2,'verified_completion','postconditions_digest')]]
    return [review,grant,admission]+events

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--probe',type=Path,required=True);ap.add_argument('--root',type=Path,default=Path('.'));ap.add_argument('--evidence',type=Path)
    a=ap.parse_args();plan=fixture();base=ledger(plan);requests=[];checks=[];names=[]
    def add(name,p,records=None,check=None,**extra):
        names.append(name);requests.append(copy.deepcopy(dict(plan=p,receipts=[] if records is None else records,**extra)));checks.append(check or good(p,records or []))
    def good(p,records):
        expected=digests(p);payload=canonical(p).decode();receipts=[dict(payload=canonical(r).decode(),digest=sha(canonical(r))) for r in records]
        matched=[dict(id=r['id'],kind=r['kind'],digest=sha(canonical(r))) for i,r in enumerate(records) if r['id'] not in {x['id'] for x in records[:i]}]
        return lambda v:all(v.get(k)==value for k,value in expected.items()) and v.get('payload')==payload and v.get('receipt_payloads')==receipts and v.get('caller_input_immutable') is True and v.get('file_io') is False and v.get('inspection')==dict(scope='private-fake-definition-receipt-binding',matches_declared_bindings=True,authenticated=False,authorizes_effects=False,validates_durability=False,receipts=matched)
    def bad(code,witness=None):return lambda v:v.get('error')==code and (witness is None or v.get('witness')==witness)
    def change_plan(name,edit,code):
        p=copy.deepcopy(plan);edit(p);add(name,p,check=bad(code))
    def change_receipt(name,index,edit,code):
        r=copy.deepcopy(base);edit(r[index]);add(name,plan,r,check=bad(code))
    add('canonical-plan-and-ledger',plan,base,freeze=True)
    expected_summary=dict(all_replayable=False,all_resumable=True,all_rollback_before_boundary=False,all_rollback_after_boundary=False,
        any_external_backup_required=True,any_irreversible_after=True,any_forensic_best_effort=True,cancellation_checkpoints=['s.write1'],qualifies_recovery=False)
    add('independent-recovery-properties',plan,check=lambda v:good(plan,[])(v) and v.get('recovery_summary')==expected_summary)
    p=copy.deepcopy(plan);p['id']='p'*128;add('maximum-identifier',p)
    for path in [('resources',0),('steps',0),('steps',0,'effects',0),('steps',0,'recovery')]:
        p=copy.deepcopy(plan);row=p
        for key in path:row=row[key]
        row['unknown']=True;add('strict-nested-fields-'+str(path),p,check=bad('definition_shape'))
    for key in ('status','acknowledgements','digest','progress'):change_plan('mutable-plan-field-'+key,lambda p,k=key:p.update({k:'proposed'}),'definition_shape')
    for key in ('id','basis_digest','policy_digest','required_acknowledgements'):
        p=copy.deepcopy(plan);p[key]=['ack.loss','ack.new'] if key=='required_acknowledgements' else h('changed') if 'digest' in key else 'plan.changed'
        add('bound-root-'+key,p);add('stale-receipt-root-'+key,p,[base[0]],bad('receipt_plan_mismatch'))
    for i in range(len(plan['resources'])):
        for key in ('epoch','identity_digest','state_digest','failure_domains','verification'):
            p=copy.deepcopy(plan);r=p['resources'][i]
            r[key]='4' if key=='epoch' else h('changed') if 'digest' in key else ['fd.changed'] if key=='failure_domains' else 'independent-postcondition'
            if key=='state_digest' and i==4:p['steps'][0]['effects'][0]['before_digest']=r[key]
            add('bound-resource-'+str(i)+'-'+key,p);add('stale-receipt-resource-'+str(i)+'-'+key,p,[base[0]],bad('receipt_plan_mismatch'))
    for key in ('preconditions_digest','postconditions_digest'):
        p=copy.deepcopy(plan);p['steps'][0][key]=h('changed');add('bound-step-'+key,p);add('stale-receipt-step-'+key,p,[base[0]],bad('receipt_plan_mismatch'))
    for field in ('id','identity'):
        for value in ('','x'*129,'bad name','bad\x1bname','é'):
            change_plan('identifier-'+field+'-'+repr(value),lambda p,k=field,v=value:p['resources'][0].update({k:v}),'definition_identifier')
    change_plan('nonfake-identity',lambda p:p['resources'][0].update(identity='real:r.backup'),'definition_fake_identity')
    for value in ('sha256:'+'0'*64,'sha256:'+'A'*64,'sha256:12',None):
        change_plan('digest-'+repr(value),lambda p,v=value:p.update(basis_digest=v),'definition_string' if value is None else 'definition_digest')
    for key in ('epoch','begin','end'):
        for value in ('01','-1',str(MAX+1),'1.0',1,None):
            change_plan('u64-'+key+'-'+repr(value),lambda p,k=key,v=value:p['resources'][0].update({k:v}),'definition_string' if not isinstance(value,str) else 'definition_integer')
    p=copy.deepcopy(plan);p['resources'][0]['epoch']=str(MAX);add('max-resource-epoch',p)
    change_plan('zero-epoch',lambda p:p['resources'][0].update(epoch='0'),'definition_integer')
    change_plan('reversed-resource-range',lambda p:p['resources'][4].update(begin='4097'),'definition_footprint')
    change_plan('empty-write-resource',lambda p:p['resources'][4].update(end='0'),'definition_footprint')
    change_plan('resource-order',lambda p:p['resources'].reverse(),'definition_set_order')
    change_plan('step-order',lambda p:p['steps'].reverse(),'definition_set_order')
    change_plan('ack-duplicate',lambda p:p.update(required_acknowledgements=['ack.loss','ack.loss']),'definition_set_order')
    change_plan('identity-not-an-alias',lambda p:p['resources'][0].update(aliases=['fake:other']),'definition_identity_alias')
    change_plan('shared-alias',lambda p:p['resources'][1].update(aliases=['fake:r.backup','fake:r.code']),'definition_aliased_resources')
    change_plan('alias-order',lambda p:p['resources'][0].update(aliases=['fake:z','fake:r.backup']),'definition_set_order')
    p=copy.deepcopy(plan);p['resources'][0]['aliases']=sorted(['fake:r.backup']+['fake:alias.%02d'%i for i in range(15)]);add('maximum-aliases',p)
    q=copy.deepcopy(p);q['resources'][0]['aliases']=sorted(q['resources'][0]['aliases']+['fake:alias.15']);add('aliases-over-limit',q,check=bad('definition_array_limit'))
    p=copy.deepcopy(plan);p['resources'][0]['failure_domains']=sorted(['fd.backup']+['fd.other.%02d'%i for i in range(7)]);add('maximum-failure-domains',p)
    q=copy.deepcopy(p);q['resources'][0]['failure_domains']=sorted(q['resources'][0]['failure_domains']+['fd.other.07']);add('failure-domains-over-limit',q,check=bad('definition_array_limit'))
    p=copy.deepcopy(plan);p['required_acknowledgements']=['ack.%02d'%i for i in range(16)];add('maximum-acknowledgements',p,ledger(p))
    q=copy.deepcopy(p);q['required_acknowledgements'].append('ack.16');add('acknowledgements-over-limit',q,check=bad('definition_array_limit'))
    for name,key in [('dependency','depends_on'),('effect','effects')]:
        p=copy.deepcopy(plan);p['steps'][0][key]=['s.%02d'%i for i in range(33)] if key=='depends_on' else [copy.deepcopy(plan['steps'][0]['effects'][0]) for i in range(33)]
        add(name+'-collection-over-limit',p,check=bad('definition_array_limit'))
    p=copy.deepcopy(plan);p['steps'][0]['recovery']['reconstruction_resources']=['r.%02d'%i for i in range(33)];add('reconstruction-over-limit',p,check=bad('definition_array_limit'))
    for key in ('resources','steps'):change_plan('empty-'+key,lambda p,k=key:p.update({k:[]}),'definition_array_limit')
    change_plan('unused-resource',lambda p:p['resources'].insert(0,resource('r.a','scratch','read',4096,'fd.a')),'definition_unused_resource')
    change_plan('missing-journal',lambda p:p.update(journal_resource='r.missing'),'definition_resource_reference')
    for key,value in [('purpose','target'),('persistent',False),('access','read')]:change_plan('journal-dependency-'+key,lambda p,k=key,v=value:p['resources'][2].update({k:v}),'definition_journal_dependency')
    for key,value in [('purpose','backup'),('persistent',False),('access','observe')]:change_plan('code-dependency-'+key,lambda p,k=key,v=value:p['resources'][1].update({k:v}),'definition_code_dependency')
    for key,value,code in [('resource','r.missing','definition_resource_reference'),('resource','r.journal','definition_effect_role'),('end','4097','definition_effect_footprint'),('begin','1024','definition_effect_footprint'),('after_digest',h('wrong'),'definition_intermediate_state')]:
        change_plan('effect-'+key+'-'+value,lambda p,k=key,v=value:p['steps'][0]['effects'][0].update({k:v}),code)
    change_plan('wrong-initial-state',lambda p:p['steps'][0]['effects'][0].update(before_digest=h('wrong')),'definition_intermediate_state')
    change_plan('empty-effect-set',lambda p:p['steps'][0].update(effects=[]),'definition_array_limit')
    change_plan('duplicate-effect-resource',lambda p:p['steps'][0]['effects'].append(copy.deepcopy(p['steps'][0]['effects'][0])),'definition_set_order')
    change_plan('write-through-read-binding',lambda p:p['resources'][4].update(access='read'),'definition_effect_footprint')
    p=copy.deepcopy(plan);r=resource('r.scratch','scratch','read',MAX,'fd.scratch');p['resources'].insert(4,r)
    p['steps'][0]['effects'].insert(0,dict(resource=r['id'],access='read',begin=str(MAX-1),end=str(MAX),before_digest=r['state_digest'],after_digest=r['state_digest']));add('max-footprint-read',p)
    q=copy.deepcopy(p);q['steps'][0]['effects'][0]['after_digest']=h('wrong');add('read-changing-state',q,check=bad('definition_read_effect'))
    q=copy.deepcopy(p);q['steps'][0]['effects'][0].update(access='observe',begin=str(MAX),end=str(MAX));add('empty-observation-footprint',q)
    q=copy.deepcopy(p);q['steps'][0]['effects'][0]['access']='observe';add('nonempty-observation-footprint',q,check=bad('definition_effect_footprint'))
    change_plan('missing-step',lambda p:p['steps'][1].update(depends_on=['s.absent']),'definition_step_reference')
    change_plan('unordered-writes',lambda p:p['steps'][1].update(depends_on=[]),'definition_unordered_effects')
    p=copy.deepcopy(plan);p['steps'][0]['depends_on']=['s.write2'];add('cycle-witness',p,check=bad('definition_dependency_cycle',['s.write1','s.write2','s.write1']))
    p=copy.deepcopy(plan);p['steps'][0]['depends_on']=['s.write1'];add('self-cycle',p,check=bad('definition_dependency_cycle',['s.write1','s.write1']))
    change_plan('rollback-and-irreversible',lambda p:p['steps'][0]['recovery'].update(rollback_after_boundary=True),'definition_recovery_contradiction')
    change_plan('missing-reconstruction',lambda p:p['steps'][0]['recovery'].update(reconstruction_resources=[]),'definition_reconstruction_required')
    for key,value in [('verification','identity-epoch'),('persistent',False),('access','observe')]:change_plan('backup-'+key,lambda p,k=key,v=value:p['resources'][0].update({k:v}),'definition_backup_dependency')
    for i in range(4):change_plan('dependency-domain-'+str(i),lambda p,i=i:p['resources'][i].update(failure_domains=['fd.target']),'definition_dependency_failure_domain')
    for i in range(5):
        for key in ('plan_digest','issuer'):
            change_receipt('receipt-common-'+str(i)+'-'+key,i,lambda r,k=key:r.update({k:h('other') if k!='issuer' else ''}),'definition_identifier' if key=='issuer' else 'receipt_plan_mismatch')
    for i in range(5):change_receipt('receipt-extra-'+str(i),i,lambda r:r.update(extra=True),'definition_shape')
    for i in range(5):change_receipt('missing-evidence-'+str(i),i,lambda r:r.update(evidence_digest='sha256:'+'0'*64),'definition_digest')
    p=copy.deepcopy(plan);p['steps'][1]['effects'][0]['after_digest']=h('new effect');add('bound-write-effect',p);add('stale-effect-receipt',p,[base[0]],bad('receipt_plan_mismatch'))
    p=copy.deepcopy(plan);p['steps'][1]['recovery']['resumable']=False;add('bound-recovery-trait',p);add('stale-recovery-receipt',p,[base[0]],bad('receipt_plan_mismatch'))
    change_receipt('missing-ack',1,lambda r:r.update(acknowledgements=[]),'receipt_acknowledgements')
    change_receipt('extra-ack',1,lambda r:r.update(acknowledgements=['ack.extra','ack.loss']),'receipt_acknowledgements')
    change_receipt('extra-permission',1,lambda r:r['permissions'][0].update(access='write'),'receipt_permission_scope')
    change_receipt('missing-permission',1,lambda r:r['permissions'].pop(),'receipt_permission_scope')
    for key in ('policy_digest','provider_closure_digest'):change_receipt('admission-'+key,2,lambda r,k=key:r.update({k:h('wrong')}),'receipt_closure_mismatch')
    for key,value in [('epoch','4'),('identity_digest',h('wrong')),('state_digest',h('wrong')),('resource','r.wrong')]:change_receipt('observation-'+key,2,lambda r,k=key,v=value:r['observations'][0].update({k:v}),'receipt_observation_mismatch')
    change_receipt('missing-observation',2,lambda r:r['observations'].pop(),'receipt_observation_scope')
    for index,key in [(1,'permissions'),(2,'observations')]:change_receipt('receipt-collection-over-limit-'+key,index,lambda r,k=key:r.update({k:[copy.deepcopy(r[k][0]) for i in range(33)]}),'definition_array_limit')
    for i in (2,3):
        for value in ('0','01',str(MAX+1)):change_receipt('worker-epoch-'+str(i)+'-'+value,i,lambda r,v=value:r.update(worker_epoch=v),'definition_integer')
    for key in ('operation_id','attempt_id','worker_identity','worker_epoch'):change_receipt('stale-attempt-'+key,3,lambda r,k=key:r.update({k:'8' if k=='worker_epoch' else 'fake:other'}),'receipt_attempt_mismatch')
    for value in ('0','01',str(MAX+1)):change_receipt('sequence-invalid-'+value,3,lambda r,v=value:r.update(sequence=v),'definition_integer')
    for value in ('2',str(MAX)):change_receipt('sequence-gap-'+value,3,lambda r,v=value:r.update(sequence=v),'receipt_sequence')
    change_receipt('second-sequence-gap',4,lambda r:r.update(sequence='3'),'receipt_sequence')
    for i in (3,4):change_receipt('wrong-postpre-'+str(i),i,lambda r:r.update(observation_digest=h('wrong')),'receipt_observation_mismatch')
    change_receipt('unknown-event',3,lambda r:r.update(event='effect_observed'),'definition_enum')
    for event in ('cancellation_request','recovery_observation'):
        r=copy.deepcopy(base[:4]);r[-1].update(event=event,observation_digest=h(event));add('observational-event-'+event,plan,r)
    for key,value,code in [('review_id','absent','receipt_reference'),('grant_id','receipt.review','receipt_reference')]:change_receipt('reference-'+key,2,lambda r,k=key,v=value:r.update({k:v}),code)
    change_receipt('rejected-review',0,lambda r:r.update(decision='rejected'),'receipt_admission_scope')
    change_receipt('no-host-effects',1,lambda r:r.update(host_effects=False),'receipt_admission_scope')
    r=copy.deepcopy(base);r[0]['step_ids']=['s.write1'];add('review-scope-incomplete',plan,r,bad('receipt_admission_scope'))
    r=copy.deepcopy(base);r[1]['step_ids']=['s.write1'];add('grant-step-scope-differs',plan,r,bad('receipt_admission_scope'))
    r=copy.deepcopy(base);r[1]['step_ids']=['s.write1'];r[2]['step_ids']=['s.write1'];r[3]['step_id']='s.write2';r[3]['observation_digest']=plan['steps'][1]['preconditions_digest'];add('execution-outside-admission',plan,r,bad('receipt_execution_scope'))
    # Binding inspection deliberately cannot certify intention/flush/effect order.
    r=copy.deepcopy(base[:3])+[copy.deepcopy(base[4])];r[-1]['sequence']='1';add('completion-declaration-does-not-prove-durability',plan,r)
    r=copy.deepcopy(base);r[2]['worker_epoch']=str(MAX);r[3]['worker_epoch']=str(MAX);r[4]['worker_epoch']=str(MAX);add('max-worker-epoch',plan,r)
    add('forward-reference',plan,[base[2],base[0],base[1]],bad('receipt_reference'))
    add('duplicate-identical-receipts',plan,base+[base[0],base[3]])
    r=copy.deepcopy(base);new=copy.deepcopy(base[0]);new['evidence_digest']=h('later');r.append(new);add('immutable-receipt-identity',plan,r,bad('receipt_identity_reused'))
    r=copy.deepcopy(base);new=copy.deepcopy(base[2]);new['id']='receipt.other';r.append(new);add('attempt-reuse',plan,r,bad('receipt_attempt_reused'))
    r=copy.deepcopy(base);ad=copy.deepcopy(base[2]);ad.update(id='receipt.admission2',attempt_id='fake:attempt2',worker_epoch='8');event=copy.deepcopy(base[3]);event.update(id='receipt.execution3',admission_id=ad['id'],attempt_id=ad['attempt_id'],worker_epoch='8');add('new-attempt-sequence-reset',plan,r+[ad,event])
    r=[receipt(plan,'review.'+str(i),'review',step_ids=['s.write1'],decision='reviewed') for i in range(128)];add('maximum-receipt-count',plan,r);add('receipt-count-over-limit',plan,r+[copy.deepcopy(r[0])],bad('receipt_count_limit'))
    p=copy.deepcopy(plan)
    for i in range(27):
        name='r.scratch%02d'%i;p['resources'].append(resource(name,'scratch','read',16,'fd.scratch'))
        p['steps'][0]['effects'].append(dict(resource=name,access='read',begin='0',end='16',before_digest=h('initial:'+name),after_digest=h('initial:'+name)))
    p['resources'].sort(key=lambda r:r['id']);p['steps'][0]['effects'].sort(key=lambda r:r['resource']);add('maximum-resources',p)
    add('maximum-grant-permissions-and-admission-observations',p,ledger(p))
    q=copy.deepcopy(p);q['resources'].append(resource('r.zz','scratch','read',16,'fd.zz'));add('resource-count-over-limit',q,check=bad('definition_array_limit'))
    p=copy.deepcopy(plan);p['steps']=[]
    for i in range(32):
        s=copy.deepcopy(plan['steps'][0]);s['id']='s.%02d'%i;s['depends_on']=[] if i==0 else ['s.%02d'%(i-1)];s['effects'][0].update(before_digest=plan['resources'][-1]['state_digest'] if i==0 else h('after%02d'%(i-1)),after_digest=h('after%02d'%i));p['steps'].append(s)
    add('maximum-steps',p);q=copy.deepcopy(p);q['steps'].append(copy.deepcopy(q['steps'][-1]));add('step-count-over-limit',q,check=bad('definition_array_limit'))
    # A structurally valid value on the byte limit, plus one byte, tests the
    # stated payload boundary without relying on an unknown-field failure.
    for i in range(27):
        name='r.scratch%02d'%i;p['resources'].append(resource(name,'scratch','read',16,'fd.scratch'))
        p['steps'][0]['effects'].append(dict(resource=name,access='read',begin='0',end='16',before_digest=h('initial:'+name),after_digest=h('initial:'+name)))
    p['resources'].sort(key=lambda r:r['id']);p['steps'][0]['effects'].sort(key=lambda r:r['resource'])
    fillers=[]
    for i,r in enumerate(p['resources']):
        for j in range(15):
            remaining=65536-len(canonical(p))
            if remaining<=131:break
            value='z%02d.%02d.'%(i,j)+'x'*121;r['aliases'].append(value);fillers.append((r,value))
        if 65536-len(canonical(p))<=131:break
    remaining=65536-len(canonical(p))
    if remaining<8:
        owner,value=fillers[-1];owner['aliases'][-1]=value[:-8];remaining+=8
    r=next(r for r in p['resources'] if len(r['aliases'])<16)
    final='zz.'+'x'*(remaining-6);r['aliases'].append(final)
    assert len(canonical(p))==65536 and all(len(s)<=128 for r in p['resources'] for s in r['aliases'])
    add('exact-payload-byte-limit',p);q=copy.deepcopy(p)
    row=next(r for r in q['resources'] if final in r['aliases']);row['aliases'][-1]+='x';add('payload-one-byte-over-limit',q,check=bad('definition_payload_limit'))
    p=copy.deepcopy(plan);p['unexpected']='x'*65536;add('payload-budget',p,check=bad('definition_payload_limit'))
    profile=json.loads((a.root/'spec/catalog/plan-prototype.json').read_bytes())
    assert set(plan)==set(profile['definition_fields']) and set(plan['resources'][0])==set(profile['resource_fields']) and set(plan['steps'][0])==set(profile['step_fields']) and set(plan['steps'][0]['effects'][0])==set(profile['effect_fields']) and set(plan['steps'][0]['recovery'])==set(profile['recovery_fields'])
    assert all(set(r)==set(profile['receipt_base_fields']+profile['receipt_extra_fields'][r['kind']]) for r in base)
    assert profile['max_payload_bytes']==65536 and profile['max_resources']==profile['max_steps']==32 and profile['max_receipts']==128 and not profile['authenticates'] and not profile['authorizes_effects']
    assert profile['max_aliases_per_resource']==16 and profile['max_failure_domains_per_resource']==8 and profile['max_acknowledgements']==16
    assert all(profile[k]==32 for k in ('max_dependencies_per_step','max_effects_per_step','max_reconstruction_resources_per_step','max_permissions_per_grant','max_observations_per_admission'))
    encoded=b''.join(canonical(v)+b'\n' for v in requests);result=subprocess.run([str(a.probe.resolve())],input=encoded,capture_output=True,timeout=90)
    assert result.returncode==0 and not result.stderr,(result.returncode,result.stderr)
    outputs=result.stdout.splitlines();assert len(outputs)==len(requests),(len(outputs),len(requests))
    observations=[];failed=[]
    for name,request,line,check in zip(names,requests,outputs,checks):
        output=json.loads(line)
        try:passed=bool(check(output))
        except (KeyError,TypeError,ValueError):passed=False
        observations.append(dict(name=name,passed=passed,input_sha256=sha(canonical(request)),output_sha256=sha(line),error=output.get('error'),witness=output.get('witness',[])))
        if not passed:failed.append(dict(name=name,error=output.get('error'),output_sha256=sha(line),witness=output.get('witness',[])))
    evidence=dict(scope='private-fake-definition-receipt-binding',cases=len(requests),passed=not failed,file_io=False,
        authenticated=False,authorizes_effects=False,validates_durability=False,observations=observations)
    if a.evidence:a.evidence.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8',newline='\n')
    assert not failed,json.dumps(failed[:8],indent=2)
    print(str(len(requests))+' independent definition/receipt fixtures passed; no authentication, effects or durability qualified')

if __name__=='__main__':main()
