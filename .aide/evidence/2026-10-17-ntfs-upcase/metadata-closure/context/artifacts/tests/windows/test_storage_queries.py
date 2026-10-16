"""Independent binary Win32 query fixtures; no live storage handles or queries."""
import argparse,copy,hashlib,json,struct,subprocess
from pathlib import Path

def packet(b=b'',*,ok=True,error=0,returned=None):return dict(hex=b.hex(),ok=ok,error=str(error),returned=str(len(b) if returned is None else returned))
def descriptor(vendor=b'Vendor',product=b'Product',revision=b'1',serial=b'SERIAL',raw=b'',size=None):
    b=bytearray(max(40,36+len(raw)));b[36:36+len(raw)]=raw
    for index,value in enumerate((vendor,product,revision,serial)):
        if value is not None:struct.pack_into('<I',b,12+index*4,len(b));b.extend(value+b'\0')
    struct.pack_into('<II',b,0,40,len(b) if size is None else size);b[10]=1;struct.pack_into('<II',b,28,7,len(raw));return bytes(b)
def disk(key='disk',number=0,*,size=1048576,serial=b'SERIAL'):
    d=descriptor(serial=serial)
    return dict(key=key,kind='disk',replies=dict(descriptor=[packet(d[:8]),packet(d)],number=[packet(struct.pack('<III',7,number,0))],
        geometry=[packet(struct.pack('<QIIIIQ',0,12,0,0,512,size))],length=[packet(struct.pack('<Q',size))]))
def extent_bytes(rows):return struct.pack('<I4x',len(rows))+b''.join(struct.pack('<I4xQQ',*r) for r in rows)
def volume(key='volume',rows=((0,4096,8192),),size=8192):
    b=extent_bytes(rows);replies=[packet(b)] if len(rows)<=1 else [packet(b[:32],ok=False,error=234),packet(b)]
    return dict(key=key,kind='volume',replies=dict(number=[packet(struct.pack('<III',7,99,1))],length=[packet(struct.pack('<Q',size))],extents=replies))
