"""Independent native case-chain, retention, inference and disclosure fixtures."""
import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path
import subprocess

def encode(v):
    # Independent encoding of the private contract: every control uses u00xx,
    # including newline/tab, while literal backslashes remain literal data.
    def string(s):return '"'+''.join('\\u%04x'%ord(c) if ord(c)<32 else '\\"' if c=='"' else '\\\\' if c=='\\' else c for c in s)+'"'
    def value(x):
        if isinstance(x,str):return string(x)
        if isinstance(x,dict):return '{'+','.join(string(k)+':'+value(x[k]) for k in sorted(x))+'}'
        if isinstance(x,list):return '['+','.join(value(y) for y in x)+']'
        return json.dumps(x,allow_nan=False,separators=(',',':'))
    return value(v).encode()
def digest(v):return 'sha256:'+hashlib.sha256(encode(v) if not isinstance(v,bytes) else v).hexdigest()
CODE=dict(source_revision='a'*40,input_digest=digest(b'owned code inputs'),configuration_digest=digest(b'owned config'))
FIXTURE=digest(b'owned case fixture')
def policy(values=(False,False,False,False)):return dict(zip(('identifiers','raw_values','interpretations','customer_data'),values))
def request():
    fields=[dict(id=i,sensitivity=s) for i,s in [('temperature','public'),('serial','identifier'),('filename','customer'),('secret','secret')]]
    return dict(target=dict(id='fake:case-target@1',generation='1',identity_digest=digest(b'composite')),sources=[dict(id='fake:case-source@1',provider_digest=digest(b'provider'),capability='observe',fields=fields)])
def response(q=None,source=0):
    q=q or request();s=q['sources'][source];values={'temperature':(b'\x23','35 Celsius'),'serial':(b'OWNED-SERIAL','OWNED-SERIAL'),'filename':(b'OWNED-CUSTOMER','OWNED-CUSTOMER'),'secret':(b'OWNED-SECRET','OWNED-SECRET')}
    fields=[]
    for f in s['fields']:
        raw,text=values.get(f['id'],(b'\x00','owned value'))
        fields.append(dict(id=f['id'],raw=dict(availability='available',hex=raw.hex()),interpretation=dict(availability='available',text=text,rule_id='fixture.case@1')))
    return dict(ticket=dict(source=s['id'],capture='1',worker='1'),target=q['target'],provider_digest=s['provider_digest'],outcome='complete',fields=fields)
def capture(name='a',q=None,r=None,retire=True):
    q=q or request();actions=[dict(action='capture',as_=name,request=q)]
    actions[0]['as']=actions[0].pop('as_')
    for i,s in enumerate(q['sources']):
        key=name+str(i);actions.append(dict(action='start',capture=name,source=s['id'],as_=key));actions[-1]['as']=actions[-1].pop('as_')
        actions.append(dict(action='finish',capture=name,ticket=key,response=r if r is not None else response(q,i)))
        if retire:actions.append(dict(action='retire',capture=name,ticket=key))
    return actions
def append(name='a',phase='before',**extra):return dict(action='append',capture=name,phase=phase,origin='injected-fixture',fixture_digest=FIXTURE,**extra)
def pair(q=None,r=None):return capture()+[append()]+capture('b',q,r)+[append('b','after')]
def event(o):return o['events'][-1]
def compare(o,state):return o['final']['comparison']['state']==state
def support(o):return event(o)['support']
def unchanged(o,error):return event(o).get('error')==error and event(o)['case_digest']==o['events'][-2]['case_digest']
def validate_chains(o):
    if 'error' in o:return
    view=o['final'];assert digest(view)==o['case_digest']
    context=digest(dict(case_id=view['case_id'],code_identity=view['code_identity']));assert context==view['context_digest']
    previous='sha256:'+'0'*64
    for i,record in enumerate(view['records']):
        assert record['context_digest']==context and record['sequence']==str(i+1) and record['previous_digest']==previous
        row=copy.deepcopy(record);expected=row.pop('digest');assert digest(row)==expected;previous=expected
        assert record['clock']==dict(domain='unobserved',observed_at=None)
    for e in o['events']:
        if 'support' not in e:continue
        p=e['support'];previous='sha256:'+'0'*64
        for row in p['records']:
            if p['policy']['identifiers']:
                item=copy.deepcopy(row);expected=item.pop('projection_digest');assert item['previous_projection_digest']==previous and digest(item)==expected;previous=expected
            else:assert 'projection_digest' not in row and 'previous_projection_digest' not in row
        for omitted in [view['context_digest'],o['case_digest'],FIXTURE]+[r['digest'] for r in view['records']]:assert omitted.encode() not in encode(p)
        assert p['claims']==view['claims'] and p['claims']['authenticity']=='not_established' and not p['claims']['physical_admission'] and not p['claims']['mutation_authority']

