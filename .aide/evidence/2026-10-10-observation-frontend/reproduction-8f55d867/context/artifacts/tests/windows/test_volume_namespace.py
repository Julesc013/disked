"""Independent native API-response fixtures; no host/device namespace query."""
import argparse,copy,hashlib,json,subprocess
from pathlib import Path

def units(text):
    raw=text.encode('utf-16le','surrogatepass')
    return [str(int.from_bytes(raw[i:i+2],'little')) for i in range(0,len(raw),2)]
def name(text):return units(text+'\0')
def representation(text):
    return dict(original_encoding='utf16le-code-units',original_hex=text.encode('utf-16le','surrogatepass').hex(),
                display_encoding='ascii-with-utf16-unit-escapes',
                display=''.join(chr(int(x)) if 32<=int(x)<=126 else '\\u'+format(int(x),'04x') for x in units(text)))
VOLUME='\\\\?\\Volume{12345678-1234-abcd-abcd-123456789abc}\\'
OTHER='\\\\?\\Volume{87654321-1234-abcd-abcd-123456789abc}\\'
CLAIMS=dict(physical_identity='unknown',full_topology='not_observed',media_preservation='not_established',
            physical_admission=False,mutation_authority=False,complete_alias_proof=False)
def reply(paths=(),*,error=0,ok=True,copied=None,raw=None):
    data=units(''.join(x+'\0' for x in paths)+'\0') if raw is None else raw
    return dict(units=data,copied=str(len(data) if copied is None else copied),error=str(error),ok=ok)
