"""Combined producer failures observed through a hidden test-owned console."""
import json
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'frontend'))
from console_tui_fixture import k,configure,current_text,key,snapshot

def run(exe,frontend,report):
    configure(k.GetStdHandle(-11),100,35);before=snapshot();p=None;frames=[]
    report.update(frontend=frontend,before=before,frames=frames)
    def wait(needle,seconds=5,after=None):
        started=time.monotonic()
        while time.monotonic()-started<seconds:
            text=current_text();tail=text.rsplit(after,1)[-1] if after and after in text else '' if after else text
            if needle in tail:
                frames.append(dict(contains=needle,text=text,elapsed_ms=(time.monotonic()-started)*1000));return text
            if p.poll() is not None:raise AssertionError('frontend exited before '+needle)
            time.sleep(.005)
        raise AssertionError('missing '+needle+'\n'+text)
    def type_text(text):
        for char in text:key(0,char)
    try:
        args=['shell','--terminal=linear'] if frontend=='shell' else ['--tui','--terminal=linear']
        p=subprocess.Popen([exe,*args],close_fds=False)
        wait('disked>' if frontend=='shell' else 'TARGET INVENTORY')
        time.sleep(.55);key(0x74)
        if frontend=='shell':
            wait('view refreshed');type_text('target list');key(0x78);wait('F9 submits: target.list');key(0x78)
        wait('slow:timed_out:probe_wait_expired')
        for reason in ['denied:denied:access_denied:5','malformed:malformed:provider_result_invalid','exited:unavailable:provider_exited:3758150013']:
            wait(reason)
        if frontend=='shell':
            wait('disked> [local|none] ""');type_text('inert draft');wait('inert draft')
            key(0x72);wait('targets (cached)',.25);report['cached_navigation_ms']=frames[-1]['elapsed_ms']
            key(0x1b);wait('inert draft')
        else:
            key(0x71);wait('COMMAND EXPLORER',.25);report['cached_navigation_ms']=frames[-1]['elapsed_ms']
            key(0x72);wait('TARGET INVENTORY',.25)
        time.sleep(1.5);key(0x74)
        if frontend=='shell':
            wait('inert draft',after='view refreshed')
            for _ in 'inert draft':key(8)
            type_text('mode explain');key(0x78);wait('F9 submits: mode.explain');key(0x78)
            wait('"exit_observed": true');wait('disked> [local|none] ""',after='"request_id": "shell:2"')
            key(0x72);wait('fake:late@1')
        else:wait('fake:late@1')
        key(0x79);report['exit']=p.wait(timeout=5);assert report['exit']==0
        report['after']=after=snapshot()
        for field in ['modes','codepages','buffer','cursor_style']:
            if before[field]!=after[field]:raise AssertionError('caller console changed '+field)
    finally:
        if p is not None and p.poll() is None:
            try:p.wait(timeout=3)
            except subprocess.TimeoutExpired:p.kill();p.wait(timeout=3)

if __name__=='__main__':
    report={};code=0
    try:run(sys.argv[1],sys.argv[3],report)
    except Exception as error:report['fixture_error']=str(error);code=1
    Path(sys.argv[2]).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(code)