def cases():
    cases=[]
    def add(name,actions,check,**extra):
        value=dict(case_id='case:owned@1',code_identity=copy.deepcopy(CODE),actions=actions);value.update(extra);cases.append((name,value,check))
    add('empty-case-is-open-and-incomparable',[],lambda o:o['final']['collection_state']=='open' and not o['final']['records'] and compare(o,'not_comparable'))
    add('complete-pair-is-closed-with-fixture-inference',pair(),lambda o:o['final']['collection_state']=='closed' and compare(o,'equal') and not o['final']['comparison']['fresh_sampling_established'])
    add('missing-after-is-not-certification',capture()+[append()],lambda o:o['final']['collection_state']=='open' and compare(o,'not_comparable') and o['final']['claims']['storage_postconditions']=='not_established')
    a=append();a['origin']='compiled-fixture';add('compiled-origin-remains-a-declaration',capture()+[a],lambda o:o['final']['records'][0]['origin']=='compiled-fixture' and o['final']['claims']['authenticity']=='not_established')
    add('case-close-is-not-cancellation-or-exit-proof',[dict(action='capture',**{'as':'a'},request=request()),append(),dict(action='cancel',capture='a'),append(phase='after')],lambda o:o['final']['records'][0]['capture']['state']=='collecting' and o['final']['records'][1]['capture']['state']=='cancelled' and compare(o,'not_comparable'))
    for phase in ('observation','after','unknown'):
        add('first-phase-'+phase,capture()+[append(phase=phase)],lambda o:unchanged(o,'case_phase_order') and not o['final']['records'])
    add('second-before-rejected',capture()+[append(),append()],lambda o:unchanged(o,'case_phase_order'))
    add('append-after-closure-rejected',pair()+[append(phase='observation')],lambda o:unchanged(o,'case_closed'))
    for origin in ('native-observation','signed-operator','physical-device',''):
        a=append();a['origin']=origin;add('unqualified-origin-'+origin,capture()+[a],lambda o:unchanged(o,'case_origin_unavailable'))
    for fixture in ('sha256:'+'A'*64,'sha256:'+'0'*63,'sha256:'+'0'*65,'raw-name'):
        a=append();a['fixture_digest']=fixture;add('invalid-fixture-'+str(len(cases)),capture()+[a],lambda o:unchanged(o,'case_digest'))
    add('snapshot-survives-live-collector-reset',capture()+[append(),dict(action='next',capture='a'),append(phase='after')],lambda o:o['final']['records'][0]['capture']['sources'][0]['fields'][0]['raw']['hex']=='23' and o['final']['records'][1]['capture']['sources'][0]['fields'][0]['raw']['hex'] is None and compare(o,'not_comparable'))
    add('returned-view-is-not-mutable-history',pair()+[dict(action='mutate_returned_view')],lambda o:o['final']['case_id']=='case:owned@1' and len(o['final']['records'])==2 and event(o)['case_digest']==o['events'][-2]['case_digest'])
    add('recording-does-not-retire-worker',capture(retire=False)+[append(),append(phase='after')],lambda o:all(r['capture']['workers_outstanding']=='1' for r in o['final']['records']) and o['final']['claims']['source_preservation']=='not_established')
    r=response();r['fields'][0]['raw']['hex']='24';add('changed-public-raw',pair(r=r),lambda o:compare(o,'different'))
    r=response();r['fields'][0]['interpretation']['text']='36 Celsius';add('changed-public-interpretation',pair(r=r),lambda o:compare(o,'different'))
    for field in range(1,4):
        r=response();r['fields'][field]['raw']['hex']=b'CHANGED'.hex();r['fields'][field]['interpretation']['text']='CHANGED'
        add('nonpublic-field-'+str(field)+'-does-not-change-inference',pair(r=r),lambda o:compare(o,'equal'))
    for key,value in [('id','fake:replaced@1'),('generation','2'),('identity_digest',digest(b'replacement'))]:
        q=request();q['target'][key]=value;add('changed-target-'+key,pair(q=q),lambda o:compare(o,'not_comparable'))
    q=request();q['sources'][0]['provider_digest']=digest(b'replaced provider');add('replaced-provider-is-incomparable',pair(q=q),lambda o:compare(o,'not_comparable'))
    q=request();q['sources'][0]['id']='fake:replaced-observer@1';add('replaced-observer-is-incomparable',pair(q=q),lambda o:compare(o,'not_comparable'))
    q=request();q['sources'][0]['fields'][0]['id']='other-public';add('different-public-field-contract-is-incomparable',pair(q=q),lambda o:compare(o,'not_comparable'))
    q=request();q['sources'][0]['fields'].reverse();add('requested-field-order-does-not-change-comparison',pair(q=q),lambda o:compare(o,'equal'))
    q=request();q['sources'][0]['fields']=q['sources'][0]['fields'][1:];add('no-public-fields-is-incomparable',capture(q=q)+[append()]+capture('b',q)+[append('b','after')],lambda o:compare(o,'not_comparable'))
    for kind in ('raw','interpretation'):
        for state in ('unknown','unavailable','denied','error'):
            r=response();r['fields'][0][kind]=dict(availability=state,**({'hex':None} if kind=='raw' else {'text':None,'rule_id':None}))
            add('public-'+kind+'-'+state,pair(r=r),lambda o:compare(o,'not_comparable'))
    q=request();q['sources'][0]['capability']='unavailable'
    add('unavailable-before-and-after-retained',[dict(action='capture',**{'as':'a'},request=q),append(),append(phase='after')],lambda o:compare(o,'not_comparable') and all(r['capture']['sources'][0]['state']=='unavailable' for r in o['final']['records']))
    a=capture(retire=False);a+=[dict(action='timeout',capture='a',ticket='a0'),append(),append(phase='after')]
    add('timeout-after-reply-cannot-rewrite-observations',a,lambda o:all(r['capture']['sources'][0]['worker_outstanding'] and r['capture']['sources'][0]['state']=='complete' for r in o['final']['records']) and not o['events'][3]['changed'])
    # A timeout before any response leaves the accepted values unknown.
    a=capture(retire=False)[:2]+[dict(action='timeout',capture='a',ticket='a0'),append(),append(phase='after')]
    add('pending-timeout-keeps-unknown-values',a,lambda o:all(not r['capture']['sources'][0]['fields'][0]['received'] for r in o['final']['records']) and compare(o,'not_comparable'))
    for values in itertools.product((False,True),repeat=4):
        identifiers,raw,interpretations,customer=values;p=policy(values)
        def check(o,ids=identifiers,raw=raw,interp=interpretations,customer=customer):
            v=support(o);encoded=encode(v)
            if b'OWNED-SECRET' in encoded or b'4f574e45442d534543524554' in encoded:return False
            if ('case_id' in v)!=ids or ('code_identity' in v)!=ids:return False
            if v['comparison']['state']!=('equal' if raw and interp else 'not_disclosed'):return False
            for row in v['records']:
                fields=row['support_report']['sources'][0]['fields']
                for i,f in enumerate(fields):
                    permitted=i==0 or i==1 and ids or i==2 and customer
                    if ('raw' in f)!=bool(permitted and raw) or ('interpretation' in f)!=bool(permitted and interp) or ('id' in f)!=bool(permitted and ids):return False
            if not ids and any(x in encoded for x in (b'sha256:',b'case:owned',b'fake:',b'"rule_id"') if x!=b'"rule_id"' or not interp):return False
            return True
        add('support-policy-'+''.join('1' if v else '0' for v in values),pair()+[dict(action='support',policy=p)],check)
    # An omitted private value changes original custody while leaving the entire
    # selected support payload identical, including its disclosed hash chain.
    r=response();r['fields'][3]['interpretation']['text']='NEW-SECRET';r['fields'][3]['raw']['hex']=b'NEW-SECRET'.hex()
    add('secret-changed-private-custody-only',pair(r=r)+[dict(action='support',policy=policy((True,True,True,True)))],lambda o:compare(o,'equal') and b'NEW-SECRET' not in encode(support(o)))
    r=response();r['fields'][2]['interpretation']['text']='NEW-CUSTOMER';r['fields'][2]['raw']['hex']=b'NEW-CUSTOMER'.hex()
    add('customer-changed-without-disclosure',pair(r=r)+[dict(action='support',policy=policy((True,True,True,False)))],lambda o:compare(o,'equal') and b'NEW-CUSTOMER' not in encode(support(o)))
    r=response();r['fields'][1]['interpretation']['text']='NEW-SERIAL';r['fields'][1]['raw']['hex']=b'NEW-SERIAL'.hex()
    add('identifier-changed-without-disclosure',pair(r=r)+[dict(action='support',policy=policy((False,True,True,True)))],lambda o:compare(o,'equal') and b'NEW-SERIAL' not in encode(support(o)))
    r=response();r['fields'][2]['interpretation']['text']='owned\x1b[31m\n\u202e\U0001f4be';r['fields'][2]['raw']['hex']=r['fields'][2]['interpretation']['text'].encode().hex()
    add('display-escapes-but-retains-machine-values',pair(r=r)+[dict(action='support',policy=policy((True,True,True,True))),dict(action='display',policy=policy((True,True,True,True)))],lambda o:event(o)['display'].isascii() and '\x1b' not in event(o)['display'] and json.loads(event(o)['display'])==o['events'][-2]['support'])
    for p in ({},dict(policy(),force=True),dict(policy(),raw_values='yes')):
        add('invalid-policy-'+str(len(cases)),pair()+[dict(action='support',policy=p)],lambda o:event(o).get('error') in ('case_shape','case_policy') and event(o)['case_digest']==o['events'][-2]['case_digest'])
    add('maximum-records-can-close',capture()+[append()]+[append(phase='observation') for _ in range(14)]+[append(phase='after')],lambda o:len(o['final']['records'])==16 and o['final']['collection_state']=='closed',trace=False)
    add('record-count-rejection-keeps-open-history',capture()+[append()]+[append(phase='observation') for _ in range(16)],lambda o:len(o['final']['records'])==16 and o['final']['collection_state']=='open' and unchanged(o,'case_record_limit'),trace=False)
    q=request();q['sources'][0]['fields']=[dict(id='f%02d'%i,sensitivity='public') for i in range(16)];q['sources']=[dict(q['sources'][0],id='fake:budget'+str(i)) for i in range(8)]
    actions=[dict(action='capture',**{'as':'a'},request=q)]
    for i,s in enumerate(q['sources']):
        r=response(q,i)
        for j,f in enumerate(r['fields']):f['raw']['hex']='00'*1024 if j<4 else '';f['interpretation']['text']='\x00'*256
        actions += [dict(action='start',capture='a',source=s['id'],**{'as':'k'+str(i)}),dict(action='finish',capture='a',ticket='k'+str(i),response=r),dict(action='retire',capture='a',ticket='k'+str(i))]
    actions += [append()]+[append(phase='observation') for _ in range(8)]
    add('aggregate-byte-limit-without-truncating-old-records',actions,lambda o:len(encode(o['final']))<=1048576 and event(o).get('error')=='case_byte_limit' and unchanged(o,'case_byte_limit') and 0<len(o['final']['records'])<9,trace=False)
    for case_id in ('','bad space','bad\x00id','x'*129):
        add('invalid-case-id-'+str(len(cases)),[],lambda o:o.get('error')=='case_id',case_id=case_id)
    add('maximum-case-id',[],lambda o:o['final']['case_id']=='x'*128,case_id='x'*128)
    for key,value,error in [('source_revision','A'*40,'case_code_revision'),('source_revision','a'*39,'case_code_revision'),('source_revision',3,'case_code_revision'),('input_digest','sha256:'+'A'*64,'case_digest'),('configuration_digest','not-a-hash','case_digest')]:
        code=dict(CODE);code[key]=value;add('invalid-code-'+str(len(cases)),[],lambda o,e=error:o.get('error')==e,code_identity=code)
    code=dict(CODE,operator='FORGED-OPERATOR');add('unknown-code-claim-rejected',[],lambda o:o.get('error')=='case_shape',code_identity=code)
    return cases

