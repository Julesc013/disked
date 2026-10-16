"""Provisional joined report producer semantics; no file or execution ports."""
import re

def integer(value,label):
    if not isinstance(value,str) or not re.fullmatch(r'(0|[1-9][0-9]{0,19})',value) or int(value)>18446744073709551615:
        raise ValueError('Joined report integer outside u64: '+label)
    return int(value)

def bounds(value,encode,byte_limit,depth_limit,value_limit,string_limit):
    count=0
    def visit(node,depth=0):
        nonlocal count
        count+=1
        if count>value_limit or depth>=depth_limit:raise ValueError('Joined report value/depth bound')
        if isinstance(node,str) and len(node.encode('utf-8'))>string_limit:raise ValueError('Joined report string byte bound')
        if isinstance(node,dict):
            for key,child in node.items():
                if len(key.encode('utf-8'))>string_limit:raise ValueError('Joined report key byte bound')
                visit(child,depth+1)
        elif isinstance(node,list):
            for child in node:visit(child,depth+1)
    visit(value)
    if len(encode(value))>byte_limit:raise ValueError('Joined report canonical byte bound')

def generation(value):
    for key in ('created','volume_id'):integer(value[key],'generation '+key)

def diagnostic(value):
    if value is not None and len(value.encode('utf-8'))>256:raise ValueError('Joined report diagnostic byte bound')

def metadata(value,limit):
    values={k:integer(value[k],'metadata '+k) for k in ('attributes','bytes','changed','created','hardlinks','volume_id','written')}
    if values['attributes']>0xffffffff or values['attributes']&(0x10|0x400|0x1000|0x40000|0x400000) or values['hardlinks']!=1 or not 0<values['bytes']<=limit:
        raise ValueError('Joined report file outside ordinary profile')

def definition(v,encode):
    case=v['sources']['case'];collection=v['sources']['collection'];store=case['store'];report=v['report'];effect=v['effect']
    if case['case_revision']!=report['case_revision'] or collection['collection_revision']!=report['collection_revision']:
        raise ValueError('Joined report source revision mismatch')
    if case['ancestors'][-1]!=store['generation'] or store['failure_domain']!='observed-file-volume:'+store['generation']['volume_id']:
        raise ValueError('Joined report case generation/failure domain mismatch')
    for g in case['ancestors']+[store['generation']]+collection['ancestors']:generation(g)
    for i,f in enumerate(case['files']):metadata(f['metadata'],1048576 if i else 32768)
    metadata(collection['metadata'],1048577)
    if any((f['metadata']['file_id'],f['metadata']['volume_id'])==(collection['metadata']['file_id'],collection['metadata']['volume_id']) for f in case['files']):
        raise ValueError('Joined report source file alias')
    if not 0<integer(effect['artifact']['bytes'],'artifact bytes')<=1048577:raise ValueError('Joined report artifact byte bound')
    d=effect['resources']['destination'];p=effect['resources']['producer']
    if d['identity']==p['identity'] or d['location']==p['location'] or d['location']==collection['path'] or any(d['location']==store['path']+'\\'+child for child in store['children']):
        raise ValueError('Joined report output resource alias')
    bounds(effect,encode,16384,12,512,960);bounds(v,encode,65536,32,8192,960)

def output(v):
    diagnostic(v['diagnostic'])
    counts={k:None if v[k] is None else integer(v[k],k) for k in ('submitted_bytes','written_bytes','read_bytes','verified_bytes')}
    submitted,written,read,verified=(counts[k] for k in ('submitted_bytes','written_bytes','read_bytes','verified_bytes'))
    if any(x is not None and x>1048577 for x in counts.values()) or verified>read or (written is not None and written>submitted):raise ValueError('Joined report output counters contradict')
    if v['output_state']=='not_created' and (any(x!=0 for x in counts.values()) or v['uncertain_effect'] or v['flush']!='not_attempted'):raise ValueError('Uncreated joined report has effects')
    if v['status']=='completed' and (v['phase']!='completed' or v['diagnostic'] is not None or v['output_state']!='created' or v['flush']!='api_confirmed' or v['uncertain_effect'] or None in counts.values() or len(set(counts.values()))!=1 or not submitted):
        raise ValueError('Joined report completion lacks verified output')

def outcome(v,encode):
    diagnostic(v['diagnostic'])
    checks=integer(v['source_checks'],'source checks');sources=v['source_observations']
    if checks>256:raise ValueError('Joined report source visit bound')
    expected={'case':checks if checks%2 else max(checks-1,0),'collection':checks-1 if checks%2 else checks}
    for role in ('case','collection'):
        observed=sources[role];n=integer(observed['check_sequence'],'source sequence')
        if n!=expected[role] or (n==0)!=(observed['state']=='not_observed'):raise ValueError('Joined report source sequence/state contradicts')
    output(v['output'])
    if v['status']=='completed' and (checks<4 or v['diagnostic'] is not None or any(x['state']!='matched' for x in sources.values()) or v['output']['status']!='completed'):raise ValueError('Joined report completion lacks final observations')
    if v['status']=='unknown' and (v['output']['output_state']!='uncertain' or not v['output']['uncertain_effect']):raise ValueError('Unknown joined report lacks uncertainty')
    bounds(v,encode,65536,28,8192,1024)

def worker(v,encode):
    definition(v['export'],encode);store=v['store'];source=v['export']['sources']['case']
    for g in store['ancestors']+[store['generation']]:generation(g)
    if store['ancestors'][-1]!=store['generation'] or store['failure_domain']!='observed-file-volume:'+store['generation']['volume_id'] or store['generation']==source['store']['generation']:
        raise ValueError('Joined report execution store generation/alias')
    if v['export']['effect']['resources']['producer']['digest']!='sha256:'+v['image_digest']:raise ValueError('Joined report worker/producer code mismatch')
    bounds(v,encode,65536,28,8192,1024)

def validate(kind,value,encode):
    {'acquisition-verification-export-definition':definition,'acquisition-verification-export-outcome':outcome,'joined-report-worker-definition':worker}[kind](value,encode)
