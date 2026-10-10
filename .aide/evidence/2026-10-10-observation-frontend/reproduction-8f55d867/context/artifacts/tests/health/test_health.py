"""Independent native health collection, identity and consent fixtures.

Owned strings/bytes only. No physical observation, self-test or archive execution.
Expected outcomes are specified here before the native reducer is evaluated.
"""
import argparse,copy,hashlib,itertools,json,subprocess
from pathlib import Path

MAX=2**64-1
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
def sha(v):return 'sha256:'+hashlib.sha256(v if isinstance(v,bytes) else canonical(v)).hexdigest()
def fixture():
    return dict(target=dict(id='target:owned@1',generation='17',identity_digest=sha(b'owned composite identity')),
        sources=[dict(id='fake:health.1',provider_digest=sha(b'fake health provider revision'),capability='observe',
            fields=[dict(id=k,sensitivity=c) for k,c in [('temperature','public'),('serial','identifier'),('label','customer'),('debug','secret')]])])
def key(q=None,capture=1,worker=1):return dict(source=(q or fixture())['sources'][0]['id'],capture=str(capture),worker=str(worker))
def response(q=None,capture=1,worker=1):
    q=q or fixture();rows=[]
    for i,f in enumerate(q['sources'][0]['fields']):
        rows.append(dict(id=f['id'],raw=dict(availability='available',hex=(b'\x00\xff' if i==0 else ('OWNED-SENTINEL-'+f['sensitivity']).encode()).hex()),
            interpretation=dict(availability='available',text='35 Celsius' if i==0 else 'OWNED-INTERPRETATION-'+f['sensitivity'],rule_id='fake:vendor-rule-v1')))
    return dict(ticket=key(q,capture,worker),target=copy.deepcopy(q['target']),provider_digest=q['sources'][0]['provider_digest'],outcome='complete',fields=rows)
def start(q=None,alias='a'):return dict(action='start',source=(q or fixture())['sources'][0]['id'],**{'as':alias})
def finish(r=None,k='a'):return dict(action='finish',key=k,response=r or response())
def retire(k='a'):return dict(action='retire',key=k)
def policy(**kw):return dict(identifiers=False,raw_values=False,interpretations=False,customer_data=False,**kw) if not kw else {k:kw.get(k,False) for k in ('identifiers','raw_values','interpretations','customer_data')}
def src(out,index=-1):return out['events'][index]['view']['sources'][0]
def event(out,index=-1):return out['events'][index]
def bad(code):return lambda out:out.get('error')==code
def malformed(code):return lambda out:event(out).get('accepted') is False and src(out)['state']=='malformed' and src(out)['diagnostic']==code and all(not x['received'] for x in src(out)['fields']) and src(out)['worker_outstanding']
def complete(out):return out['final']['state']=='complete' and out['final']['coverage_complete'] and all(f['received'] for f in out['final']['sources'][0]['fields']) and out['final']['claims']==dict(reliability='not_established',mutation_authority=False,physical_admission=False)

