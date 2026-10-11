"""Owned hidden-console active observation journeys; no foreground input."""
import json,re,subprocess,sys,time
from pathlib import Path
from inventory_console import k,w,c,checked,configure,key,snapshot,current_text
from inventory_events import InventoryEvents

probe,mode,request,receipt,report_path=sys.argv[1:];report={};process=None
try:
    with InventoryEvents() as events:
        packet=json.loads(Path(request).read_bytes());packet['controls']=events.names
        Path(request).write_text(json.dumps(packet,indent=2)+'\n',encoding='utf-8',newline='\n')
        configure(k.GetStdHandle(-11),160,25)
        marker='OWNED CALLER BUFFER\r\n';written=w.DWORD()
        checked(k.WriteConsoleW(k.GetStdHandle(-11),marker,len(marker),c.byref(written),None))
        assert written.value==len(marker)
        report['before']=snapshot();frames=[];report['frames']=frames
        def wait(needle):
            end=time.monotonic()+8
            while time.monotonic()<end:
                text=current_text()
                if needle in text:frames.append(dict(contains=needle,text=text));return text
                if process.poll() is not None:raise AssertionError('Exited before '+needle+': '+str(process.returncode)+'\n'+text)
                time.sleep(.02)
            raise AssertionError('Missing '+needle+'\n'+text)
        def write(text):
            for character in text:key(0,character)
        process=subprocess.Popen([probe,'__disked_nt_inventory_advance_fixture',mode,request,receipt],close_fds=False,stderr=subprocess.PIPE)
        initial=wait('OBSERVATION INVENTORY' if mode=='tui' else 'disked>')
        scenario=packet.get('journey','review')
        if scenario=='fault':
            events.signal('advance')
        elif mode=='shell' and scenario in ('chooser','completion'):
            write('target ins')
            key(0x72 if scenario=='chooser' else 9)
            wait('Enter selects:' if scenario=='chooser' else 'Tab inserts:')
            events.signal('advance');wait('observations updated');events.signal('release')
            # Controller pacing is not the acceptance oracle. The retained
            # native/model receipt below must prove the changed publication.
            time.sleep(.8);key(0x79)
        elif mode=='tui':
            key(13,'\r');observed=wait('observation-only');node=re.search(r'observation:[0-9a-f]{64}',observed).group(0)
            key(0x71);index=next(i for i,v in enumerate(packet['registry']['commands']) if v['id']=='target.inspect')
            for _ in range(index):key(0x28)
            key(13,'\r');wait('TYPED FORM (inert)');write(node);key(0x78);wait('REQUEST REVIEW')
        else:
            write('target list');key(0x78);wait('F9 submits: target.list');key(0x78)
            observed=wait('observation_ids');node=re.search(r'observation:[0-9a-f]{64}',observed).group(0)
            # Selection is an explicit cached action; F3/Enter selects this ID.
            key(0x72);wait('Enter selects:');key(13,'\r');wait('selection')
            write('target inspect '+node);key(0x78);wait('F9 submits: target.inspect')
        if scenario=='review':
            report['reviewed_id']=node;events.signal('advance')
            wait('Observations updated' if mode=='tui' else 'observations updated');events.signal('release')
            # A new publication must be observed before consuming the old review.
            end=time.monotonic()+8
            while time.monotonic()<end:
                text=current_text()
                if re.search(r'"state"\s*:\s*"missing"',text):frames.append(dict(contains='later publication',text=text));break
                time.sleep(.02)
            else:raise AssertionError('No later delivered publication')
            key(0x78);wait('revision_conflict');key(0x79)
        report['exit']=process.wait(timeout=8);report['stderr']=process.stderr.read().decode('ascii');process.stderr.close()
        assert report['exit']==(4 if scenario=='fault' else 0)
        assert report['stderr']==('disked: frontend_event_error\r\n' if scenario=='fault' else '')
        report['after']=snapshot();value=json.loads(Path(receipt).read_bytes());report['receipt']=value
        assert not value['errors'] and not value['retirement']['outstanding']
        if scenario=='fault':
            assert value['callback_threw'] and all(value['callback_sources_before_throw'])
            assert value['final_model_state'] is None and all(value['retirement']['before']) and not value['dispatches']
        elif scenario=='review':
            assert value['dispatches'][-1]['parameters']['target_id']==node and value['dispatches'][-1]['outcome']['diagnostics'][0]['code']=='revision_conflict'
        else:
            final=value['final_model_state'];before=value['model_samples'][1]
            assert final['editor']==before['editor']=='target ins' and final['cursor']==before['cursor']
            assert final['candidates']==before['candidates'] and not value['dispatches'] and final['requests']=='0'
            assert before['view']==('targets' if scenario=='chooser' else 'completion')
            assert final['view']==('editor' if scenario=='chooser' else 'completion')
            assert final['view_revision']==value['trace'][-1]['graph']['revision']!=value['trace'][0]['graph']['revision']
        for name in ('modes','codepages','cursor_style','attributes'):assert report['before'][name]==report['after'][name],name
        if packet.get('terminal_style','linear')=='screen':
            for name in ('handles','buffer','viewport','cursor','content'):assert report['before'][name]==report['after'][name],name
            report['active_after']=current_text();assert report['active_after']==report['before']['content']
            assert any('CACHED OBSERVATIONS | screen' in f['text'] for f in frames)
        report['status']='pass'
except Exception as error:report['status']='fail';report['error']=str(error)
finally:
    if process is not None and process.poll() is None:process.kill();process.wait(timeout=5)
    Path(report_path).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
raise SystemExit(0 if report.get('status')=='pass' else 1)
