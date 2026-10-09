"""Independent byte/grant/order assertions for the private inward export port."""
import argparse,copy,hashlib,itertools,json,subprocess
from pathlib import Path
from test_case import encode
def digest(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def grant():return dict(definition_digest='$prepared',report_write=True,host_effects=True)
def policy(flags):return dict(zip(('identifiers','raw_values','interpretations','customer_data'),flags))
def inspect(v):
    d=v['definition'];a=d['artifact'];payload=encode(v['artifact_preview'])+b'\n'
    assert digest(encode(d))==v['definition_digest'] and a['digest']==digest(payload) and int(a['bytes'])==len(payload)
    assert a['scope']=='fixture-case-support' and a['encoding']=='private-case-json-utf8-lf/1'
    assert b'OWNED-SECRET' not in payload and b'534543524554' not in payload
    assert v['outcome']['worker_exit']=='unobserved' and not v['outcome']['physical_backing_qualified']
    if v['outcome']['status']=='completed':
        assert v['output_digest']==digest(payload) and int(v['output_bytes'])==len(payload)
        assert all(int(v['outcome'][k])==len(payload) for k in ('submitted_bytes','written_bytes','read_bytes','verified_bytes'))
        assert v['outcome']['flush']=='api_confirmed' and not v['outcome']['uncertain_effect']
    return payload
def main():
    p=argparse.ArgumentParser();p.add_argument('--probe',required=True,type=Path);p.add_argument('--root',required=True,type=Path);p.add_argument('--evidence',type=Path);a=p.parse_args()
    profile=json.loads((a.root/'spec/catalog/report-export-prototype.json').read_bytes());assert profile['limits']['artifact_bytes']==1048577 and profile['limits']['chunk_bytes']==65536
    records=[]
    def run(name,extra=None,refusal=None):
        request=dict(grant=grant());request.update(extra or {});raw=encode(request);r=subprocess.run([str(a.probe.resolve())],input=raw,capture_output=True,timeout=30)
        assert r.returncode==(3 if refusal else 0) and not r.stderr,(name,r.returncode,r.stdout,r.stderr)
        v=json.loads(r.stdout)
        if refusal:assert v['refusal']==refusal,(name,v)
        else:inspect(v)
        records.append(dict(name=name,input_sha256=digest(raw),output_sha256=digest(r.stdout),status=v.get('outcome',{}).get('status'),diagnostic=v.get('refusal') or v.get('outcome',{}).get('diagnostic')))
        return v
    baseline=run('default-completed');assert baseline['outcome']['status']=='completed' and baseline['writes']=='1'
    for flags in itertools.product((False,True),repeat=4):
        v=run('policy-'+''.join(str(int(b)) for b in flags),dict(policy=policy(flags)));payload=inspect(v)
        ids,raw,interpret,customer=flags
        assert ('case_id' in v['artifact_preview'])==ids
        assert (b'OWNED-SERIAL' in payload)==(ids and interpret) and (b'OWNED-CUSTOMER' in payload)==(customer and interpret)
        assert (b'"hex":"23"' in payload)==raw
    v=run('multichunk-exact-controls',dict(large=True,policy=policy((True,True,True,True))));assert int(v['writes'])>1 and int(v['reads'])>1 and len(inspect(v))>65536
    v=run('literal-control-encoding',dict(controls=True,policy=policy((True,True,True,True))));assert b'\\u001b[31m' in inspect(v) and b'\\u000a' in inspect(v)
    for key in ('definition_digest','report_write','host_effects'):
        g=grant();g[key]='sha256:'+'0'*64 if key=='definition_digest' else False
        v=run('grant-'+key,dict(grant=g));assert v['outcome']['status']=='refused' and v['outcome']['diagnostic']=='export_grant' and v['observations']=='0' and not v['created']
    expected={
        'binding-before':('failed','export_binding_changed','not_created'),
        'binding-after':('failed','export_binding_changed','created'),
        'create-refused':('refused','fixture_no_creation','not_created'),
        'create-unknown':('failed','fixture_create_unknown','uncertain'),
        'created-then-error':('failed','fixture_created_error','uncertain'),
        'write-error':('failed','fixture_write_error','created'),
        'write-short':('failed','export_short_write','created'),
        'write-ack-lost':('failed','fixture_ack_lost','created'),
        'write-oversized':('failed','export_write_acknowledgement','created'),
        'flush-error':('failed','fixture_flush_error','created'),
        'read-error':('failed','fixture_read_error','created'),
        'read-short':('failed','export_short_read','created'),
        'read-oversized':('failed','export_read_acknowledgement','created'),
        'read-corrupt':('failed','export_readback_mismatch','created'),
        'wrong-size':('failed','export_output_length','created')}
    for fault,(status,error,state) in expected.items():
        v=run(fault,dict(fault=fault));o=v['outcome'];assert (o['status'],o['diagnostic'],o['output_state'])==(status,error,state),(fault,v)
        assert o['uncertain_effect']==(state!='not_created')
        if fault in ('write-error','write-ack-lost','write-oversized'):assert o['written_bytes'] is None
        if fault=='flush-error':assert o['flush']=='uncertain'
        if fault.startswith('read-'):assert o['verified_bytes']=='0'
    for fault in ('cancel-before','cancel-created','cancel-written','cancel-flushed'):
        v=run(fault,dict(fault=fault));o=v['outcome'];assert o['status']=='cancelled' and o['verified_bytes']=='0'
        assert o['output_state']==('not_created' if fault=='cancel-before' else 'created')
    bindings=baseline['definition']['resources']
    mutations=[('extra',lambda r:r.update(extra=True),'export_shape'),('epoch',lambda r:r['destination'].update(epoch='unbound'),'export_digest'),
        ('access',lambda r:r['destination'].update(access='overwrite'),'export_access'),('verification',lambda r:r['destination'].update(verification='none'),'export_access'),
        ('alias-id',lambda r:r['destination'].update(identity=r['producer']['identity']),'export_alias'),('alias-location',lambda r:r['destination'].update(location=r['producer']['location']),'export_alias'),
        ('producer-digest',lambda r:r['producer'].update(digest='sha256:'+'A'*64),'export_digest'),('identity-controls',lambda r:r['destination'].update(identity='x\x1b'),'export_identity'),
        ('location-limit',lambda r:r['destination'].update(location='x'*961),'export_identity')]
    for name,mutate,error in mutations:
        r=copy.deepcopy(bindings);mutate(r);run('definition-'+name,dict(resources=r),refusal=error)
    for bad in ({},dict(default=True),policy((1,False,False,False))):run('invalid-policy-'+str(len(records)),dict(policy=bad),refusal='case_shape' if len(bad)!=4 else 'case_policy')
    evidence=dict(passed=True,cases=len(records),observations=records,file_io=False,physical_io=False,public_command=False,worker_containment_qualified=False)
    if a.evidence:a.evidence.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(str(len(records))+' independent native inward export/grant/byte/fault cases passed')
if __name__=='__main__':main()