def cases():
    cases=[]
    def add(name,actions,check,q=None,**extra):cases.append((name,dict(request=copy.deepcopy(q or fixture()),actions=actions,**extra),check))
    add('no-query-on-construction',[],lambda o:o['queries']=='0' and o['final']['state']=='collecting' and all(not f['received'] and f['raw']['availability']=='unknown' and f['raw']['hex'] is None for f in o['final']['sources'][0]['fields']))
    add('complete-is-not-safe-media',[start(),finish(),retire()],lambda o:complete(o) and o['final']['workers_outstanding']=='0' and src(o)['fields'][0]['raw']['hex']=='00ff')
    add('result-does-not-prove-worker-exit',[start(),finish(),dict(action='next')],lambda o:event(o).get('error')=='health_worker_outstanding' and o['final']==o['events'][1]['view'])
    r=response();r['fields'][0]['interpretation']['text']='owned\x1b[31m\x00\n\u202e\U0001f4be'
    add('exact-control-and-unicode-value',[start(),finish(r)],lambda o,t=r['fields'][0]['interpretation']['text']:src(o)['fields'][0]['interpretation']['text']==t)
    for availability in ('unavailable','denied','error','unknown'):
        for kind in ('raw','interpretation'):
            r=response();r['fields'][0][kind]=dict(availability=availability,**({'hex':None} if kind=='raw' else {'text':None,'rule_id':None}))
            add(kind+'-'+availability,[start(),finish(r)],lambda o,k=kind,a=availability:complete(o) and src(o)['fields'][0][k]['availability']==a)
    r=response();r['outcome']='partial';r['fields']=r['fields'][:1]
    add('partial-leaves-omitted-values-unknown',[start(),finish(r),retire()],lambda o:o['final']['state']=='partial' and not o['final']['coverage_complete'] and src(o)['fields'][0]['received'] and all(not f['received'] and f['raw']['hex'] is None for f in src(o)['fields'][1:]))
    r=response();r['fields']=[];r['outcome']='partial';add('empty-partial',[start(),finish(r)],lambda o:o['final']['state']=='partial' and not any(f['received'] for f in src(o)['fields']))
    for outcome in ('unavailable','denied','error'):
        r=response();r.update(outcome=outcome,fields=[]);add('observer-'+outcome,[start(),finish(r)],lambda o,x=outcome:src(o)['state']==x and not o['final']['coverage_complete'])
    q=fixture();q['sources'][0]['capability']='unavailable';add('bridge-unavailable-before-query',[start(q)],lambda o:o['queries']=='0' and src(o)['state']=='unavailable' and event(o)['error']=='health_observer_unavailable',q)
    add('duplicate-start',[start(),start()],lambda o:o['queries']=='1' and event(o)['error']=='health_already_started' and event(o)['view']==o['events'][0]['view'])
    add('duplicate-result',[start(),finish(),finish()],lambda o:event(o)['error']=='health_stale_result' and event(o)['view']==o['events'][1]['view'])
    add('retirement-before-result',[start(),retire(),finish()],lambda o:event(o)['error']=='health_stale_result' and src(o)['state']=='unavailable' and not src(o)['worker_outstanding'])
    add('timeout-late-result',[start(),dict(action='timeout',key='a'),finish(),dict(action='next'),retire(),dict(action='next')],lambda o:o['events'][2]['error']=='health_stale_result' and o['events'][3]['error']=='health_worker_outstanding' and o['events'][2]['view']==o['events'][1]['view'] and o['final']['capture']=='2' and src(o)['state']=='not_started')
    add('repeat-timeout-and-retirement',[start(),dict(action='timeout',key='a'),dict(action='timeout',key='a'),retire(),retire()],lambda o:o['events'][1]['changed'] and not o['events'][2]['changed'] and not event(o)['changed'] and src(o)['state']=='timed_out')
    add('cancel-before-start',[dict(action='cancel'),start(),dict(action='cancel')],lambda o:o['queries']=='0' and o['final']['state']=='cancelled' and o['events'][1]['error']=='health_cancelled' and not event(o)['changed'])
    add('cancel-keeps-valid-pending-result',[start(),dict(action='cancel'),finish(),dict(action='next'),retire()],lambda o:o['events'][1]['view']['state']=='cancel_requested' and o['events'][2]['accepted'] and o['events'][3]['error']=='health_worker_outstanding' and o['final']['state']=='cancelled' and src(o)['fields'][0]['received'])
    add('cancel-exit-without-result',[start(),dict(action='cancel'),retire()],lambda o:o['final']['state']=='cancelled' and src(o)['state']=='cancelled' and src(o)['diagnostic']=='observer_cancelled')
    add('cancel-after-completion-does-not-rewrite-facts',[start(),finish(),dict(action='cancel')],lambda o:not event(o)['changed'] and complete(o))
    add('fresh-capture-forgets-old-values',[start(),finish(),retire(),dict(action='next'),start(alias='b')],lambda o:o['final']['capture']=='2' and src(o)['worker']=='2' and not any(f['received'] for f in src(o)['fields']))
    for action in ('finish','timeout','retire'):
        a=dict(action=action,key='a');
        if action=='finish':a['response']=response()
        add('old-'+action+'-cannot-replace-new-worker',[start(),finish(),retire(),dict(action='next'),start(alias='b'),a],lambda o,x=action:(event(o).get('error')=='health_stale_result' if x=='finish' else not event(o)['changed']) and event(o)['view']==o['events'][4]['view'])
    add('worker-counter-max-fails-before-wrap',[start()],lambda o:event(o)['error']=='health_counter_exhausted' and src(o)['worker']==str(MAX) and o['queries']=='0',worker_seed=str(MAX))
    add('worker-counter-last-value-works',[start(),finish(response(worker=MAX))],lambda o:complete(o) and src(o)['worker']==str(MAX),worker_seed=str(MAX-1))
    add('capture-counter-max-fails-before-wrap',[dict(action='next')],lambda o:event(o)['error']=='health_counter_exhausted' and o['final']['capture']==str(MAX),capture_seed=str(MAX))
    add('capture-counter-last-value-works',[dict(action='next'),start(),finish(response(capture=MAX))],lambda o:complete(o) and o['final']['capture']==str(MAX),capture_seed=str(MAX-1))
    add('zero-capture-rejected',[],bad('health_integer'),capture_seed='0')
    for field in ('id','generation','identity_digest'):
        r=response();r['target'][field]='serial:FORGED' if field=='id' else '18' if field=='generation' else sha(b'wrong composite')
        add('wrong-target-'+field,[start(),finish(r)],malformed('health_target_mismatch'))
    r=response();r['provider_digest']=sha(b'replaced provider');add('wrong-provider',[start(),finish(r)],malformed('health_provider_mismatch'))
    r=response();r['ticket']['worker']='2';add('wrong-echoed-ticket',[start(),finish(r)],malformed('health_ticket_mismatch'))
    mutations=[('unknown-result-field',lambda r:r.update(force=True),'health_shape'),('duplicate-field',lambda r:r['fields'].append(copy.deepcopy(r['fields'][0])),'health_duplicate_field'),('unrequested-field',lambda r:r['fields'][0].update(id='other'),'health_unrequested_field'),('missing-complete-field',lambda r:r['fields'].pop(),'health_incomplete_result'),('sensitivity-downgrade',lambda r:r['fields'][3].update(sensitivity='public'),'health_shape'),('raw-hidden-under-unknown',lambda r:r['fields'][0]['raw'].update(availability='unknown'),'health_unavailable_value'),('interpretation-hidden-under-unknown',lambda r:r['fields'][0]['interpretation'].update(availability='unknown'),'health_unavailable_value'),('raw-invalid-hex',lambda r:r['fields'][0]['raw'].update(hex='0G'),'health_raw'),('raw-odd-hex',lambda r:r['fields'][0]['raw'].update(hex='0'),'health_raw'),('raw-over-budget',lambda r:r['fields'][0]['raw'].update(hex='00'*1025),'health_raw'),('interpretation-without-rule',lambda r:r['fields'][0]['interpretation'].update(rule_id=None),'health_text'),('interpretation-over-budget',lambda r:r['fields'][0]['interpretation'].update(text='x'*257),'health_text'),('unavailable-with-data',lambda r:r.update(outcome='unavailable'),'health_outcome_fields')]
    for name,mutate,code in mutations:
        r=response();mutate(r);add(name,[start(),finish(r)],malformed(code))
    for name,change,code in [('extra-request',lambda q:q.update(force=True),'health_shape'),('empty-sources',lambda q:q.update(sources=[]),'health_count'),('duplicate-source',lambda q:q['sources'].append(copy.deepcopy(q['sources'][0])),'health_duplicate_source'),('deep-test-capability',lambda q:q['sources'][0].update(capability='self-test'),'health_enum'),('unknown-capability',lambda q:q['sources'][0].update(capability='unbounded'),'health_enum'),('duplicate-request-field',lambda q:q['sources'][0]['fields'].append(copy.deepcopy(q['sources'][0]['fields'][0])),'health_duplicate_field'),('unknown-sensitivity',lambda q:q['sources'][0]['fields'][0].update(sensitivity='guess'),'health_enum'),('zero-generation',lambda q:q['target'].update(generation='0'),'health_integer'),('noncanonical-generation',lambda q:q['target'].update(generation='01'),'health_integer'),('generation-over-u64',lambda q:q['target'].update(generation=str(MAX+1)),'health_integer'),('oversized-id',lambda q:q['target'].update(id='x'*129),'health_id'),('control-id',lambda q:q['target'].update(id='id\x1b'),'health_id')]:
        q=fixture();change(q);add(name,[],bad(code),q)
    q=fixture();q['sources'][0]['fields']=[dict(id='f'+str(i),sensitivity='public') for i in range(33)];add('field-count-over-limit',[],bad('health_count'),q)
    for n in (8,9):
        q=fixture();q['sources']=[dict(q['sources'][0],id='fake:source'+str(i)) for i in range(n)]
        add('source-count-'+str(n),[],(lambda o:len(o['final']['sources'])==8) if n==8 else bad('health_count'),q)
    q=fixture();q['sources'][0]['fields']=[dict(id='f'+str(i),sensitivity='public') for i in range(32)];q['sources']=[dict(q['sources'][0],id='fake:source'+str(i)) for i in range(5)];add('total-field-count-over-limit',[],bad('health_count'),q)
    q=fixture();q['sources'][0]['fields']=[dict(id='f'+str(i),sensitivity='public') for i in range(5)];r=response(q)
    for f in r['fields']:f['raw']['hex']='00'*1024
    add('source-raw-byte-total-over-limit',[start(q),finish(r)],malformed('health_raw_total'),q)
    for flags in itertools.product((False,True),repeat=4):
        p=dict(zip(('identifiers','raw_values','interpretations','customer_data'),flags))
        def consent_check(o,p=p):
            v=event(o)['support'];source=v['sources'][0]
            if ('target' in v)!=p['identifiers'] or ('provider_digest' in source)!=p['identifiers']:return False
            for i,c in enumerate(('public','identifier','customer','secret')):
                field=source['fields'][i];allowed=c!='secret' and (c!='identifier' or p['identifiers']) and (c!='customer' or p['customer_data'])
                if ('id' in field)!=(allowed and p['identifiers']) or ('raw' in field)!=(allowed and p['raw_values']) or ('interpretation' in field)!=(allowed and p['interpretations']):return False
                if field['raw_availability']!='available' or field['interpretation_availability']!='available':return False
            encoded=canonical(v)
            return b'OWNED-SENTINEL-secret' not in encoded and b'OWNED-INTERPRETATION-secret' not in encoded and b'debug' not in encoded
        add('consent-'+''.join('1' if x else '0' for x in flags),[start(),finish(),dict(action='support',policy=p)],consent_check)
    add('default-support-contains-no-identifier-or-content',[start(),finish(),dict(action='support',policy=policy())],lambda o:all(x not in canonical(event(o)['support']) for x in (b'target:owned',b'fake:health',b'identity_digest',b'provider_digest',b'temperature',b'serial',b'"id":"label"',b'debug',b'00ff',b'OWNED-',b'rule_id')))
    q=fixture();q['sources'].append(dict(q['sources'][0],id='fake:health.2',provider_digest=sha(b'provider2')));r=response(dict(target=q['target'],sources=[q['sources'][1]]));r['target']['generation']='18'
    add('bad-second-observer-preserves-first-observer',[start(q),finish(response(q)),retire(),start(dict(sources=[q['sources'][1]]),'b'),finish(r,'b')],lambda o:o['final']['state']=='partial' and o['final']['sources'][0]==o['events'][2]['view']['sources'][0] and o['final']['sources'][1]['state']=='malformed',q)
    for p in ({},dict(policy(),force=True),dict(policy(),raw_values='yes')):
        add('invalid-policy-'+str(len(cases)),[dict(action='support',policy=p)],lambda o:event(o).get('error') in ('health_shape','health_policy'))
    # Fill a structurally valid result to the exact native JSON byte budget.
    q=fixture();q['sources'][0]['fields']=[dict(id='f%02d'%i+'x'*125,sensitivity='public') for i in range(32)];r=response(q)
    for i,f in enumerate(r['fields']):f['raw']['hex']='00'*1024 if i<4 else '';f['interpretation'].update(text='x',rule_id='r'+'x'*127)
    remaining=65536-len(canonical(r));assert remaining>0
    for f in r['fields']:
        t=f['interpretation']['text']
        while len(t)<256 and remaining>=6:t+='\x00';remaining-=6
        while len(t)<256 and remaining>0:t+='x';remaining-=1
        f['interpretation']['text']=t
    assert remaining==0 and len(canonical(r))==65536
    add('exact-result-json-byte-limit',[start(q),finish(r)],complete,q)
    x=copy.deepcopy(r);next(f for f in x['fields'] if len(f['interpretation']['text'])<256)['interpretation']['text']+='x';assert len(canonical(x))==65537
    add('one-byte-over-result-json-limit',[start(q),finish(x)],malformed('health_input_limit'),q)
    # Exercise the maximum total field count and lossless report projection.
    q=fixture();q['sources'][0]['fields']=[dict(id='f%02d'%i,sensitivity='public') for i in range(32)];q['sources']=[dict(q['sources'][0],id='fake:source'+str(i)) for i in range(4)];actions=[]
    for i,s in enumerate(q['sources']):
        one=dict(target=q['target'],sources=[s]);r=response(one)
        for j,f in enumerate(r['fields']):f['raw']['hex']='00'*1024 if j<4 else '';f['interpretation']['text']='\x00'*256
        actions += [start(one,'a'+str(i)),finish(r,'a'+str(i)),retire('a'+str(i))]
    add('maximum-total-fields-and-content',actions,lambda o:o['final']['state']=='complete' and sum(len(s['fields']) for s in o['final']['sources'])==128 and len(canonical(o['final']))<=1048576,q)
    return cases