def fixture(names=(VOLUME,),mounts=None,**changes):
    return dict(dict(names=[name(x) for x in names],terminal_error='18',close_error='0',
                     mount_replies=[[reply(('C:\\',))] for _ in names] if mounts is None else mounts,
                     volume_limit='64',mount_limit='64',unit_limit='8192',include_mounts=True,
                     capture_epoch='1',cancel_after_calls='4294967295'),**changes)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--pointer-bytes',type=int,required=True,choices=(4,8))
    args=parser.parse_args();probe=args.probe.absolute();out=args.output.absolute();out.mkdir();checks=[];executions=[]
    def check(label,condition):
        checks.append(dict(label=label,passed=bool(condition)))
        assert condition,label
    def run(label,value=None,expected=0,options=()):
        data=None if value is None else json.dumps(value,separators=(',',':'),ensure_ascii=True).encode()
        result=subprocess.run([str(probe),*options],input=data,capture_output=True,timeout=15)
        (out/(label+'.stdout')).write_bytes(result.stdout);(out/(label+'.stderr')).write_bytes(result.stderr)
        if data is not None:(out/(label+'.request.json')).write_bytes(data)
        executions.append(dict(label=label,command=[str(probe),*options],exit_code=result.returncode,expected_exit=expected))
        check(label+'-actual-exit',result.returncode==expected and not result.stderr)
        if not result.stdout:return None
        actual=json.loads(result.stdout)
        if expected==0 and value is not None:
            s=actual['snapshot'];check(label+'-fixed-claims',s['claims']==CLAIMS and s['api_binding']=='injected-win32-table')
            check(label+'-no-restart-or-close-retry',actual['reuse_refused'] and actual['close_calls'] in ('0','1'))
            check(label+'-unique-observation-ids',len({x['observation_id'] for x in s['records']})==len(s['records']))
            check(label+'-no-native-storage-claim',actual['qualification']=='injected-win32-api-not-native-storage')
        return actual
    binding=run('native-table-construction',options=('--binding',))
    check('bound-native-table-without-dispatch',binding['queries']==0 and binding['native_table_bound'] and not binding['live_namespace_qualified'] and binding['pointer_bytes']==args.pointer_bytes)
    run('unknown-invocation',expected=2,options=('--live',))
    for label,error,status in [('empty',18,'complete'),('first-denied',5,'denied'),('first-unavailable',1167,'unavailable')]:
        a=run(label,fixture(names=(),terminal_error=str(error)))
        check(label+'-not-empty-success',a['snapshot']['status']==status and not a['snapshot']['records'] and a['close_calls']=='0')
    a=run('one-complete',fixture());s=a['snapshot'];r=s['records'][0]
    check('exact-original-volume-and-mount',r['volume_path']==representation(VOLUME) and r['mounts']['paths']==[representation('C:\\')])
    check('complete-only-enumeration-scope',s['status']=='complete' and s['scope']=='volume-namespace-only' and s['enumeration']['exhausted'] and a['close_calls']=='1')
    check('exact-native-dispatch-order',[x['api'] for x in a['trace']]==['FindFirstVolumeW','GetVolumePathNamesForVolumeNameW','FindNextVolumeW','GetLastError','FindVolumeClose'])
    check('mount-query-original-name',a['trace'][1]['queried_name']==representation(VOLUME))
    for raw in (['0'],['0','0']):
        a=run('empty-mounts-'+str(len(raw)),fixture(mounts=[[reply(raw=raw)]]))
        check('empty-mounts-observed-'+str(len(raw)),a['snapshot']['status']=='complete' and a['snapshot']['records'][0]['mounts']['paths']==[])
    a=run('mounts-not-selected',fixture(include_mounts=False));check('no-implicit-mount-query',all(x['api']!='GetVolumePathNamesForVolumeNameW' for x in a['trace']))
    for label,change in [('removed-after-volume',dict(terminal_error='1167')),('denied-after-volume',dict(terminal_error='5'))]:
        a=run(label,fixture(**change));check(label+'-prior-retained',a['snapshot']['status']=='partial' and len(a['snapshot']['records'])==1 and not a['snapshot']['enumeration']['exhausted'])
    a=run('mount-denied',fixture(mounts=[[reply(ok=False,error=5)]]));check('denied-volume-still-present',a['snapshot']['status']=='partial' and a['snapshot']['records'][0]['mounts']['state']=='denied')
    a=run('invalid-volume-name',fixture(names=('do-not-follow-physical-path',)));check('malformed-name-never-queried',a['snapshot']['records'][0]['state']=='malformed' and all(x['api']!='GetVolumePathNamesForVolumeNameW' for x in a['trace']))
    value=fixture();value['names']=[['65']*64];a=run('missing-name-nul',value);check('name-buffer-bounded',a['snapshot']['enumeration']['state']=='malformed' and a['close_calls']=='1')
    for label,first,second,state in [
        ('inconsistent-growth',reply(ok=False,error=234,copied=128),None,'malformed'),
        ('oversized-growth',reply(ok=False,error=234,copied=4097),None,'budget_exhausted'),
        ('second-growth',reply(ok=False,error=234,copied=140),reply(ok=False,error=234,copied=200),'changed'),
        ('growth-success',reply(ok=False,error=234,copied=140),reply(('D:\\',)),'observed')]:
        a=run(label,fixture(mounts=[[first] if second is None else [first,second]]));r=a['snapshot']['records'][0]
        check(label+'-finite-growth',r['mounts']['state']==state and sum(x['api']=='GetVolumePathNamesForVolumeNameW' for x in a['trace'])==(1 if second is None else 2))
        if second is not None:check(label+'-exact-required-buffer',[x['buffer_units'] for x in a['trace'] if x['api']=='GetVolumePathNamesForVolumeNameW']==['128','140'])
    for label,raw,copied in [('zero-count',[],0),('out-of-buffer',[],129),('missing-mount-nul',['65'],1),('missing-extra-nul',units('C:\\\0'),4),('trailing-data',units('C:\\\0\0X\0'),7)]:
        a=run(label,fixture(mounts=[[reply(raw=raw,copied=copied)]]));check(label+'-reject-partial-buffer',a['snapshot']['records'][0]['mounts']['state']=='malformed' and not a['snapshot']['records'][0]['mounts']['paths'])
    text='C:\\'+chr(27)+'[2J'+chr(0x202e)+chr(0xd800)+chr(0xd83d)+chr(0xde00)+'\\'
    a=run('lossless-hostile-presentation',fixture(mounts=[[reply((text,))]]));r=a['snapshot']['records'][0]
    check('exact-utf16-and-inert-ascii',r['mounts']['paths']==[representation(text)] and '\\u001b' in r['mounts']['paths'][0]['display'] and '\\ud800' in r['mounts']['paths'][0]['display'])
    a=run('duplicate-volume-guid',fixture(names=(VOLUME,VOLUME.lower())));check('cloned-volume-name-not-merged',len(a['snapshot']['records'])==2 and all(x['conflicts']['duplicate_volume_name'] for x in a['snapshot']['records']) and a['snapshot']['status']=='partial')
    a=run('duplicate-mount-across-volumes',fixture(names=(VOLUME,OTHER),mounts=[[reply(('C:\\',))],[reply(('c:\\',))]]));check('conflicting-alias-not-merged',all(x['conflicts']['duplicate_mount_alias'] for x in a['snapshot']['records']))
    a=run('duplicate-mount-within-volume',fixture(mounts=[[reply(('C:\\','c:\\'))]]));check('duplicate-alias-preserved',len(a['snapshot']['records'][0]['mounts']['paths'])==2 and a['snapshot']['records'][0]['conflicts']['duplicate_mount_alias'])
    a=run('volume-budget',fixture(volume_limit='1'));check('budget-stops-before-next',a['snapshot']['enumeration']['state']=='budget_exhausted' and all(x['api']!='FindNextVolumeW' for x in a['trace']))
    a=run('mount-count-budget',fixture(mount_limit='1',mounts=[[reply(('C:\\','D:\\'))]]));check('mount-list-not-truncated',a['snapshot']['records'][0]['mounts']['state']=='budget_exhausted' and not a['snapshot']['records'][0]['mounts']['paths'])
    a=run('unit-budget-before-growth',fixture(unit_limit='128',mounts=[[reply(ok=False,error=234,copied=140)]]));check('remaining-unit-budget-no-retry',sum(x['api']=='GetVolumePathNamesForVolumeNameW' for x in a['trace'])==1)
    for size,state in ((256,'observed'),(257,'budget_exhausted')):
        paths=('C:\\'+'U'*(size-3),);positive=reply(paths)
        a=run('path-unit-boundary-'+str(size),fixture(mounts=[[reply(ok=False,error=234,copied=int(positive['copied'])),positive]]))
        check('path-unit-boundary-'+str(size),a['snapshot']['records'][0]['mounts']['state']==state and len(a['snapshot']['records'][0]['mounts']['paths'])==(1 if size==256 else 0))
    wide_paths=tuple('C:\\'+str(i).zfill(2)+'U'*121 for i in range(32))
    positive=reply(wide_paths);growth=reply(ok=False,error=234,copied=int(positive['copied']))
    a=run('maximum-mount-count',fixture(names=(VOLUME,OTHER,'\\\\?\\Volume{00000000-1234-abcd-abcd-123456789abc}\\'),mounts=[[growth,positive],[growth,positive],[]]))
    check('maximum-count-retains-all-64',sum(len(x['mounts']['paths']) for x in a['snapshot']['records'])==64 and a['snapshot']['records'][2]['mounts']['state']=='budget_exhausted')
    a=run('total-unit-budget',fixture(names=(VOLUME,OTHER),unit_limit=positive['copied'],mounts=[[growth,positive],[]]))
    check('total-unit-budget-no-next-query',len(a['snapshot']['records'][0]['mounts']['paths'])==32 and a['snapshot']['records'][1]['mounts']['state']=='budget_exhausted' and sum(x['api']=='GetVolumePathNamesForVolumeNameW' for x in a['trace'])==2)
    names=tuple('\\\\?\\Volume{'+format(i,'08x')+'-1234-abcd-abcd-123456789abc}\\' for i in range(64))
    a=run('maximum-volume-count',fixture(names=names,include_mounts=False));check('maximum-count-no-hidden-next',len(a['snapshot']['records'])==64 and a['snapshot']['enumeration']['state']=='budget_exhausted' and sum(x['api']=='FindNextVolumeW' for x in a['trace'])==63)
    for label,cancel,count in [('cancel-before-first',0,0),('cancel-after-name',1,1),('cancel-after-mount',2,1)]:
        a=run(label,fixture(cancel_after_calls=str(cancel)));check(label+'-retains-known',a['snapshot']['status']=='cancelled' and len(a['snapshot']['records'])==count and all(x['api']!='FindNextVolumeW' for x in a['trace']))
    a=run('callback-exception',fixture(mounts=[[dict(reply(),throw=True)]]));check('callback-exception-retains-volume',len(a['snapshot']['records'])==1 and a['snapshot']['records'][0]['mounts']['state']=='adapter_exception' and a['close_calls']=='1')
    a=run('failed-close',fixture(close_error='5'));check('failed-close-not-quiescence',a['snapshot']['status']=='partial' and a['snapshot']['close']==dict(state='uncertain',platform_code='5') and a['repeat_close_state']=='uncertain' and a['close_calls']=='1')
    for key,value in [('volume_limit','0'),('volume_limit','65'),('mount_limit','0'),('mount_limit','65'),('unit_limit','0'),('unit_limit','8193'),('capture_epoch','0'),('capture_epoch','18446744073709551616')]:
        a=run('invalid-'+key+'-'+value,fixture(**{key:value}),expected=3);check('invalid-input-before-ports-'+key+'-'+value,a['api_calls']=='0')
    a=run('maximum-capture',fixture(capture_epoch='18446744073709551615'));check('u64-capture-preserved',a['snapshot']['capture_epoch']=='18446744073709551615')
    result=dict(status='pass',qualification='injected-api-only',native_executions=len(executions),assertions=len(checks),
                pointer_bytes=args.pointer_bytes,probe_sha256=hashlib.sha256(probe.read_bytes()).hexdigest(),
                checks=checks,executions=executions,live_namespace_qualified=False,physical_access=False,owner_accepted=False,unit_complete=False)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps({k:v for k,v in result.items() if k not in ('checks','executions')}))

if __name__=='__main__':main()
