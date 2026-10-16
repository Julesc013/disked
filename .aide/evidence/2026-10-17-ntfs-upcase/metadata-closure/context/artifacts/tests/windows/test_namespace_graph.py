"""Independent observation graph checks over generated names and owned fixture workers."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
from test_volume_namespace import fixture,reply,VOLUME,OTHER,representation


def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
def digest(v):return 'sha256:'+hashlib.sha256(canonical(v)).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--pointer-bytes',type=int,required=True,choices=(4,8));a=p.parse_args()
    a.output.mkdir();checks=[];runs=[];bindings=set();child_launches=0
    def check(label,ok):
        checks.append(dict(label=label,passed=bool(ok)))
        assert ok,label
    def run(label,value,expected=0):
        data=json.dumps(value,separators=(',',':'),ensure_ascii=True).encode();(a.output/(label+'.request.json')).write_bytes(data)
        r=subprocess.run([str(a.probe.resolve())],input=data,capture_output=True,timeout=20)
        (a.output/(label+'.stdout')).write_bytes(r.stdout);(a.output/(label+'.stderr')).write_bytes(r.stderr)
        runs.append(dict(label=label,exit_code=r.returncode,expected_exit=expected));check(label+' actual exit',r.returncode==expected and not r.stderr)
        v=json.loads(r.stdout)
        if expected==0:check(label+' actual architecture',v['pointer_bytes']==str(a.pointer_bytes))
        return v
    def graph_check(label,g):
        unbound=copy.deepcopy(g);claimed=unbound.pop('revision');check(label+' graph digest',digest(unbound)==claimed)
        ids={n['id'] for n in g['nodes']};check(label+' distinct node IDs',len(ids)==len(g['nodes']))
        for n in g['nodes']:
            q=n['properties']
            if q['scope']=='fake-only':continue
            check(label+' unknown physical identity',q['identity'] is None and q['media_generation'] is None and q['capacity_bytes'] is None and q['aliases']==[] and q['physical_identity']=='unknown')
            check(label+' no authority',q['physical_admission'] is False and q['mutation_authority'] is False and q['state'] in ('unknown','stale'))
            expected='observation:'+digest(dict(binding=q['observation_binding'],kind=n['kind'],label=q['label'],payload=q['observation']))[7:]
            check(label+' independently derived observation ID',n['id']==expected)
            check(label+' exact name and safe display',q['label']==q['observation']['name']['display'] and all(32<=ord(c)<=126 for c in q['label']))
        for e in g['edges']:check(label+' observation-only mount edge',e['from'] in ids and e['to'] in ids and e['kind']=='mounts')
    def owned(label,stages,mode='sequence'):
        nonlocal child_launches
        v=run(label,dict(mode=mode,stages=[x if 'fixture' in x else dict(fixture=x) for x in stages]))
        previous_by_binding={}
        for i,s in enumerate(v['samples']):
            w=s['worker'];c=s['capture'];g=c['graph'];graph_check(label+' '+str(i),g)
            identity=tuple(w[k] for k in ('attempt_id','observer_epoch','worker_epoch','request_digest','code_sha256'))+(w['worker']['pid'],w['worker']['created'])
            if identity not in previous_by_binding:
                check(label+' unique owned attempt',identity not in bindings);bindings.add(identity);child_launches+=1
                check(label+' exact executing code',w['code_sha256']==hashlib.sha256(a.probe.read_bytes()).hexdigest())
            previous_by_binding[identity]=w
            check(label+' peer retained',any(n['id']=='fake:peer' for n in g['nodes']))
            if w['worker']['observation']!='exited':check(label+' publication does not retire',c['sources'][0]['outstanding'])
            for n in g['nodes']:
                q=n['properties']
                if q['scope']!='observation-only' or q['state']=='stale':continue
                b=q['observation_binding'];context=q['observation']['worker_context']
                expected={k:w[k] for k in ('attempt_id','observer_epoch','worker_epoch','request_digest','code_sha256')}
                expected.update({k:w['worker'][k] for k in ('pid','created')})
                check(label+' exact current owned binding',context==expected and b['context_digest']==digest(context) and b['capture_epoch']==c['capture'] and b['worker_epoch']==c['sources'][0]['attempt_worker'])
                check(label+' exact frame digest',b['frame_digest']==digest(w['result']))
        check(label+' final exact reader exit',v['samples'][-1]['worker']['worker']['observation']=='exited' and not v['samples'][-1]['capture']['sources'][0]['outstanding'])
        finals=[s['capture']['graph'] for s in v['samples'] if s['worker']['worker']['observation']=='exited']
        check(label+' old immutable views retained',v['retained']==finals)
        return v

    good=run('pure-lossless',dict(mode='project',fixture=fixture(mounts=[[reply(('C:\\','C:\\label\x1b[31m\ud800\u202e\\'))]])))
    graph_check('pure-lossless',good['graph']);check('lossless original code units',good['graph']['nodes'][2]['properties']['observation']['name']==representation('C:\\label\x1b[31m\ud800\u202e\\'))
    duplicate=run('pure-duplicates',dict(mode='project',fixture=fixture(names=(VOLUME,VOLUME),mounts=[[reply(('C:\\','c:\\'))],[reply(('C:\\',))]])))
    graph_check('pure-duplicates',duplicate['graph']);check('duplicates never merged',len(duplicate['graph']['nodes'])==5 and len(duplicate['graph']['edges'])==3 and duplicate['snapshot']['status']=='partial')
    check('all duplicate flags preserved',all(n['properties']['observation']['conflicts']['duplicate_volume_name'] for n in duplicate['graph']['nodes']))
    base=good['snapshot'];mutations={
        'capture':lambda s:s.update(capture_epoch='2'),
        'live-binding':lambda s:s.update(api_binding='native-win32-table'),
        'authority':lambda s:s['claims'].update(physical_admission=True),
        'display':lambda s:s['records'][0]['volume_path'].update(display='replacement'),
        'epoch-id':lambda s:s['records'][0].update(observation_id='nt-volume-observation:2:1'),
        'units-budget':lambda s:s['policy'].update(mount_units='1'),
        'status':lambda s:s.update(status='invented'),
        'partial-complete':lambda s:s['enumeration'].update(state='budget_exhausted',exhausted=False),
        'unknown-field':lambda s:s.update(unexpected=True),
        'physical-identity':lambda s:s['claims'].update(physical_identity='known'),
    }
    for label,mutate in mutations.items():
        s=copy.deepcopy(base);mutate(s);v=run('reject-'+label,dict(mode='project',snapshot=s),3);check(label+' typed refusal',v['status']=='refused')
    s=copy.deepcopy(base);s['policy']['mount_units']='1'
    run('reject-consistent-unit-overrun',dict(mode='project',snapshot=s,policy=s['policy']),3)
    context=copy.deepcopy(good['context']);context['pid']='0';run('reject-zero-process',dict(mode='project',snapshot=base,context=context),3)
    context=copy.deepcopy(good['context']);context['worker_epoch']='worker:stale';run('reject-worker-domain',dict(mode='project',snapshot=base,context=context),3)
    names=tuple('\\\\?\\Volume{'+format(i,'08x')+'-1234-abcd-abcd-123456789abc}\\' for i in range(64))
    maximum=run('maximum-observations',dict(mode='project',fixture=fixture(names=names,include_mounts=False),policy=dict(volumes='64',mounts='64',mount_units='8192',include_mounts=False)))
    graph_check('maximum-observations',maximum['graph']);check('volume budget exact retained remainder',len(maximum['graph']['nodes'])==64 and maximum['snapshot']['status']=='partial')

    v=owned('repeated-complete',[fixture(),fixture()]);g=[s['capture']['graph'] for s in v['samples'] if s['worker']['worker']['observation']=='exited']
    check('new capture IDs never reused',{n['id'] for n in g[0]['nodes'] if n['id']!='fake:peer'}.isdisjoint(n['id'] for n in g[1]['nodes'] if n['id']!='fake:peer'))
    v=owned('partial-cache',[fixture(),fixture(names=(OTHER,),terminal_error='5'),fixture(names=(OTHER,),terminal_error='5'),fixture([],terminal_error='5'),fixture([])])
    finals=[s['capture'] for s in v['samples'] if s['worker']['worker']['observation']=='exited']
    for c in finals[1:3]:
        q=[n['properties'] for n in c['graph']['nodes'] if n['id']!='fake:peer'];check('partial current plus complete cache',len(q)==4 and [x['state'] for x in q]==['unknown','unknown','stale','stale'])
        check('cache from exact last complete frame',all(x['observation_binding']['capture_epoch']=='1' for x in q if x['state']=='stale'))
    check('denial retains prior observations as stale',finals[3]['sources'][0]['state']=='denied' and len(finals[3]['graph']['nodes'])==5 and all(n['properties']['state']=='stale' for n in finals[3]['graph']['nodes']))
    check('complete empty replaces namespace only',finals[4]['sources'][0]['state']=='complete' and [n['id'] for n in finals[4]['graph']['nodes']]==['fake:peer'])
    for label,mode,fault in [('publication-before-exit','held','hold'),('late-current','late','delay'),('superseded','superseded','delay'),('retirement','retire','hang')]:
        f=fixture();f['reply_fault' if fault=='hold' else 'worker_fault']=fault;v=owned(label,[f],mode)
        if mode=='held':check('held frame published while running',v['samples'][1]['worker']['worker']['observation']=='running' and len(v['samples'][1]['capture']['graph']['nodes'])==3)
        elif mode=='superseded':check('old frame never published',all([n['id'] for n in s['capture']['graph']['nodes']]==['fake:peer'] for s in v['samples']))
        elif mode=='late':check('late current frame safely observed',v['samples'][-1]['capture']['sources'][0]['state']=='complete' and len(v['samples'][-1]['capture']['graph']['nodes'])==3)
        else:check('forced reader exit does not invent result',v['samples'][-1]['capture']['sources'][0]['state']=='unavailable')
    v=owned('cancel-before-query',[fixture()],'cancel');check('cancel explicit partial',v['samples'][-1]['capture']['sources'][0]['state']=='partial' and len(v['samples'][-1]['capture']['graph']['nodes'])==1)
    for fault in ('digest','capture','worker','claims','shape','status','schema'):
        f=fixture(names=(OTHER,));f['reply_fault']=fault;v=owned('malformed-'+fault,[fixture(),f]);last=v['samples'][-1]['capture']
        check(fault+' prior content retained',last['sources'][0]['state']=='unavailable' and len(last['graph']['nodes'])==3 and all(n['properties']['state']=='stale' for n in last['graph']['nodes']))
    result=dict(status='pass',scope='private observation graph over owned injected namespace workers',pointer_bytes=a.pointer_bytes,
        controller_executions=len(runs),actual_child_launches=child_launches,assertions=len(checks),executions=runs,checks=checks,
        artifact_sha256='sha256:'+hashlib.sha256(a.probe.read_bytes()).hexdigest(),native_graph_projection_qualified=True,
        live_namespace_qualified=False,provider_admitted=False,physical_access=False,owner_accepted=False,unit_complete=False)
    (a.output/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps({k:v for k,v in result.items() if k not in ('checks','executions')}))


if __name__=='__main__':main()
