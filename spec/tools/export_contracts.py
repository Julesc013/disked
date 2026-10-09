"""Provisional public report producers; pure validation, never execution ports."""
import hashlib
from joined_report_contracts import bounds,integer

JOINED='recorded-acquisition-verification-support-export'
ACQUISITION='recorded-acquisition-case-support-export'

def require(condition,message):
    if not condition:raise ValueError(message)

def digest(value,encode):return 'sha256:'+hashlib.sha256(encode(value)).hexdigest()

def definition(value,encode,semantic):
    joined=value['schema']=='org.disked.report-worker-definition-prototype/2'
    require(joined or value['schema']=='org.disked.report-worker-definition-prototype/1','Unknown report definition version')
    semantic('joined-report-worker-definition' if joined else 'report-worker-definition',value)
    return joined

def execution_parameters(value,encode):
    joined=value['schema']=='org.disked.report-worker-definition-prototype/2'
    flags=['case_read','report_write','store_write','host_effects']+(['collection_read'] if joined else [])
    return dict(phase='execute',definition=value,definition_digest=digest(value,encode),**{'allow_'+key:True for key in flags})

def public_request(parameters,encode):
    # Conservative complete envelope, including worst JSON escaping of the
    # maximum request identity and the LF; this is a projection, not a grant.
    frame=dict(schema='org.disked.request/1',request_id='\x01'*128,command='evidence.export',parameters=parameters,required_features=[])
    bounds(frame,encode,65535,32,8192,32768)

def observed(state,value,d,joined,encode,semantic):
    semantic('report-worker-state',state)
    require(d is not None,'Observed report state has no exact definition')
    b=state['binding']
    require(b['definition_digest']==digest(d,encode) and b['image_digest']==d['image_digest'] and b['host_id']==d['host_id'],'Report state code/definition binding disagrees')
    if 'definition_digest' in value:require(b['definition_digest']==value['definition_digest'],'Report state/reply digest disagrees')
    if 'worker_epoch' in value:require(b['worker_epoch']==value['worker_epoch'],'Report state/watch worker epoch disagrees')
    outcome=state['outcome']
    if outcome is None:return
    require((outcome['schema']=='org.disked.acquisition-verification-export-outcome-prototype/1')==joined,'Report outcome profile disagrees')
    joint=d['export'];effect=joint['effect'];artifact=effect['artifact'];size=integer(artifact['bytes'],'artifact bytes');output=outcome['output']
    for key in ('submitted_bytes','written_bytes','read_bytes','verified_bytes'):
        n=output[key]
        if n is not None:require(integer(n,key)<=size,'Report output exceeds reviewed artifact')
    if output['status']=='completed':require(all(output[k]==artifact['bytes'] for k in ('submitted_bytes','written_bytes','read_bytes','verified_bytes')),'Completed report differs from reviewed artifact')
    receipt=state['receipt']
    if receipt is None:return
    require(receipt['definition_digest']==digest(joint,encode) and not receipt['routing_metadata_is_support_export'],'Report joint receipt disagrees')
    r=receipt['output_receipt']
    if r is None:return
    require(r['definition_digest']==digest(effect,encode) and r['artifact_digest']==artifact['digest'] and not r['routing_metadata_is_support_export'] and r['output_path']==effect['resources']['destination']['location'] and r['producer']==effect['resources']['producer'],'Report output receipt differs from review')
    if r['output_metadata'] is not None:require(integer(r['output_metadata']['bytes'],'output metadata bytes')<=size,'Report receipt exceeds reviewed artifact')

def validate(kind,value,encode,semantic):
    if kind=='export-command-parameters':
        if value['phase']=='execute':
            joined=definition(value['definition'],encode,semantic)
            require(value['definition_digest']==digest(value['definition'],encode),'Report execution digest mismatch')
            require(('allow_collection_read' in value)==joined,'Report authority/profile mismatch')
            public_request(value,encode)
        else:
            require(('collection_path' in value)==('collection_digest' in value),'Report collection selection is incomplete')
            bounds(value,encode,65535,32,8192,32768)
        return
    d=value.get('definition');joined=value['scope']==JOINED
    require(value['scope'] in (JOINED,ACQUISITION),'Unknown report producer scope')
    if d is not None:
        require(definition(d,encode,semantic)==joined,'Report producer scope/version mismatch')
        require(value.get('definition_digest')==digest(d,encode),'Report reply definition digest mismatch')
        if 'state_directory' in value:require(value['state_directory']==d['store']['path'],'Report reply store differs from review')
    bounds(value,encode,1048575,32,131072,32768)
    if kind=='export-preparation-result':
        public_request(execution_parameters(d,encode),encode);return
    for key in ('state','last_validated_state'):
        if value.get(key) is not None:observed(value[key],value,d,joined,encode,semantic)
    if 'cancellation_request' in value:
        state=value.get('state')
        require(state is not None and value['request_kind']=='operation-observation' and (value['cancellation_request']=='too_late')==(state['phase']=='finished'),'Report cancellation request contradicts observation')
    previous=None
    for event in value.get('events',[]):
        semantic('report-operation-event',event);s=event['payload']['record']['state'];observed(s,value,d,joined,encode,semantic)
        if previous is not None:require(s['binding']==previous['binding'] and integer(s['sequence'],'sequence')==integer(previous['sequence'],'sequence')+1,'Report event sequence/binding changed')
        previous=s
    if previous is not None and value.get('state') is not None:require(previous==value['state'],'Report watch state differs from last emitted record')
    if 'last_sequence' in value:require(integer(value['last_sequence'],'watch sequence')<=16,'Report watch cursor bound')
