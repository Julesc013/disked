"""Actual owned Windows renderers during serialized injected reader changes."""
import argparse, copy, hashlib, json, subprocess, sys, time
from pathlib import Path
from inventory_events import InventoryEvents
from test_observation_frontend import selected_registry
from test_identity_frame import fixture as identity, identity_disk
from test_storage_queries import disk, volume, packet, digest
from test_volume_namespace import fixture as namespace, reply, OTHER


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--probe',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--pointer-bytes',type=int,choices=(4,8),required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'tests/frontend'))
    from gui_fixture import Gui, wait, caption
    out=a.output.absolute();out.mkdir();probe=a.probe.absolute()
    code=hashlib.sha256(probe.read_bytes()).hexdigest();registry=selected_registry(root)
    checks=[];runs=[];children=set();prefix='__disked_nt_inventory_advance_fixture'
    def check(label,value):
        checks.append(dict(label=label,passed=bool(value)));assert value,label
    def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
    def stage(ns=None,storage=None):return dict(namespace=namespace() if ns is None else ns,storage=identity() if storage is None else storage)
    def verify(name,v,failed=False):
        check(name+' actual host/architecture/budget',v['renderer_exit']==('4' if failed else '0') and v['pointer_bytes']==str(a.pointer_bytes)
              and v['frontend_budget_ready'] and int(v['advance_calls'])>0 and int(v['callbacks'])>0)
        check(name+' no controller storage/namespace/health dispatch',v['namespace_api_calls']==v['storage_api_calls']==v['health_calls']=='0')
        check(name+' bounded retained native and model history',1<len(v['trace'])<=32 and len(v['workers'])<=64 and len(v['model_samples'])<=32)
        check(name+' explicitly observed reader retirement',not v['retirement']['outstanding'] and not any(s['outstanding'] for s in v['trace'][-1]['sources']))
        workers={}
        for w in v['workers']:
            check(name+' exact owned reader code and authority',w['code_sha256']==code and not any(w['claims'].values()))
            pid,created=w['worker']['pid'],w['worker']['created']
            if pid is not None:
                check(name+' native process identity',int(pid)>0 and int(created)>0)
                children.add((pid,created));workers[(w['attempt_id'],pid,created)]=w
        held=v['retained_after_session_and_renderer']
        check(name+' every owned reader has observed exit',all(w['worker']['observation']=='exited' for w in workers.values()))
        check(name+' complete history still owned after session/renderer teardown',len(held)==len(v['trace']) and all(x['same_snapshot'] for x in held))
        for index,sample in enumerate(v['trace']):
            prior=held[index];check(name+' immutable held complete publication',all(prior[k]==sample[k] for k in ('graph','sources','bindings','artifacts','resolved')))
            graph=sample['graph'];unbound=copy.deepcopy(graph);revision=unbound.pop('revision')
            check(name+' independent complete graph identity',revision==digest(unbound))
            by_id={n['id']:n for n in graph['nodes']}
            check(name+' complete matching native backing for every row',[b['node'] for b in sample['bindings']]==list(by_id))
            for b in sample['bindings']:
                n=by_id[b['node']];q=n['properties'];binding=q['observation_binding'];context=b['context']
                check(name+' independent exact observation identity',n['id']=='observation:'+digest(dict(binding=binding,kind=n['kind'],label=q['label'],payload=q['observation']))[7:])
                check(name+' complete frame/context and unknown media authority',binding['frame_digest']==digest(sample['artifacts'][b['artifact']])
                      and binding['context_digest']==digest(context) and q['scope']=='observation-only'
                      and q['identity'] is None and q['media_generation'] is None and q['capacity_bytes'] is None
                      and q['aliases']==[] and not q['physical_admission'] and not q['mutation_authority'])
                w=workers[(context['attempt_id'],context['pid'],context['created'])]
                expected={k:w[k] for k in ('attempt_id','observer_epoch','worker_epoch','request_digest','code_sha256')}
                expected.update({k:w['worker'][k] for k in ('pid','created')})
                if binding['source']=='storage' and v['composition']!='metadata':expected['storage_profile']='identity-layout'
                check(name+' exact native attempt/code/process/epoch binding',context==expected)
                check(name+' display label inert',all(32<=ord(c)<=126 for c in q['label']))
            for ref in sample['resolved']:
                check(name+' exact complete reference retrieval',ref['reference']['digest']==digest(sample['artifacts'][ref['artifact']])
                      and by_id[ref['node']]['properties']['observation']['references'][ref['name']]==ref['reference'])
        if failed:
            check(name+' callback escaped with both readers outstanding',v['callback_threw'] and v['callback_fault']=='pending'
                  and v['callback_sources_before_throw']==[True,True] and v['retirement']['before']==[True,True])
            check(name+' no destroyed model accessed or successful request manufactured',v['final_model_state'] is None and not v['dispatches'] and not v['errors'])
        else:
            check(name+' no callback failure manufactured',not v['callback_threw'] and not v['callback_sources_before_throw'])
            check(name+' model keeps last publication it actually observed',v['final_model_state']['view_revision'] in {s['graph']['revision'] for s in v['trace']})
    def gui(name,composition,stages,action='review',states=('complete','complete')):
        request=out/(name+'.request.json');receipt=out/(name+'.receipt.json');start=time.monotonic();g=None
        with InventoryEvents() as events:
            save(request,dict(registry=registry,composition=composition,stages=stages,controls=events.names))
            try:
                g=Gui(probe,[prefix,'gui',str(request),str(receipt)],render=True)
                check(name+' cached native caption',caption(g.window)=='DiskEd - Cached observation prototype')
                g.choose(0);g.click(108);old=g.details()['result']['node']['id']
                g.click(105);g.choose(next(i for i,s in enumerate(g.list_ids()) if s.startswith('target.inspect')))
                g.click(108);g.set(200,old);g.click(109);reviewed=g.details()
                check(name+' staged request reviewed before new readers',reviewed['reviewed'] and reviewed['parameters']['target_id']==old)
                events.signal('advance');wait(lambda:'Observations updated' in g.text(103))
                if action=='close-pending':pass
                elif action=='startup-recover':
                    time.sleep(5.4);events.signal('advance');time.sleep(.12);events.signal('release');time.sleep(.8)
                elif action=='deadline':
                    events.signal('release');time.sleep(5.4)
                else:
                    if action=='refuse-pending':events.signal('advance');time.sleep(.12)
                    if action=='cancel-before':events.signal('cancel');time.sleep(.12)
                    events.signal('release')
                    if action in ('cancel-during','late-timeout'):
                        time.sleep(.08);events.signal('cancel' if action=='cancel-during' else 'timeout')
                    time.sleep(.8)
                check(name+' exact reviewed fields/revision unchanged by delivery',g.details()==reviewed)
                if action!='close-pending':
                    g.click(110);outcome=g.details()
                    check(name+' stale review refused before target dispatch',outcome['status']=='refused' and outcome['diagnostics'][0]['code']=='revision_conflict')
                host=g.observation();capture=g.screenshot(out/(name+'.png'));g.close()
                check(name+' actual owned desktop exit/channels',g.code==0 and not g.output and not g.error and not g.created_files)
                v=json.loads(receipt.read_bytes());verify(name,v)
                observed_states=[s['state'] for s in v['trace'][-1]['sources']]
                check(name+' source outcome not inferred from display',observed_states==list(states) if states is not None
                      else all(s in ('partial','unavailable') for s in observed_states))
                check(name+' selection never rebound',v['selection']['observation_id']==old and v['selection']['target_id'] is None)
                check(name+' one preserved request without duplicate submission',len(v['dispatches'])==(0 if action=='close-pending' else 1))
                if action!='close-pending':
                    request_value=v['dispatches'][0]
                    check(name+' exact originally reviewed identity/revision',request_value['parameters']['target_id']==old
                          and request_value['expected_revision']==v['trace'][0]['graph']['revision'])
                kinds=[e['kind'] for e in v['events']]
                check(name+' expected error evidence',bool(v['errors'])==(action=='startup-recover'))
                if action=='refuse-pending':check(name+' no replacement while source outstanding','advance_refused_outstanding' in kinds)
                if action in ('late-timeout','deadline','startup-recover'):check(name+' finite timeout recorded','timeout' in kinds)
                if action in ('deadline','startup-recover'):
                    check(name+' timeout issued once with separately observed retirement',kinds.count('timeout')==1
                          and ('deadline_retired' in kinds or kinds.count('settled')>=2)
                          and not any(v['retirement']['before']))
                if action.startswith('cancel'):check(name+' explicit cancellation recorded','cancel' in kinds)
                if action=='close-pending':check(name+' host closing did not imply reader exit',any(v['retirement']['before']))
                if action=='startup-recover':check(name+' recovered next capture keeps historical error',v['trace'][-1]['stage']=='2' and 'after_spawn' in v['errors'][0]['reason'])
                save(out/(name+'.host.json'),dict(host=host,capture=capture,reviewed=reviewed))
                runs.append(dict(label=name,frontend='gui',exit_code=g.code,elapsed_seconds=round(time.monotonic()-start,3)))
            finally:
                if g is not None and g.desktop is not None:g.close()
    def console(name,mode,composition,stages,journey='review',style='linear'):
        request=out/(name+'.request.json');receipt=out/(name+'.receipt.json');report=out/(name+'.host.json')
        save(request,dict(registry=registry,composition=composition,stages=stages,journey=journey,terminal_style=style,callback_fault='pending' if journey=='fault' else 'none'))
        startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0;start=time.monotonic()
        r=subprocess.run([sys.executable,str(root/'tests/windows/inventory_advance_console.py'),str(probe),mode,str(request),str(receipt),str(report)],startupinfo=startup,creationflags=subprocess.CREATE_NEW_CONSOLE,timeout=40)
        host=json.loads(report.read_bytes());check(name+' actual owned hidden-console journey',r.returncode==0 and host['status']=='pass')
        v=json.loads(receipt.read_bytes());verify(name,v,journey=='fault')
        check(name+' exact native restoration',all(host['before'][k]==host['after'][k] for k in ('modes','codepages','cursor_style','attributes')))
        check(name+' inert actual console text',all('\x1b' not in f['text'] for f in host['frames']))
        check(name+' exact diagnostic and private host selection',v['terminal_style']==style and host['exit']==(4 if journey=='fault' else 0)
              and host['stderr']==('disked: frontend_event_error\r\n' if journey=='fault' else ''))
        if style=='screen':
            check(name+' actual screen presentation',any('CACHED OBSERVATIONS | screen' in f['text'] for f in host['frames']))
            check(name+' original active buffer content cursor and geometry restored',host['active_after']==host['before']['content']
                  and all(host['before'][k]==host['after'][k] for k in ('handles','buffer','viewport','cursor','content')))
        if journey=='review':
            check(name+' exact old review conflicts',v['dispatches'][-1]['expected_revision']==v['trace'][0]['graph']['revision']
                  and v['dispatches'][-1]['parameters']['target_id']==host['reviewed_id'] and v['selection']['state']=='missing')
        else:check(name+' no implicit dispatch from chooser/completion',not v['dispatches'])
        runs.append(dict(label=name,frontend=mode,exit_code=r.returncode,elapsed_seconds=round(time.monotonic()-start,3)))
    def gui_fault():
        name='gui-callback-fault';request=out/(name+'.request.json');receipt=out/(name+'.receipt.json');g=None;start=time.monotonic()
        with InventoryEvents() as events:
            save(request,dict(registry=registry,composition='identity',stages=[stage(),stage()],controls=events.names,callback_fault='pending'))
            try:
                g=Gui(probe,[prefix,'gui',str(request),str(receipt)],render=True)
                check(name+' initial cached window exists',caption(g.window)=='DiskEd - Cached observation prototype')
                g.choose(0);g.click(108);old=g.details()['result']['node']['id']
                host=g.observation();capture=g.screenshot(out/(name+'.png'));events.signal('advance')
                wait(lambda:g.process.poll() is not None);g.close()
                check(name+' internal-error exit and inert diagnostic',g.code==4 and not g.output and g.error==b'disked: gui_event_error\r\n' and not g.created_files)
                v=json.loads(receipt.read_bytes());verify(name,v,True)
                check(name+' selected observation not rebound by failed host',v['selection']['observation_id']==old and v['selection']['target_id'] is None)
                save(out/(name+'.host.json'),dict(host=host,capture=capture,exit=g.code,stderr=g.error.decode('ascii')))
                runs.append(dict(label=name,frontend='gui',exit_code=g.code,elapsed_seconds=round(time.monotonic()-start,3)))
            finally:
                if g is not None and g.desktop is not None:g.close()
    def reject(name,args,reason=None,exit_code=3):
        before={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.iterdir() if f.is_file()}
        r=subprocess.run([probe,*map(str,args)],cwd=out,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=10)
        after={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.iterdir() if f.is_file()}
        check(name+' exact inert refusal and no changed files',r.returncode==exit_code and not r.stderr and before==after)
        if exit_code==2:check(name+' invalid shape has no output',not r.stdout)
        else:
            v=json.loads(r.stdout);check(name+' typed refusal before reader start',v['status']=='refused' and v['reason']==reason and v['reader_starts']=='0')
        (out/(name+'.stdout.log')).write_bytes(r.stdout);runs.append(dict(label=name,frontend='launcher-rejection',exit_code=r.returncode))
    try:
        with InventoryEvents() as events:
            base=dict(registry=registry,composition='identity',stages=[stage()],controls=events.names)
            request=out/'valid-rejection-input.json';receipt=out/'must-not-exist.json';save(request,base)
            for name,args in [('no-args',[]),('wrong-role',['unknown','gui',request,receipt]),('short',[prefix,'gui',request]),('extra',[prefix,'gui',request,receipt,'extra']),('mode',[prefix,'cli',request,receipt])]:reject(name,args,exit_code=2)
            bad_controls=[({},'fixture_controls'),(dict(base['controls'],other='invalid'),'fixture_controls'),(dict(base['controls'],advance=True),'fixture_shape'),(dict(base['controls'],advance='Global\\unowned'),'fixture_controls'),(dict(base['controls'],advance=events.names['release']),'fixture_controls'),(dict(base['controls'],advance=events.names['advance'].replace('Inventory.','Other.')),'fixture_controls'),(dict(base['controls'],advance=events.names['advance'].replace(events.names['advance'][23:55],'0'*32)),'fixture_controls')]
            for i,(controls,reason) in enumerate(bad_controls):
                invalid=out/('controls-'+str(i)+'.request.json');value=copy.deepcopy(base);value['controls']=controls;save(invalid,value);reject('controls-'+str(i),[prefix,'gui',invalid,receipt],reason)
            for name,bad in [('relative','input.json'),('namespace','\\\\?\\C:\\input.json'),('unc','\\\\invalid-host\\share\\input.json'),('stream',str(request)+':extra.json'),('device',str(out/'CON.json')),('parent',str(out)+'\\..\\input.json'),('wildcard',str(out/'*.json')),('extension',str(out/'input.txt'))]:
                reject('input-'+name,[prefix,'gui',bad,receipt],'fixture_path');reject('receipt-'+name,[prefix,'gui',request,bad],'fixture_path')
            existing=out/'existing.json';existing.write_bytes(b'original\r\n');reject('existing-receipt',[prefix,'gui',request,existing],'fixture_receipt_unavailable');reject('input-alias',[prefix,'gui',request,request],'fixture_receipt_unavailable')
            for name,field,value,reason in [('style-value','terminal_style','auto','fixture_terminal_style'),('style-type','terminal_style',False,'fixture_shape'),('fault-value','callback_fault','arbitrary','fixture_callback_fault'),('fault-type','callback_fault',False,'fixture_shape')]:
                invalid=out/(name+'.request.json');selection_input=copy.deepcopy(base);selection_input[field]=value;save(invalid,selection_input);reject(name,[prefix,'tui',invalid,receipt],reason)
        good=('complete','complete');metadata=dict(subjects=[disk(),volume()])
        for composition,storage in [('metadata',metadata),('identity-frame',identity()),('identity',identity())]:
            stages=[stage(storage=storage),stage(storage=storage)]
            gui('gui-'+composition,composition,stages)
            for mode in ('tui','shell'):console(mode+'-'+composition,mode,composition,stages)
        denied=identity_disk();denied['replies']['alignment']=[packet(ok=False,error=5)]
        gui('gui-partial-stale','identity',[stage(),stage(namespace(names=(OTHER,),terminal_error='5'),identity(denied,volume()))],states=('partial','partial'))
        hostile=namespace(mounts=[[reply(('C:\\label\x1b[2J\ud800\u202e\\',))]])
        gui('gui-inert-names','identity',[stage(),stage(hostile)])
        gui('gui-refuse-pending','identity',[stage(),stage()],action='refuse-pending')
        gui('gui-cancel-before','identity',[stage(),stage()],action='cancel-before',states=('partial','partial'))
        delayed=stage(namespace(worker_fault='delay'),identity(worker_fault='delay'))
        gui('gui-cancel-during','identity',[stage(),delayed],action='cancel-during',states=('partial','partial'))
        gui('gui-late-timeout','identity',[stage(),delayed],action='late-timeout')
        gui('gui-hang-deadline','identity',[stage(),stage(namespace(worker_fault='hang'),identity(worker_fault='hang'))],action='deadline',states=('unavailable','unavailable'))
        # A cancellation receipt can win the race with explicit owned-job
        # retirement. Both partial and unavailable remain non-success evidence.
        gui('gui-close-pending','identity',[stage(),stage()],action='close-pending',states=None)
        gui('gui-startup-recover','identity',[stage(),stage(namespace(startup_fault='after_spawn')),stage()],action='startup-recover')
        for journey in ('chooser','completion'):console('shell-'+journey,'shell','identity',[stage(),stage()],journey)
        for composition,storage in [('metadata',metadata),('identity-frame',identity()),('identity',identity())]:
            console('tui-screen-'+composition,'tui',composition,[stage(storage=storage),stage(storage=storage)],style='screen')
        gui_fault()
        for mode in ('tui','shell'):
            for style in ('linear','screen'):console(mode+'-'+style+'-callback-fault',mode,'identity',[stage(),stage()],'fault',style)
        result=dict(status='pass',pointer_bytes=a.pointer_bytes,controller_executions=len(runs),actual_child_launches=len(children),assertions=len(checks),checks=checks,executions=runs,private_native_advance_qualified=True,live_qualified=False,product_admitted=False,owner_accepted=False,unit_complete=False)
        save(out/'results.json',result);print(json.dumps({k:result[k] for k in ('status','controller_executions','actual_child_launches','assertions')}))
    except BaseException as error:
        save(out/'results.json',dict(status='fail',error=str(error),checks=checks,executions=runs));raise


if __name__=='__main__':main()
