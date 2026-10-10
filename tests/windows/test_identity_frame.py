"""Owned /2 ID/layout frames, pure replay and independent graph expectations; generated inputs only."""
import argparse,copy,hashlib,json,struct,subprocess,time
from pathlib import Path
from test_storage_queries import disk,volume,packet,digest
from test_identity_queries import identifiers,alignment,entry,layout

def identity_disk(key='disk',number=0,ids=None,align=None,table=None,serial=b'SERIAL'):
    d=disk(key,number,serial=serial)
    ids=identifiers([(1,3,0,key.encode())]) if ids is None else ids
    if table is None:
        table=bytearray(layout(entries=[entry(guid=(key+'.p').encode().ljust(16,b'\0')[:16])]))
        table[8:24]=key.encode().ljust(16,b'\0')[:16]
        struct.pack_into('<q',table,32,1048576-4096);table=bytes(table)
    replies=[];size=192
    while len(table)>size:replies.append(packet(ok=False,error=122));size*=2
    d['replies'].update(identifiers=[packet(ids[:8]),packet(ids)],alignment=[packet(alignment() if align is None else align)],layout=replies+[packet(table)])
    return d

def fixture(*subjects,**kw):return dict(profile='identity-layout',subjects=list(subjects or (identity_disk(),volume())),**kw)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--pointer-bytes',type=int,choices=(4,8),required=True);a=p.parse_args()
    out=a.output.absolute();out.mkdir();probe=a.probe.absolute();checks=[];runs=[];children=set();code=hashlib.sha256(probe.read_bytes()).hexdigest()
    def check(name,ok):checks.append(dict(label=name,passed=bool(ok)));assert ok,name
    def run(name,value,expected=0):
        raw=json.dumps(value,separators=(',',':')).encode();(out/(name+'.request.json')).write_bytes(raw);start=time.monotonic()
        r=subprocess.run([probe],input=raw,capture_output=True,timeout=20);(out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
        runs.append(dict(label=name,exit_code=r.returncode,expected_exit=expected,elapsed_seconds=round(time.monotonic()-start,3)))
        check(name+' exit',r.returncode==expected and not r.stderr);v=json.loads(r.stdout);check(name+' pointer',v['pointer_bytes']==str(a.pointer_bytes))
        for sample in v.get('samples',[]):
            w=sample['worker'];g=sample['capture']['graph'];s=sample['capture']['sources'][0]
            if int(w['worker']['pid']):children.add((w['worker']['pid'],w['worker']['created']))
            check(name+' selected schema',w['schema']=='org.disked.nt-storage-worker-observation/2' and w['attempt_id'].startswith('identity-attempt:'))
            check(name+' pinned code',w['code_sha256']==code)
            check(name+' no authority',w['claims']==dict(live_namespace=False,physical_admission=False,mutation_authority=False,durable_reconnect=False))
            unbound=copy.deepcopy(g);rev=unbound.pop('revision');check(name+' graph digest',rev==digest(unbound))
            check(name+' peer retained',sum(n['id']=='fake:peer' for n in g['nodes'])==1)
            check(name+' graph bounds',len(g['nodes'])<=320 and len(g['edges'])<=512)
            for n in g['nodes']:
                if n['id']=='fake:peer':continue
                q=n['properties'];b=q['observation_binding'];payload=q['observation'];c=payload['worker_context']
                check(name+' unknown physical target',q['identity'] is None and q['media_generation'] is None and q['capacity_bytes'] is None and q['aliases']==[] and q['physical_identity']=='unknown' and not q['physical_admission'] and not q['mutation_authority'])
                check(name+' exact context',b['context_digest']==digest(c) and c['storage_profile']=='identity-layout' and c['code_sha256']==code and int(c['pid'])>0 and int(c['created'])>0 and payload['binding_scope']=='owned-reader-context')
                check(name+' node identity',n['id']=='observation:'+digest(dict(binding=b,kind=n['kind'],label=q['label'],payload=payload))[7:])
                check(name+' inert label',all(32<=ord(x)<=126 for x in q['label']))
                if q['state']!='stale' and w['result'] is not None:check(name+' exact current frame',b['frame_digest']==digest(w['result']) and c['pid']==w['worker']['pid'] and c['created']==w['worker']['created'] and c['request_digest']==w['request_digest'])
            if w['worker']['observation']=='running':check(name+' outstanding reader',s['outstanding'])
            elif w['worker']['observation'] in ('exited','not_started'):check(name+' retired ownership',not s['outstanding'])
        return v
    def execute(name,f=None,mode='sequence',**kw):return run(name,dict(mode=mode,stages=[fixture() if f is None else f],**kw))
    def last(v):return v['samples'][-1]
    healthy=execute('healthy');sample=last(healthy);w=sample['worker'];frame=w['result'];graph=sample['capture']['graph']
    check('complete owned frame',w['status']=='completed' and w['admitted'] and w['worker']['exit_code']=='0' and frame['schema']=='org.disked.nt-storage-observation-prototype/2' and frame['status']=='selected_queries_complete')
    check('six distinct nodes',len(graph['nodes'])==6 and len({n['id'] for n in graph['nodes']})==6)
    check('no backing inference',all(e['kind']=='contains' for e in graph['edges']))
    check('raw independent verification absent',frame['claims']['raw_metadata_independently_verified'] is False)
    id_node=next(n for n in graph['nodes'] if n['kind']=='storage-identifier-observation');part_node=next(n for n in graph['nodes'] if n['kind']=='storage-partition-observation');device=next(n for n in graph['nodes'] if n['kind']=='storage-device-observation')
    check('exact identifier bytes',id_node['properties']['observation']['identifier']['original_hex']==b'disk'.hex())
    part=part_node['properties']['observation']['partition'];check('lossless GPT units',part['gpt_name']['original_hex']==entry()[72:144].hex() and part['gpt_attributes']==str(0xf000000000000001))
    check('summary arrays separated','identifiers' not in device['properties']['observation']['components']['identifiers']['data'] and 'partitions' not in device['properties']['observation']['components']['layout']['data'])
    check('child parent bound',id_node['properties']['observation']['parent_observation']==device['id'] and part_node['properties']['observation']['parent_observation']==device['id'])
    def outcome(name,f,state='partial'):
        v=execute(name,f);check(name+' frame state',last(v)['worker']['result']['status']==state);return last(v)['worker']['result']
    shared=identifiers([(1,3,0,b'CLONE')]);v=outcome('clone-device-IDs',fixture(identity_disk(ids=shared),identity_disk('other',1,ids=shared,serial=b'OTHER')))
    check('candidate duplicates remain separate',len(v['resources'])==2 and all(x['conflicts']['duplicate_identifier_candidate'] for x in v['resources']))
    shared=identifiers([(1,3,1,b'SHARED-PORT')]);v=outcome('port-association-not-device-clone',fixture(identity_disk(ids=shared),identity_disk('other',1,ids=shared,serial=b'OTHER')),'selected_queries_complete')
    check('port observation not device identity',not any(x['conflicts']['duplicate_identifier_candidate'] for x in v['resources']))
    table=bytearray(layout());struct.pack_into('<q',table,32,1048576-4096);table=bytes(table)
    v=outcome('clone-GPT-layout',fixture(identity_disk(table=table),identity_disk('other',1,table=table,serial=b'OTHER')));check('clone layouts flagged',all(x['conflicts']['duplicate_layout_identifier_candidate'] for x in v['resources']))
    v=outcome('alignment-disagreement',fixture(identity_disk(align=alignment(520,4160,1040))));check('alignment conflict retained',v['resources'][0]['conflicts']['alignment_disagreement'])
    v=outcome('layout-capacity-disagreement',fixture(identity_disk(table=layout(entries=[entry(start=1048576)]))));check('range disagreement retained',v['resources'][0]['conflicts']['partition_range_disagreement'])
    v=outcome('MBR-unused-slots',fixture(identity_disk(table=layout(0,[entry(0,number=i+1,mbr_type=7 if i==0 else 0) for i in range(4)]))),'selected_queries_complete');check('unused slots preserved',len(v['resources'][0]['components']['layout']['data']['partitions'])==4)
    outcome('RAW-uninitialized',fixture(identity_disk(table=layout(2,[]))),'selected_queries_complete')
    for component,error,wanted in [('identifiers',5,'denied'),('alignment',50,'unsupported'),('layout',1167,'unavailable')]:
        f=fixture();f['subjects'][0]['replies'][component]=[packet(ok=False,error=error)];v=outcome(component+'-'+wanted,f);check(component+' typed outcome',v['resources'][0]['components'][component]['state']==wanted)
    for name,reply in [('pending-invalid-count',packet(ok=False,error=997,returned=9999)),('callback-runtime',dict(packet(),throw=True)),('callback-invalid-argument',dict(packet(),throw_invalid_argument=True))]:
        f=fixture();f['subjects'][0]['replies']['identifiers']=[reply];v=outcome(name,f,'unresolved');check(name+' batch stops',v['resources'][0]['components']['alignment']['state']=='not_attempted' and v['resources'][1]['components']['number']['state']=='not_attempted')
    for mode,kw in [('late',dict(worker_fault='delay')),('held',dict(reply_fault='hold')),('cancel-before',{}),('cancel-during',dict(worker_fault='delay')),('superseded',dict(worker_fault='delay')),('retire',dict(worker_fault='hang'))]:
        v=execute(mode,fixture(**kw),mode);s=last(v)
        if mode.startswith('cancel'):check(mode+' cancellation acknowledged',s['worker']['result']['status']=='cancelled' and s['worker']['cancellation_requested'])
        if mode=='late':check('late result retained same owned reader',v['samples'][1]['capture']['sources'][0]['state']=='timed_out' and s['worker']['status']=='completed')
        if mode=='held':check('held publication is not exit',v['samples'][1]['worker']['worker']['observation']=='running' and v['samples'][1]['capture']['sources'][0]['outstanding'])
        if mode=='superseded':check('old capture cannot publish',s['capture']['capture']=='2' and len(s['capture']['graph']['nodes'])==1)
        if mode=='retire':check('exact owned retirement',s['worker']['worker']['exit_code']=='31' and not s['capture']['sources'][0]['outstanding'])
    for fault in ('before_spawn','after_spawn','after_spawn_alloc'):
        v=execute('startup-'+fault,fixture(startup_fault=fault),'startup');check(fault+' recovery is explicit',len(v['start_errors'])==1 and last(v)['capture']['capture']=='2' and last(v)['worker']['worker']['exit_code']=='0')
    for fault in ('digest','capture','worker','schema','claims','capacity','status'):
        v=execute('reject-owned-reply-'+fault,fixture(reply_fault=fault));check(fault+' publication refused',last(v)['worker']['status']=='unknown' and last(v)['worker']['result'] is None and last(v)['worker']['diagnostic'] is not None)
    for fault in ('native_table','native_error','crash'):
        v=execute('refuse-'+fault,fixture(worker_fault=fault));check(fault+' untrusted or missing result',last(v)['worker']['status']=='unknown' and last(v)['worker']['result'] is None)
    invalid=fixture();invalid.pop('profile');run('missing-profile',dict(mode='sequence',stages=[invalid]),3)
    for value in ('0','33'):run('invalid-ID-policy-'+value,dict(mode='sequence',stages=[fixture()],detail_policy=dict(identifiers=value,partitions='64')),3)
    v=execute('restricted-ID-policy',fixture(identity_disk(ids=identifiers([(1,3,0,b'A'),(1,3,0,b'B')]))),detail_policy=dict(identifiers='1',partitions='64'));check('restricted IDs bounded',last(v)['worker']['result']['resources'][0]['components']['identifiers']['state']=='budget_exhausted')
    v=execute('restricted-partition-policy',fixture(identity_disk(table=layout(entries=[entry(),entry(start=32768,number=2,guid=b'X'*16)]))),detail_policy=dict(identifiers='32',partitions='1'));check('restricted partitions bounded',last(v)['worker']['result']['resources'][0]['components']['layout']['state']=='budget_exhausted')
    noids=identifiers([]);large=bytearray(layout(entries=[entry(start=4096+i*8192,number=i+1,guid=(i+1).to_bytes(16,'little')) for i in range(64)]));struct.pack_into('<q',large,32,1048576-4096)
    f=fixture(identity_disk(ids=noids,table=bytes(large)),identity_disk('other',1,ids=noids,table=bytes(large),serial=b'OTHER'),identity_disk('third',2,ids=noids,table=bytes(large),serial=b'THIRD'))
    v=outcome('shared-detail-exhaustion',f);check('third detail dispatch skipped',v['resources'][2]['components']['identifiers']['receipts']==[] and v['resources'][2]['components']['layout']['state']=='budget_exhausted' and v['resources'][2]['selected_partition_limit']=='0')
    ids=identifiers([(1,3,0,i.to_bytes(4,'little')) for i in range(32)]);subjects=[identity_disk(ids=ids,table=bytes(large))]
    for i in range(15):subjects.append(volume('volume'+str(i),rows=tuple((0,4096+j*4096,4096) for j in range(4 if i==14 else 2)),size=16384 if i==14 else 8192))
    complete=fixture(*subjects);partial=copy.deepcopy(complete);partial['subjects'][0]['replies']['alignment']=[packet(ok=False,error=5)]
    maximum=run('maximum-current-and-cache',dict(mode='sequence',stages=[complete,partial,partial]));g=last(maximum)['capture']['graph']
    check('128 details without widening graph',len(maximum['retained'][0]['nodes'])==145 and len(g['nodes'])==289 and sum(n['id']!='fake:peer' and n['properties']['state']=='stale' for n in g['nodes'])==144)
    v=run('pure-receipt-replay',dict(mode='read',snapshot=frame,fixture=fixture(worker_fault='hang')));check('replay is not a fixture call',v['snapshot']==frame)
    mutations={
        'physical-grant':lambda v:v['claims'].__setitem__('physical_admission',True),
        'profile':lambda v:v.__setitem__('schema','org.disked.nt-storage-observation-prototype/1'),
        'ID-property':lambda v:v['resources'][0]['components']['identifiers']['receipts'][0].__setitem__('property_id','6'),
        'alignment-property':lambda v:v['resources'][0]['components']['alignment']['receipts'][0].__setitem__('property_id','2'),
        'receipt-digest':lambda v:v['resources'][0]['components']['layout']['receipts'][0].__setitem__('returned_sha256','sha256:'+'0'*64),
        'original-name':lambda v:v['resources'][0]['components']['layout']['data']['partitions'][0]['gpt_name'].__setitem__('original_hex','00'),
        'partition-parent':lambda v:v['resources'][0]['components']['layout']['data']['partitions'][0].__setitem__('partition_number_hint','2'),
        'detail-policy':lambda v:v['policy'].__setitem__('frame_details','129'),
        'extra-receipt-field':lambda v:v['resources'][0]['components']['alignment']['receipts'][0].__setitem__('permit_writer',True),
        'oversize-layout':lambda v:v['resources'][0]['components']['layout']['receipts'][0].__setitem__('buffer_bytes','12289'),
    }
    for label,mutate in mutations.items():
        v=copy.deepcopy(frame);mutate(v);run('reject-frame-'+label,dict(mode='read',snapshot=v,fixture=fixture(worker_fault='hang')),3)
    run('legacy-reader-refuses-v2',dict(mode='read-legacy',snapshot=frame,fixture=fixture()),3)
    old_path=Path(__file__).resolve().parents[2]/'.aide/evidence/2026-10-10-identity-queries/reproduction-b853621b/storage-worker-x64/healthy.stdout'
    old=json.loads(old_path.read_bytes())['samples'][-1]['worker']['result'];v=run('retained-v1-still-readable',dict(mode='read-legacy',snapshot=old,fixture=dict(subjects=[disk(),volume()])));check('v1 conformance unchanged',v['snapshot']==old)
    run('v2-reader-refuses-v1',dict(mode='read',snapshot=old,fixture=fixture()),3)
    result=dict(status='pass',pointer_bytes=a.pointer_bytes,controller_executions=len(runs),actual_child_launches=len(children),assertions=len(checks),executions=runs,checks=checks,artifact_sha256='sha256:'+code,owned_identity_fixture_qualified=True,live_storage_qualified=False,physical_access=False,raw_metadata_independently_verified=False,provider_admitted=False,owner_accepted=False,unit_complete=False)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps({k:v for k,v in result.items() if k not in ('executions','checks')}))
if __name__=='__main__':main()