def main():
    p=argparse.ArgumentParser();p.add_argument('--probe',type=Path,required=True);p.add_argument('--root',type=Path,required=True);p.add_argument('--evidence',type=Path);a=p.parse_args()
    profile=json.loads((a.root/'spec/catalog/case-evidence-prototype.json').read_bytes());assert profile['limits']['records']==16 and profile['limits']['case_json_bytes']==1048576 and set(CODE)==set(profile['code_fields'])
    assert encode(dict(s='literal\\n\n\t'))==b'{"s":"literal\\\\n\\u000a\\u0009"}'
    fixtures=cases();observations=[];failures=[];outputs={}
    for name,request_,check in fixtures:
        run=subprocess.run([str(a.probe.resolve())],input=encode(request_)+b'\n',capture_output=True,timeout=30);assert run.returncode==0 and not run.stderr,(name,run.returncode,run.stderr)
        o=json.loads(run.stdout);outputs[name]=o
        try:
            validate_chains(o);passed=bool(check(o))
            if 'final' in o:assert set(o['final'])==set(profile['view_fields']) and all(set(row)==set(profile['record_fields']) for row in o['final']['records'])
        except (AssertionError,KeyError,TypeError,ValueError):passed=False
        observations.append(dict(name=name,passed=passed,input_sha256=digest(encode(request_)),output_sha256=digest(run.stdout),error=o.get('error')))
        if not passed:failures.append(dict(name=name,output=o if len(run.stdout)<8000 else 'large fixture; output hash retained'))
    ordinary=outputs['support-policy-1111'];changed=outputs['secret-changed-private-custody-only']
    assert ordinary['case_digest']!=changed['case_digest'] and support(ordinary)==support(changed),'Private secrets changed the selected support payload'
    for changed_name,baseline in [('customer-changed-without-disclosure','support-policy-1110'),('identifier-changed-without-disclosure','support-policy-0111')]:
        assert outputs[changed_name]['case_digest']!=outputs[baseline]['case_digest'] and support(outputs[changed_name])==support(outputs[baseline]),'Omitted values changed the selected support payload/chain'
    evidence=dict(passed=not failures,cases=len(fixtures),observations=observations,physical_io=False,file_export=False,public_evidence_command=False,origin_authenticated=False)
    if a.evidence:a.evidence.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8',newline='\n')
    assert not failures,json.dumps(failures[:4],indent=2)
    print(str(len(fixtures))+' independent native case/custody/disclosure fixtures passed; no file export or forensic qualification')
if __name__=='__main__':main()
