"""Pure semantic relationships for provisional verification producers.

No paths are opened, no actor is authenticated and no present-day authority is
inferred. Native admission/history/collection validation binds actual resources.
"""
import hashlib,json

U64=(1<<64)-1
MASK=0x10|0x400|0x1000|0x40000|0x400000
COUNTERS=('records','consumed_map_bytes','covered_bytes','read_bytes','source_bytes','substituted_bytes')
def require(ok,reason):
    if not ok:raise ValueError(reason)
def number(v):
    require(isinstance(v,str) and v.isascii() and v.isdecimal() and (v=='0' or not v.startswith('0')),'Invalid verification decimal')
    n=int(v);require(n<=U64,'Verification integer exceeds u64');return n
def limits(v,encode,bytes_=262144,values=65536,depth=48):
    count=0
    def visit(x,d=0):
        nonlocal count
        count+=1;require(count<=values and d<depth,'Verification value/depth bound exceeded')
        if isinstance(x,str):require(len(x.encode('utf-8'))<=32768,'Verification string bound exceeded')
        elif isinstance(x,dict):
            for k,y in x.items():require(len(k.encode('utf-8'))<=32768,'Verification key bound exceeded');visit(y,d+1)
        elif isinstance(x,list):
            for y in x:visit(y,d+1)
    visit(v);require(len(encode(v))<=bytes_,'Verification canonical byte bound exceeded')
def digest(v,encode):return 'sha256:'+hashlib.sha256(encode(v)).hexdigest()
def public_request(p,encode,request='\x01'*128):
    limits(dict(schema='org.disked.request/1',request_id=request,command='image.verify',parameters=p,required_features=[]),encode,65535,8192,32)
def generation(g):number(g['created']);number(g['volume_id'])
def file_resource(v,encode):
    m=v['metadata'];values={k:number(m[k]) for k in ['attributes','bytes','changed','created','hardlinks','volume_id','written']}
    require(values['attributes']<=0xffffffff and not values['attributes']&MASK and values['hardlinks']==1 and values['bytes']<1<<63,'Verification file profile contradicted')
    for p in v['ancestors']:generation(p)
    id_=dict(file_id=m['file_id'],volume_id=m['volume_id']);original=dict(id_,created=m['created'])
    return dict(identity='file:'+digest(id_,encode),epoch=digest(v,encode),recorded_epoch=digest(original,encode),access='read',bytes=m['bytes'])
def duplicates(pairs):
    out={}
    for k,v in pairs:require(k not in out,'Duplicate raw request key');out[k]=v
    return out
def definition(v,encode):
    limits(v,encode);store=v['store'];source=v['case_source'];inner=v['verification'];plan=inner['plan'];resources=inner['resources']
    require(v['verification_digest']==digest(inner,encode) and inner['plan_digest']==digest(plan,encode),'Verification definition digest disagrees')
    require(store['ancestors'][-1]==store['generation'] and store['generation']!=source['store']['generation'] and store['failure_domain']=='observed-file-volume:'+store['generation']['volume_id'],'Verification store generation/alias/failure domain disagrees')
    for p in store['ancestors']+[store['generation']]+source['ancestors']+[source['store']['generation']]:generation(p)
    for f in source['files']:
        m=f['metadata'];values={k:number(m[k]) for k in ['attributes','bytes','changed','created','hardlinks','volume_id','written']}
        require(values['attributes']<=0xffffffff and not values['attributes']&MASK and values['hardlinks']==1,'Case metadata profile disagrees')
    require(source['ancestors'][-1]==source['store']['generation'] and source['store']['failure_domain']=='observed-file-volume:'+source['store']['generation']['volume_id'],'Case store generation/failure domain disagrees')
    require(number(source['files'][0]['metadata']['bytes'])<=32768 and number(source['files'][1]['metadata']['bytes'])<=1048576,'Case metadata byte bound exceeded')
    raw=v['request_raw'].encode('utf-8');h=json.loads(v['request_raw'],object_pairs_hook=duplicates);original=h['definition']
    require(h['schema']=='org.disked.acquisition-worker-request/1' and original['schema']=='org.disked.acquisition-worker-definition/1' and h['operation_id']==v['case_operation_id'] and original['plan']==plan and original['store']==source['store'],'Raw case request selection disagrees')
    require(len(raw)<=32768 and number(source['files'][0]['metadata']['bytes'])==len(raw) and source['files'][0]['digest']=='sha256:'+hashlib.sha256(raw).hexdigest(),'Raw case request bytes/hash disagree')
    require(h['definition_digest']==digest(original,encode)==h['grant']['definition_digest'] and all(h['grant'][k] is True for k in ['source_read','destination_write','map_write','host_effects']),'Original request/grant definition disagrees')
    require({k:file_resource(v['image_binding'][k],encode) for k in ['image','map']}==resources,'Current verification resource/binding disagrees')
    require(resources['image']['identity']!=resources['map']['identity'] and number(resources['map']['bytes'])<=17180917760,'Verification resource alias/map bound')
    for role in ['image','map']:
        f=v['image_binding'][role]
        if f['ancestors'][-1]==store['generation']:require(f['path'].rsplit('\\',1)[-1].lower() not in store['children'],'Verification fixed-store alias')
    for r in plan['resources'].values():
        for key in ['start','end']:
            if key in r:number(r[key])
    for k in ['bytes','chunk_bytes','retry_limit']:
        if k in plan:number(plan[k])
