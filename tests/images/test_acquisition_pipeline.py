"""Independent byte/hash and fault expectations for the private native pipeline.

The probe implements in-memory provider faults. This is neither file-provider
admission nor process/power-loss durability qualification.
"""
import argparse
import copy
import hashlib
import json
import random
from pathlib import Path
import subprocess


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def plan(size, chunk=4096):
    resources = {}
    for role in ('source', 'destination', 'map', 'host', 'executable', 'provider'):
        identity = role + '-fixture-id'
        resources[role] = dict(identity=identity, epoch=role+'-generation-1',
            access={'source':'read','destination':'create-write','map':'create-append','executable':'read'}.get(role,'observe'),
            start='0', end=str(size if role in ('source','destination') else 0), aliases=[identity],
            failure_domain='fixture-volume' if role in ('source','destination','map') else 'fixture-runtime',
            verification={'destination':'readback-sha256','map':'ordered-hash-chain'}.get(role,'identity-epoch'))
    return dict(schema='org.disked.acquisition-plan-prototype/1',capture_epoch='fixture-capture-1',
        resources=resources,bytes=str(size),chunk_bytes=str(chunk),retry_limit='0',
        read_policy='ordinary',substitution='stop')


def source(size):
    return bytes((i*37+11)%251 for i in range(size))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--probe',required=True)
    parser.add_argument('--evidence');parser.add_argument('--root',default='.')
    parser.add_argument('--validate-schemas',action='store_true');args=parser.parse_args()
    receipts=[]
    schema=None
    if args.validate_schemas:
        import sys
        sys.path.insert(0,str(Path(args.root)/'spec/tools'))
        import specctl
        schema=specctl.Bundle(Path(args.root)/'spec')

    def run(name,p,steps=None,fixture=None,refusal=None,expected=None):
        f=dict(plan=p,source_hex=source(int(p['bytes'])).hex() if int(p['bytes'])<3*1024*1024 else '',steps=steps if steps is not None else [{}])
        if fixture:f.update(fixture)
        completed=subprocess.run([args.probe],input=json.dumps(f).encode(),capture_output=True,timeout=15)
        value=json.loads(completed.stdout)
        if refusal:
            assert completed.returncode==3 and value.get('refusal')==refusal,(name,completed.returncode,value)
        else:
            assert completed.returncode==0,(name,completed.returncode,completed.stderr,value)
            assert value['plan_digest']==digest(canonical(p)),name
            if schema:schema.validate('urn:disked:schema:acquisition-plan-prototype:1',p)
            if expected:
                last=value['results'][-1]['outcome']
                for k,v in expected.items():assert last[k]==v,(name,k,last,v)
            for result in value['results']:
                if schema:schema.validate('urn:disked:schema:acquisition-outcome-prototype:1',result['outcome'])
        receipts.append(dict(name=name,exit_code=completed.returncode,passed=True,
            outcomes=[r['outcome'] for r in value.get('results',[])],refusal=value.get('refusal')))
        return value

    for n in (0,1,4095,4096,4097,65535,65536,65537,131073):
        p=plan(n)
        v=run('golden-'+str(n),p,expected=dict(status='completed',checkpoint_bytes=str(n),source_bytes=str(n),
            substituted_bytes='0',attempt_read_bytes=str(n),attempt_written_bytes=str(n),attempt_verified_bytes=str(n),uncertain_effect=False))
        assert v['source_hex']==v['destination_hex']==source(n).hex()
        previous='sha256:'+'0'*64;position=0
        for i,row in enumerate(v['records']):
            r=json.loads(row['bytes']);assert row['complete'] and int(r['sequence'])==i and r['previous']==previous
            assert canonical(r).decode()==row['bytes'];previous=digest(row['bytes'].encode())
            if r['type']=='checkpoint':
                c=r['payload'];assert int(c['offset'])==position
                size=int(c['length']);assert c['sha256']==digest(source(n)[position:position+size]);position+=size
        assert position==n
        trace=[e for e in v['results'][0]['trace'] if e not in ('observe','stop','read_source')]
        if n:
            pos=trace.index('append:pending')
            assert trace[pos:pos+7]==['append:pending','flush_map','write_destination','flush_destination','read_destination','append:checkpoint','flush_map']
    for chunk in (65536,1048576):
        v=run('chunk-'+str(chunk),plan(131073,chunk),expected=dict(status='completed'))
        assert v['destination_hex']==source(131073).hex()
    rng=random.Random(103033)
    for i in range(12):
        n=rng.randrange(1,100000);v=run('generated-boundaries-'+str(i),plan(n,rng.choice((4096,65536,1048576))),expected=dict(status='completed',source_bytes=str(n)))
        assert v['destination_hex']==source(n).hex()

    p=plan(9000)
    unicode_plan=plan(35)
    for role,b in unicode_plan['resources'].items():
        b['identity']=role+'-é-漢';b['epoch']='generation-é-漢';b['aliases']=[b['identity']]
    v=run('lossless-unicode-binding-digest',unicode_plan,expected=dict(status='completed'));assert v['destination_hex']==source(35).hex()
    for bad_value,code in (('18446744073709551616','acquisition_integer'),('01','acquisition_integer')):
        bad=copy.deepcopy(p);bad['resources']['source']['end']=bad_value;run('resource-integer-'+bad_value,bad,refusal=code)
    bad=plan(2147483648,4096);run('finite-stream-map-budget',bad,refusal='acquisition_map_limit')
    v=run('definition-is-inert',p,steps=[]);assert not v['records'] and not v['destination_hex'] and not v['results']
    for role in ('source','destination','map','host'):
        v=run('grant-deny-'+role,p,[{'deny_'+role:True}],expected=dict(status='refused',diagnostic='acquisition_grant'))
        assert v['results'][0]['trace']==[] and not v['records']
    v=run('wrong-plan-grant',p,[dict(grant_digest='sha256:'+'0'*64)],expected=dict(status='refused',diagnostic='acquisition_grant'))
    assert not v['records'] and not v['destination_hex']
    for role in p['resources']:
        for key in ('identity','epoch','access','failure_domain','verification'):
            changed=copy.deepcopy(p['resources']);changed[role][key]+='-changed'
            v=run('fresh-'+role+'-'+key,p,[dict(observed_resources=changed)],expected=dict(status='refused',diagnostic='acquisition_binding_changed'))
            assert not v['records'] and not v['destination_hex']
    for output in ('destination','map'):
        for other in ('source','host','executable','provider','map' if output=='destination' else 'destination'):
            bad=copy.deepcopy(p);bad['resources'][output]['aliases'].append(bad['resources'][other]['identity'])
            run('alias-'+output+'-'+other,bad,refusal='acquisition_alias')
    for role in p['resources']:
        for kind in ('empty-aliases','missing-identity','unknown-access','wrong-extent','empty-domain','unknown-verification'):
            bad=copy.deepcopy(p);b=bad['resources'][role]
            if kind=='empty-aliases':b['aliases']=[];code='acquisition_aliases_unknown'
            elif kind=='missing-identity':b['aliases']=['different-id'];code='acquisition_aliases_unknown'
            elif kind=='unknown-access':b['access']='force';code='acquisition_access'
            elif kind=='wrong-extent':b['end']=str(int(b['end'])+1);code='acquisition_footprint'
            elif kind=='empty-domain':b['failure_domain']='';code='acquisition_identity'
            else:b['verification']='none';code='acquisition_verification'
            run('binding-'+role+'-'+kind,bad,refusal=code)
    for key,val,code in (('bytes',str(2**64),'acquisition_integer'),('bytes',str(2**63),'acquisition_size'),
                         ('bytes','01','acquisition_integer'),('chunk_bytes','8192','acquisition_chunk_limit'),
                         ('retry_limit','4','acquisition_retry_limit'),('read_policy','unknown','acquisition_read_policy'),
                         ('substitution','hidden-zero','acquisition_substitution')):
        bad=copy.deepcopy(p);bad[key]=val;run('plan-'+key+'-'+val,bad,refusal=code)
    bad=copy.deepcopy(p);bad['read_policy']='failing-read-mostly';bad['retry_limit']='1'
    run('failing-media-no-aggressive-rereads',bad,refusal='acquisition_aggressive_reread_not_admitted')
    bad=copy.deepcopy(p);bad['extra']=True;run('unknown-plan-field',bad,refusal='acquisition_shape')
    v=run('no-clobber-provider',p,[dict(preexisting=True)],expected=dict(status='refused',diagnostic='fixture_destination_exists'))
    assert not v['records'] and not v['destination_hex']
    v=run('stop-before-effects',p,[dict(stop_after_bytes='0')],expected=dict(status='paused',checkpoint_bytes='0'))
    assert 'create' not in v['results'][0]['trace'] and not v['records']
    v=run('stop-checkpoint-and-resume',p,[dict(stop_after_bytes='4096'),dict(resume=True)],expected=dict(status='completed'))
    assert v['results'][0]['outcome']['status']=='paused' and v['results'][0]['outcome']['checkpoint_bytes']=='4096'
    assert v['destination_hex']==source(9000).hex()

    v=run('read-failure-retained',p,[dict(read_error_offset='4096')],expected=dict(status='failed',diagnostic='acquisition_source_read',checkpoint_bytes='4096'))
    assert json.loads(v['records'][-1]['bytes'])['type']=='read_failure'
    v=run('read-failure-retry-new-attempt',p,[dict(read_error_offset='4096'),dict(resume=True)],expected=dict(status='completed'))
    assert v['destination_hex']==source(9000).hex()
    for policy in ('ordinary','failing-read-mostly'):
        sub=copy.deepcopy(p);sub['substitution']='zero-fill';sub['read_policy']=policy
        v=run('explicit-substitution-'+policy,sub,[dict(read_error_offset='4096')],expected=dict(status='completed_with_substitution',source_bytes='4904',substituted_bytes='4096'))
        wanted=bytearray(source(9000));wanted[4096:8192]=bytes(4096);assert bytes.fromhex(v['destination_hex'])==wanted
        assert v['source_hex']==source(9000).hex()
    retry=copy.deepcopy(p);retry['retry_limit']='1'
    v=run('bounded-retry-success',retry,[dict(read_error_offset='0',error_calls='1')],expected=dict(status='completed',attempt_read_bytes='13096'))
    assert v['destination_hex']==source(9000).hex()
    v=run('short-read-not-zero',p,[dict(short_read=True)],expected=dict(status='failed',diagnostic='acquisition_source_read',source_bytes='0',substituted_bytes='0'))
    v=run('provider-oversized-read',p,[dict(oversized_read=True)],expected=dict(status='failed',diagnostic='acquisition_provider_read_limit',checkpoint_bytes='0'))
    v=run('corrupt-output-retained',p,[dict(corrupt_write=True)],expected=dict(status='failed',diagnostic='acquisition_destination_verification',checkpoint_bytes='0',uncertain_effect=True))
    assert json.loads(v['records'][-1]['bytes'])['type']=='pending'
    v=run('partial-effect-observed-before-replay',p,[dict(partial_write='1000'),dict(resume=True)],expected=dict(status='completed'))
    assert v['destination_hex']==source(9000).hex()
    trace=v['results'][1]['trace'];assert trace.index('read_destination')<trace.index('write_destination')
    for role in p['resources']:
        for event in ('read_source','write_destination','read_destination'):
            v=run('late-binding-'+role+'-'+event,p,[dict(change_binding_after=event,change_role=role)],expected=dict(status='failed',diagnostic='acquisition_binding_changed'))
            if event=='read_source':assert 'write_destination' not in v['results'][0]['trace']
            else:assert v['results'][0]['outcome']['uncertain_effect']
    v=run('created-outputs-before-header-failure',p,[dict(crash='create',crash_after=True),dict(resume=True)],expected=dict(status='refused',diagnostic='acquisition_map_header'))
    assert v['results'][0]['outcome']['status']=='failed' and v['destination_hex'] and not v['records']

    transitions=[('append:header',True,1),('flush_map',False,1),('flush_map',True,1),('read_source',False,1),('read_source',True,1),
        ('append:pending',False,1),('append:pending',True,1),('write_destination',False,1),('write_destination',True,1),
        ('flush_destination',False,1),('flush_destination',True,1),('read_destination',False,1),('read_destination',True,1),
        ('append:checkpoint',False,1),('append:checkpoint',True,1),('flush_map',False,3),('append:seal',False,1),('append:seal',True,1)]
    for event,after,count in transitions:
        v=run('interrupt-'+event+'-'+str(after)+'-'+str(count),p,
            [dict(crash=event,crash_after=after,crash_occurrence=str(count)),dict(resume=True)],expected=dict(status='completed'))
        assert v['results'][0]['outcome']['status']=='failed' and v['destination_hex']==source(9000).hex()
        if event=='write_destination' and after:
            assert v['results'][1]['trace'].count('write_destination')==2  # completed pending chunk was observed, not rewritten
    v=run('torn-header-is-not-admitted',p,[dict(torn_append=True),dict(resume=True)],expected=dict(status='refused',diagnostic='acquisition_map_header'))
    base=run('resume-baseline',p,[dict(stop_after_bytes='4096')])
    def saved(v):return {k:copy.deepcopy(v[k]) for k in ('active','records','destination_hex')}
    v=run('resumed-destination-mismatch',p,[dict(resume=True,destination_xor='0')],saved(base),expected=dict(status='failed',diagnostic='acquisition_destination_verification'))
    assert 'write_destination' not in v['results'][0]['trace']
    v=run('resumed-source-bytes-mismatch',p,[dict(resume=True,source_xor='0')],saved(base),expected=dict(status='failed',diagnostic='acquisition_resume_source_changed'))
    assert 'write_destination' not in v['results'][0]['trace']
    for role in p['resources']:
        f=saved(base);f['active'][role]['epoch']+='-changed'
        v=run('resume-epoch-'+role,p,[dict(resume=True)],f,expected=dict(status='refused',diagnostic='acquisition_binding_changed'))
        assert 'write_destination' not in v['results'][0]['trace']
    for mode in ('bad-json','bad-sequence','bad-hash','duplicate-header','missing-pending','reordered','noncanonical'):
        f=saved(base)
        if mode=='bad-json':f['records'][1]['bytes']='{'
        elif mode in ('bad-sequence','bad-hash'):
            r=json.loads(f['records'][1]['bytes']);r['sequence' if mode=='bad-sequence' else 'previous']='99' if mode=='bad-sequence' else 'sha256:'+'f'*64;f['records'][1]['bytes']=canonical(r).decode()
        elif mode=='duplicate-header':f['records'].append(copy.deepcopy(f['records'][0]))
        elif mode=='missing-pending':del f['records'][1]
        elif mode=='reordered':f['records'][1:3]=reversed(f['records'][1:3])
        else:f['records'][1]['bytes']=' '+f['records'][1]['bytes']
        v=run('corrupt-map-'+mode,p,[dict(resume=True)],f)
        assert v['results'][0]['outcome']['status'] in ('failed','refused') and 'write_destination' not in v['results'][0]['trace']
    for complete in (False,True):
        f=saved(base);f['records'].append(dict(bytes='{torn',complete=complete))
        v=run('tail-'+str(complete),p,[dict(resume=True)],f)
        if complete:assert v['results'][0]['outcome']['status']=='failed'
        else:assert v['results'][0]['outcome']['status']=='completed' and 'discard_tail' in v['results'][0]['trace']
    def rechain(rows):
        previous='sha256:'+'0'*64
        for index,row in enumerate(rows):
            r=json.loads(row['bytes']);r['previous']=previous;r['sequence']=str(index)
            row['bytes']=canonical(r).decode();previous=digest(row['bytes'].encode())
    for key,val in (('offset','1'),('length','4097'),('read_bytes','4097'),('retries','1'),('state','unknown'),('read_error','fabricated')):
        f=saved(base)
        for index in (1,2):
            r=json.loads(f['records'][index]['bytes']);r['payload'][key]=val;f['records'][index]['bytes']=canonical(r).decode()
        rechain(f['records'])
        v=run('map-semantic-'+key,p,[dict(resume=True)],f)
        assert v['results'][0]['outcome']['status']=='failed' and 'write_destination' not in v['results'][0]['trace']
    f=saved(base);r=json.loads(f['records'][0]['bytes']);r['payload']['plan']['capture_epoch']='another-capture';r['payload']['plan_digest']=digest(canonical(r['payload']['plan']));f['records'][0]['bytes']=canonical(r).decode();rechain(f['records'])
    run('different-original-definition',p,[dict(resume=True)],f,expected=dict(status='refused',diagnostic='acquisition_resume_plan'))
    sub=copy.deepcopy(p);sub['substitution']='zero-fill'
    s=run('substitution-pending-before-interruption',sub,[dict(read_error_offset='0',crash='write_destination',crash_after=True)])
    v=run('substitution-pending-resume',sub,[dict(resume=True)],saved(s),expected=dict(status='completed_with_substitution',substituted_bytes='4096'))
    assert bytes.fromhex(v['destination_hex'])[:4096]==bytes(4096)
    f=saved(s);r=json.loads(f['records'][1]['bytes']);r['payload']['sha256']=digest(source(4096));f['records'][1]['bytes']=canonical(r).decode();rechain(f['records'])
    run('forged-substitution-cannot-match-source',sub,[dict(resume=True)],f,expected=dict(status='failed',diagnostic='acquisition_map_substitution'))
    failing=copy.deepcopy(p);failing['read_policy']='failing-read-mostly'
    v=run('failing-resume-no-prefix-reread',failing,[dict(stop_after_bytes='4096'),dict(resume=True,source_xor='0')],expected=dict(status='completed',attempt_read_bytes='4904',consistency='live-uncoordinated'))
    assert v['destination_hex']==source(9000).hex() and v['source_hex']!=source(9000).hex()  # explicitly no coherent/point-in-time claim
    final=run('sealed-baseline',p)
    v=run('sealed-resume-inert',p,[dict(resume=True)],saved(final),expected=dict(status='completed',attempt_written_bytes='0'))
    assert not any(x.startswith('append:') for x in v['results'][0]['trace'])
    for mode in ('wrong-coverage','extra-complete','extra-incomplete','unknown-record'):
        f=saved(final)
        if mode=='wrong-coverage':
            r=json.loads(f['records'][-1]['bytes']);r['payload']['source_bytes']='0';f['records'][-1]['bytes']=canonical(r).decode();rechain(f['records'])
        elif mode=='extra-incomplete':f['records'].append(dict(bytes='{tail',complete=False))
        else:
            r=json.loads(f['records'][-1]['bytes']);r['type']='unknown' if mode=='unknown-record' else 'seal';f['records'].append(dict(bytes=canonical(r).decode(),complete=True));rechain(f['records'])
        v=run('seal-'+mode,p,[dict(resume=True)],f)
        assert v['results'][0]['outcome']['status']=='failed' and 'write_destination' not in v['results'][0]['trace']
    if args.evidence:
        Path(args.evidence).write_text(json.dumps(dict(passed=True,cases=len(receipts),scope='private in-memory acquisition ports, not real files or power loss',receipts=receipts),indent=2)+'\n')
    print('PASS:',len(receipts),'private native acquisition pipeline cases')


if __name__=='__main__':main()
