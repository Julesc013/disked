"""Actual acquisition review/submit in a newly owned hidden console."""
import json
from pathlib import Path
import subprocess
import sys
import time
from image_console_fixture import current_text
from console_tui_fixture import k,Callback,checked,configure,snapshot,key


def run(exe,params,report):
    configure(k.GetStdHandle(-11),240,25);before=snapshot();process=None
    handler=Callback(lambda _:True);checked(k.SetConsoleCtrlHandler(handler,True))
    argv=[exe,'--tui','--terminal=linear','image','acquire',params['phase']]
    if params['phase']=='prepare':argv += [params['source'],params['destination'],'--map',params['map'],'--state-dir',params['state_directory']]
    else:
        argv += ['--definition-json',json.dumps(params['definition'],separators=(',',':')),
            '--definition-digest',params['definition_digest']]
        for flag in ('source-read','destination-write','map-write','host-effects'):argv += ['--allow-'+flag]
    def response(text):
        compact=''.join(line.strip() for line in text.splitlines());decoder=json.JSONDecoder()
        for at,char in enumerate(compact):
            if char!='{':continue
            try:value,_=decoder.raw_decode(compact[at:])
            except ValueError:continue
            if isinstance(value,dict) and value.get('schema')=='org.disked.response/1':return value
    def wait(predicate):
        end=time.monotonic()+12
        while time.monotonic()<end:
            text=current_text();value=predicate(text)
            if value:return value
            assert process.poll() is None,'owned TUI exited: '+text
            time.sleep(.02)
        raise AssertionError('bounded console observation expired: '+current_text())
    try:
        process=subprocess.Popen(argv,close_fds=False)
        wait(lambda t:'TYPED FORM' in t);assert response(current_text()) is None
        key(13,'\r');time.sleep(.1);assert response(current_text()) is None
        key(0x78);wait(lambda t:'REQUEST REVIEW' in t);assert response(current_text()) is None
        key(0x78);value=wait(response);report.update(response=value,display=current_text(),inert_review=True)
        key(0x79);assert process.wait(timeout=8)==0
        after=snapshot();report['restored']={f:before[f]==after[f] for f in ('handles','modes','codepages','buffer','attributes','cursor_style')}
        assert all(report['restored'].values())
    finally:
        if process is not None and process.poll() is None:process.kill();process.wait(timeout=5)
        k.SetConsoleCtrlHandler(handler,False)


if __name__=='__main__':
    report={};code=0
    try:run(sys.argv[1],json.loads(Path(sys.argv[2]).read_bytes()),report)
    except Exception as e:report['fixture_error']=str(e);code=1
    Path(sys.argv[3]).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(code)