def outcome(o,encode,d=None):
    limits(o,encode,65536,8192);n={k:number(o[k]) for k in COUNTERS+('matched_bytes',)}
    require(n['records']<=1048576 and n['consumed_map_bytes']<=17180917760 and n['records']<=n['consumed_map_bytes']//2 and n['covered_bytes']==n['matched_bytes'] and n['read_bytes']>=n['matched_bytes'] and n['source_bytes']<=n['covered_bytes'] and n['substituted_bytes']==n['covered_bytes']-n['source_bytes'],'Verification outcome counters disagree')
    require(o['before'] is not None or not any(n.values()) and not o['sealed'] and not o['pending'],'Unobserved verification prefix')
    if o['sealed']:require(not o['pending'] and n['records']>=2,'Contradictory verification seal')
    state=o['resource_revalidation']
    if state=='passed':require(o['before'] is not None and o['after']==o['before'],'Verification passed resources disagree')
    elif state in ['changed','unavailable']:
        require(o['status']=='unknown','Uncertain resource state promotes verification')
        require(o['after'] is None if state=='unavailable' else o['after'] is not None and o['after']!=o['before'],'Verification resource revalidation contradicts observation')
    elif state=='not_attempted':require(o['before'] is None and o['after'] is None and not any(n.values()) and not o['sealed'] and not o['pending'] and o['status'] in ['refused','unknown'],'Unattempted verification has effects')
    if o['status']=='matched':
        require(state=='passed' and o['sealed'] and not o['pending'] and not o['diagnostic'] and n['records']>=2 and number(o['before']['image']['bytes'])==n['covered_bytes'] and number(o['before']['map']['bytes'])==n['consumed_map_bytes'],'Verification match lacks coverage')
    if d:
        resources=d['verification']['resources'];size=number(d['verification']['plan']['bytes'])
        require(n['covered_bytes']<=size and (not o['sealed'] or n['covered_bytes']==size) and (o['before'] is None or o['before']==resources),'Verification outcome differs from definition')
        if state=='passed':require(o['after']==resources,'Verification after differs from definition')
def state(s,encode,d=None):
    limits(s,encode,65536,8192);b=s['binding'];require(1<=number(s['sequence'])<=32 and 1<=number(b['process_id'])<=0xffffffff and number(b['process_created'])>0 and number(s['observed_filetime'])>0,'Verification identity/sequence bound')
    phase=s['phase'];p=s['progress'];n={k:number(p[k]) for k in COUNTERS};r=s['retention'];o=s['outcome']
    require(n['records']<=1048576 and n['consumed_map_bytes']<=17180917760 and n['records']<=n['consumed_map_bytes']//2 and n['read_bytes']>=n['covered_bytes'] and n['source_bytes']<=n['covered_bytes'] and n['substituted_bytes']==n['covered_bytes']-n['source_bytes'],'Verification progress counters disagree')
    require(s['quiescent']==(phase=='finished') and (phase=='finished' or s['disposition']=='running'),'Verification phase/quiescence/disposition disagree')
    if phase=='prepared':require(not any(n.values()),'Prepared verification has progress')
    if o is not None:
        outcome(o,encode,d);require(all(p[k]==o[k] for k in COUNTERS),'Verification progress/outcome disagree')
    if phase in ['prepared','verifying']:require(o is None and r['state']=='empty','Active verification has terminal effects')
    if r['bytes'] is not None:require(number(r['bytes'])<=1048577,'Verification retention bound')
    if r['state']=='empty':require(r['bytes']=='0' and r['flush']=='not_attempted' and all(r[k] is None for k in ['digest','collection_revision','observation_revision']),'Empty verification retention has effects')
    if phase=='persisting':require(o is not None and r['state']=='in_flight','Persisting verification has no actual outcome')
    if r['state']=='verified':require(phase=='finished' and o is not None and r['bytes'] is not None and number(r['bytes'])>0 and r['flush']=='api_confirmed' and all(r[k] is not None for k in ['digest','collection_revision','observation_revision']),'Verified retention lacks terminal evidence')
    if phase=='finished':
        require(s['disposition'] in ['completed','cancelled','refused','unknown'],'Terminal verification has running disposition')
        require(r['state']!='in_flight' and (o is None or r['state']!='empty'),'Terminal verification retention unresolved')
        if s['disposition']=='completed':require(o is not None and r['state']=='verified' and o['status'] not in ['cancelled','unknown'],'Completed verification has uncertain effects')
        if s['disposition']=='cancelled':require(s['cancellation_observation']=='observed' and (o is None or o['status']=='cancelled'),'Cancelled verification lacks observation')
    if d:
        require(b['definition_digest']==digest(d,encode) and b['host_id']==d['host_id'] and b['verifier']==d['verifier'],'Verification state code/definition binding disagrees')
        require(n['covered_bytes']<=number(d['verification']['plan']['bytes']) and n['consumed_map_bytes']<=number(d['verification']['resources']['map']['bytes']),'Verification state exceeds resources')
def validate(kind,v,encode):
    if kind=='verification-worker-definition':definition(v,encode)
    elif kind=='acquired-image-verification-outcome':outcome(v,encode)
    elif kind=='verification-worker-state':state(v,encode)
    elif kind=='verification-worker-record':
        state(v['state'],encode);limits(v,encode,65536,8192)
        require(hashlib.sha256(encode({k:x for k,x in v.items() if k!='digest'})).hexdigest()==v['digest'],'Verification record digest mismatch')
        if v['state']['sequence']=='1':require(v['state']['phase']=='prepared' and v['previous']=='0'*64,'Verification first record is unanchored')
    elif kind=='verification-operation-event':
        validate('verification-worker-record',v['payload']['record'],encode);limits(v,encode,67584,8256)
        s=v['payload']['record']['state'];require(v['operation_id']==s['binding']['operation_id'] and v['sequence']==s['sequence'],'Verification event identity/sequence mismatch')
        require('\0' not in v['payload']['request_id'] and len(v['payload']['request_id'].encode('utf-8'))<=128,'Verification observer request identity')
    elif kind=='verification-command-parameters':
        if v['phase']=='execute':definition(v['definition'],encode);limits(v['definition'],encode,65536,8192,32)
        # Actual request identity/envelope is validated by its owning transport.
        limits(v,encode,65535,8192,32)
    elif kind=='verification-preparation-result':
        definition(v['definition'],encode);require(v['definition_digest']==digest(v['definition'],encode),'Verification preparation digest mismatch');limits(v['definition'],encode,65536,8192,32)
        public_request(dict(phase='execute',definition=v['definition'],definition_digest=v['definition_digest'],**{'allow_'+n:True for n in ['case_read','image_read','map_read','store_write','host_effects','private_metadata']}),encode)
    elif kind=='verification-operation-result':
        d=v.get('definition');s=v.get('state')
        if d:definition(d,encode);require(v.get('definition_digest')==digest(d,encode),'Verification reply definition mismatch')
        if s:
            require(d is not None,'Verification state has no definition');state(s,encode,d)
            require(v.get('request_binding')=={k:x for k,x in s['binding'].items() if k not in ['process_id','process_created']},'Verification retained request binding disagrees')
        elif 'request_binding' in v:require(False,'Request binding has no observed state')
        if 'collection_validation' in v:require(s is not None and s['retention']['state']=='verified' and 'attachment_applicability' in v,'Collection verification lacks retained evidence')
        if 'attachment_applicability' in v:require('collection_validation' in v,'Attachment has no validated collection')
        if 'cancellation_request' in v:require(s is not None and v['request_kind']=='operation-observation' and (v['cancellation_request']=='too_late')==(s['phase']=='finished'),'Cancellation request contradicts state')
        for e in v.get('events',[]):validate('verification-operation-event',e,encode)
        if 'last_sequence' in v:require(number(v['last_sequence'])<=32,'Verification watch cursor bound')
        if v.get('last_validated_state') is not None:
            require(d is not None,'Last validated verification state has no definition');state(v['last_validated_state'],encode,d)