def main():
    p=argparse.ArgumentParser();p.add_argument('--probe',type=Path,required=True);p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--evidence',type=Path);a=p.parse_args()
    profile=json.loads((a.root/'spec/catalog/health-observation-prototype.json').read_bytes());q=fixture();r=response()
    assert set(q)==set(profile['request_fields']) and set(q['target'])==set(profile['target_fields']) and set(q['sources'][0])==set(profile['source_fields']) and set(q['sources'][0]['fields'][0])==set(profile['field_request_fields'])
    assert set(r)==set(profile['result_fields']) and set(r['fields'][0])==set(profile['field_result_fields']) and set(r['fields'][0]['raw'])==set(profile['raw_fields']) and set(r['fields'][0]['interpretation'])==set(profile['interpretation_fields']) and set(policy())==set(profile['policy_fields'])
    cases_=cases();encoded=b''.join(canonical(request)+b'\n' for _,request,_ in cases_);run=subprocess.run([str(a.probe.resolve())],input=encoded,capture_output=True,timeout=90)
    assert run.returncode==0 and not run.stderr,(run.returncode,run.stderr);lines=run.stdout.splitlines();assert len(lines)==len(cases_),(len(lines),len(cases_))
    observations=[];failed=[]
    for (name,request,check),line in zip(cases_,lines):
        output=json.loads(line)
        try:passed=bool(check(output))
        except (KeyError,TypeError,ValueError):passed=False
        observations.append(dict(name=name,passed=passed,input_sha256=sha(request),output_sha256=sha(line),error=output.get('error')))
        if not passed:failed.append(dict(name=name,output=output))
    evidence=dict(passed=not failed,cases=len(cases_),physical_io=False,self_tests=False,provider_admitted=False,public_command_implemented=False,observations=observations)
    if a.evidence:a.evidence.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8',newline='\n')
    assert not failed,json.dumps(failed[:3],indent=2)
    print(str(len(cases_))+' independent native health/redaction cases passed; no physical provider or reliability admitted')
if __name__=='__main__':main()