def request(*subjects,**kw):return dict(subjects=list(subjects),**kw)
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
def digest(v):return 'sha256:'+hashlib.sha256(canonical(v)).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--pointer-bytes',type=int,choices=(4,8),required=True);a=p.parse_args();a.output.mkdir();checks=[];executions=[]
    def check(label,ok):
        checks.append(dict(label=label,passed=bool(ok)));assert ok,label
    def run(label,value,expected=0):
        raw=json.dumps(value,ensure_ascii=True,separators=(',',':')).encode();(a.output/(label+'.request.json')).write_bytes(raw)
        v=subprocess.run([str(a.probe.resolve())],input=raw,capture_output=True,timeout=15)
        (a.output/(label+'.stdout')).write_bytes(v.stdout);(a.output/(label+'.stderr')).write_bytes(v.stderr)
        executions.append(dict(label=label,exit_code=v.returncode,expected_exit=expected));check(label+' exact exit',v.returncode==expected and not v.stderr);r=json.loads(v.stdout)
        check(label+' actual pointer width',r['pointer_bytes']==str(a.pointer_bytes))
        if 'frame' in r:
            f=r['frame'];g=r['graph'];check(label+' frame capture and no authority',f['api_binding']=='injected-win32-table' and f['claims']['physical_identity']=='unknown' and not f['claims']['physical_admission'] and not f['claims']['mutation_authority'] and f['claims']['capture_consistency']=='sequential-not-atomic')
            check(label+' fixture context bound',r['fixture_context_digest']==digest(value));unbound=copy.deepcopy(g);revision=unbound.pop('revision');check(label+' graph digest',revision==digest(unbound))
            for n in g['nodes']:
                q=n['properties'];check(label+' unknown media and no authority',q['identity'] is None and q['media_generation'] is None and q['capacity_bytes'] is None and q['aliases']==[] and q['physical_identity']=='unknown' and not q['physical_admission'] and not q['mutation_authority'])
                binding=q['observation_binding'];check(label+' exact frame/context binding',binding['frame_digest']==digest(f) and binding['context_digest']==r['fixture_context_digest'] and binding['source']=='storage' and binding['capture_epoch']==f['capture_epoch'])
                check(label+' observation ID independently calculated',n['id']=='observation:'+digest(dict(binding=binding,kind=n['kind'],label=q['label'],payload=q['observation']))[7:])
                check(label+' inert display',all(32<=ord(c)<=126 for c in q['label']))
            check(label+' distinct observation IDs',len({n['id'] for n in g['nodes']})==len(g['nodes']))
            check(label+' no physical backing edges',all(e['kind']=='contains' for e in g['edges']))
            for row in f['resources']:
                for c in row['components'].values():
                    for reply in c['receipts']:
                        if reply['returned_hex'] is not None:
                            b=bytes.fromhex(reply['returned_hex']);check(label+' exact returned byte binding',len(b)==int(reply['returned_bytes']) and reply['returned_sha256']=='sha256:'+hashlib.sha256(b).hexdigest())
            # Independent control-code values, including exact input query size.
            codes=dict(descriptor=0x2d1400,number=0x2d1080,geometry=0x700a0,length=0x7405c,extents=0x560000)
            check(label+' exact documented controls and arguments',all(int(x['control'])==codes[x['component']] and int(x['input_bytes'])==(12 if x['component']=='descriptor' else 0) for x in r['trace']))
        return r
    def component(v,name,subject=0):return v['frame']['resources'][subject]['components'][name]
    def state(v,name,expected,subject=0):check(name+' state '+expected,component(v,name,subject)['state']==expected)

    v=run('healthy-joined',request(disk(),volume()));check('healthy selected queries complete',v['frame']['status']=='selected_queries_complete' and v['api_calls']=='8')
    e=component(v,'extents',1)['data'][0];check('extent lookup only',e['lookup_state']=='unique-number-observation-only' and e['candidate_subjects']==['disk'] and e['range_state']=='within-observed-capacity')
    check('no inferred physical sector',component(v,'geometry')['data']['physical_sector_bytes'] is None)
    check('disk number is not durable identity',component(v,'number')['data']['identity_scope']=='transient-lookup-only')
    run('construction-inert',request(disk(),mode='construction'))
    for mode in ('native','mixed-io','mixed-error'):
        v=run('reject-'+mode,request(disk(),api=mode),3);check(mode+' refused before dispatch',v['api_calls']=='0' and v['error_calls']=='0')
    for field,value in [('descriptor_bytes','39'),('descriptor_bytes','4097'),('string_bytes','0'),('string_bytes','257'),('extents','0'),('extents','65')]:
        policy=dict(descriptor_bytes='4096',string_bytes='256',extents='64');policy[field]=value
        v=run('invalid-'+field+'-'+value,request(disk(),policy=policy),3);check('invalid policy no dispatch',v['api_calls']=='0')
    for label,value in [('zero-capture',request(disk(),capture='0')),('duplicate-key',request(disk(),disk())),('empty-key',request(dict(disk(),key=''))),('invalid-handle',request(dict(disk(),invalid_handle=True))),('invalid-kind',request(dict(disk(),kind='writer'))),('subjects-limit',request(*(disk('d'+str(i),i) for i in range(17))))]:
        v=run(label,value,3);check(label+' no dispatch',v['api_calls']=='0')
    v=run('query-not-reused',request(disk(),mode='reuse'),3);check('one descriptor query only',v['api_calls']=='2')
    for error,expected in [(5,'denied'),(50,'unsupported'),(1,'unsupported'),(1167,'unavailable')]:
        d=disk();d['replies']['descriptor']=[packet(ok=False,error=error)];v=run('transport-'+str(error),request(d));state(v,'descriptor',expected)
        check('immediate error retained and other queries continue',component(v,'descriptor')['platform_code']==str(error) and component(v,'length')['state']=='observed' and v['error_calls']=='1')
    for label,returned in [('pending-is-unresolved',0),('pending-with-invalid-count',9)]:
        d=disk();d['replies']['descriptor']=[packet(ok=False,error=997,returned=returned)];v=run(label,request(d,volume()));state(v,'descriptor','unresolved')
        check('pending stops reuse and later subjects',v['api_calls']=='1' and v['frame']['status']=='unresolved' and component(v,'descriptor')['receipts'][0]['returned_bytes']==str(returned) and all(x['state'] in ('not_attempted','not_selected') for x in v['frame']['resources'][1]['components'].values()))
    d=disk();d['replies']['descriptor']=[dict(packet(),throw=True)];v=run('callback-exception',request(d));state(v,'descriptor','adapter_exception');check('exception is not retirement',v['api_calls']=='1' and v['frame']['status']=='unresolved')
    for after,calls in [(0,0),(1,1),(2,2),(3,3)]:
        v=run('cancel-'+str(after),request(disk(),volume(),cancel_after_io=str(after)));check('cancel stops at checkpoint',v['api_calls']==str(calls) and v['frame']['status']=='cancelled')
    changes={
        'bad-offset':lambda b:struct.pack_into('<I',b,24,len(b)),
        'header-offset':lambda b:struct.pack_into('<I',b,24,4),
        'unterminated':lambda b:b.__setitem__(-1,65),
        'raw-overrun':lambda b:struct.pack_into('<I',b,32,len(b)),
        'changed-size':lambda b:struct.pack_into('<I',b,4,len(b)-1),
        'changed-version':lambda b:struct.pack_into('<I',b,0,44),
    }
    for label,mutate in changes.items():
        d=disk();b=bytearray.fromhex(d['replies']['descriptor'][1]['hex']);mutate(b);d['replies']['descriptor'][1]=packet(b)
        v=run(label,request(d));state(v,'descriptor','changed' if label.startswith('changed-') else 'malformed');check('bad descriptor retains independent length',component(v,'length')['state']=='observed')
    for label,first in [('short-header',packet(b'1234')),('oversized-header',packet(struct.pack('<II',40,8192))),('invalid-size',packet(struct.pack('<II',40,0))),('unknown-version',packet(struct.pack('<II',44,64))),('overreported-header',packet(b'12345678',returned=9))]:
        d=disk();d['replies']['descriptor']=[first];v=run(label,request(d));state(v,'descriptor','budget_exhausted' if label=='oversized-header' else 'unsupported_version' if label=='unknown-version' else 'malformed')
    d=disk();d['replies']['descriptor'][0].update(ok=False,error='234');v=run('descriptor-more-data-header',request(d));state(v,'descriptor','observed')
    d=disk();d['replies']['descriptor'][1]=packet(ok=False,error=234);v=run('descriptor-no-growth-loop',request(d));state(v,'descriptor','changed');check('descriptor at most two calls',sum(x['component']=='descriptor' for x in v['trace'])==2)
    d=disk();b=descriptor(vendor=None,product=b'',revision=b'\x1b[31m',serial=b'A\x80\x00',raw=b'opaque');d['replies']['descriptor']=[packet(b[:8]),packet(b)];v=run('lossless-byte-metadata',request(d));q=component(v,'descriptor')['data']
    check('missing versus empty distinct',q['vendor']['state']=='absent' and q['product']['state']=='empty');check('non-ASCII and controls preserved inertly',q['serial']['original_hex']=='4180' and q['serial']['display']=='A\\x80' and q['revision']['display']=='\\x1b[31m' and v['frame']['status']=='partial')
    d=disk();d['label_units']=['68','27','55296','8238'];v=run('lossless-label',request(d));check('original UTF16 label bytes',v['frame']['resources'][0]['label']['original_hex']=='44001b0000d82e20' and v['graph']['nodes'][0]['properties']['label']=='D\\u001b\\ud800\\u202e')
    for label,b in [('negative-geometry',struct.pack('<QIIIIQ',1<<63,12,0,0,512,1000)),('negative-capacity',struct.pack('<QIIIIQ',0,12,0,0,512,1<<63)),('zero-sector',struct.pack('<QIIIIQ',0,12,0,0,0,1000)),('truncated-geometry',b'1234')]:
        d=disk();d['replies']['geometry']=[packet(b)];v=run(label,request(d));state(v,'geometry','malformed')
    d=disk();d['replies']['geometry']=[packet(struct.pack('<QIIIIQ',0,12,0,0,520,1048576))];v=run('non-power-two-sector',request(d));check('520-byte sectors retained',component(v,'geometry')['data']['logical_sector_bytes']=='520')
    for label,b in [('negative-length',struct.pack('<Q',1<<63)),('short-length',b'1234')]:
        d=disk();d['replies']['length']=[packet(b)];v=run(label,request(d));state(v,'length','malformed')
    d=disk();d['replies']['length']=[packet(struct.pack('<Q',1048000))];v=run('capacity-disagreement',request(d,volume()));check('disagreement retained',v['frame']['resources'][0]['conflicts']['capacity_disagreement'] and v['frame']['status']=='partial' and component(v,'extents',1)['data'][0]['range_state']=='unknown')
    v=run('duplicate-identifiers',request(disk('a'),disk('b'),volume()));check('cloned serial and numbers are conflicts not merge',len(v['graph']['nodes'])==4 and all(r['conflicts']['duplicate_serial_candidate'] and r['conflicts']['duplicate_device_number'] for r in v['frame']['resources'][:2]) and component(v,'extents',2)['data'][0]['lookup_state']=='ambiguous')
    v=run('unresolved-number',request(volume(rows=((123,0,1),))));check('unresolved disk reference kept',component(v,'extents')['data'][0]['candidate_subjects']==[] and v['frame']['status']=='partial')
    v=run('outside-capacity',request(disk(),volume(rows=((0,1048576,1),))));check('range conflict retained',component(v,'extents',1)['data'][0]['range_state']=='exceeds-observed-capacity' and v['frame']['status']=='partial')
    v=run('spanned-volume',request(disk('a',0,serial=b'A'),disk('b',1,serial=b'B'),volume(rows=((0,0,4096),(1,8192,4096)))));check('all extents preserved',len(component(v,'extents',2)['data'])==2 and len(v['graph']['edges'])==2 and v['frame']['status']=='selected_queries_complete')
    v=run('empty-extents',request(volume(rows=())));state(v,'extents','observed');check('empty extent observation is not a physical identity',component(v,'extents')['data']==[] and len(v['graph']['nodes'])==1)
    for label,rows in [('negative-offset',((0,1<<63,1),)),('zero-range',((0,0,0),)),('signed-end-overflow',((0,(1<<63)-1,1),))]:
        v=run(label,request(volume(rows=rows)));state(v,'extents','malformed')
    for label,replies,expected in [
        ('missing-extent-header',[packet(b'\x02',ok=False,error=234)],'malformed'),
        ('growth-count-one',[packet(struct.pack('<I',1),ok=False,error=234)],'malformed'),
        ('extent-count-budget',[packet(struct.pack('<I',65),ok=False,error=234)],'budget_exhausted'),
        ('repeated-more-data',[packet(struct.pack('<I',2),ok=False,error=234),packet(struct.pack('<I',3),ok=False,error=234)],'changed'),
        ('changed-extent-count',[packet(struct.pack('<I',2),ok=False,error=234),packet(extent_bytes(((0,0,1),)))],'changed'),
        ('truncated-extent',[packet(struct.pack('<I4x',1))],'malformed')]:
        vol=volume();vol['replies']['extents']=replies;v=run(label,request(vol));state(v,'extents',expected);check('extent growth bounded',sum(x['component']=='extents' for x in v['trace'])<=2)
    v=run('maximum-extents',request(volume(rows=tuple((i,i*4096,4096) for i in range(64)))));check('64 extents exact',len(component(v,'extents')['data'])==64 and len(v['graph']['nodes'])==65)
    v=run('batch-extent-budget',request(*(volume('v'+str(i),tuple((j,j*4096,4096) for j in range(64))) for i in range(3))))
    check('128 extents budget stops next query',sum(len(c['data']) for r in v['frame']['resources'] for c in [r['components']['extents']] if c['state']=='observed')==128 and component(v,'extents',2)['state']=='budget_exhausted' and len(v['graph']['nodes'])==131)
    check('extent receipt retains pre-query budget', [r['selected_extent_limit'] for r in v['frame']['resources']]==['64','64','0'])
    d=disk();b=bytearray(4096);struct.pack_into('<II',b,0,40,4096);struct.pack_into('<I',b,32,4060);d['replies']['descriptor']=[packet(b[:8]),packet(b)];v=run('maximum-descriptor',request(d));check('opaque properties exact bounded',len(component(v,'descriptor')['data']['raw_properties_hex'])==8120)
    v=run('maximum-subjects',request(*(disk('d'+str(i),i,serial=('S'+str(i)).encode()) for i in range(16))));check('16 subjects at most 80 queries',v['api_calls']=='80' and len(v['graph']['nodes'])==16)
    result=dict(status='pass',qualification='injected Win32 IOCTL port and immutable private storage observation graph',pointer_bytes=a.pointer_bytes,native_executions=len(executions),assertions=len(checks),checks=checks,executions=executions,
        probe_sha256='sha256:'+hashlib.sha256(a.probe.read_bytes()).hexdigest(),live_storage_qualified=False,physical_access=False,worker_containment_qualified=False,provider_admitted=False,historical_windows_qualified=False,owner_accepted=False,unit_complete=False)
    (a.output/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps({k:v for k,v in result.items() if k not in ('checks','executions')}))

if __name__=='__main__':main()
