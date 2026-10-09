"""Actual acquisition review/submit in a newly owned hidden console."""
import ctypes as C
import json
from pathlib import Path
import subprocess
import sys
import time
from image_console_fixture import current_text
from console_tui_fixture import k,w,Callback,checked,configure,snapshot,key,active,info,Coord


def run(exe,params,report,frontend='tui',command_override=None):
    watch='operation_id' in params
    configure(k.GetStdHandle(-11),240,25)
    if watch:checked(k.SetConsoleScreenBufferSize(k.GetStdHandle(-11),Coord(240,12000)))
    before=snapshot();process=None
    handler=Callback(lambda _:True);checked(k.SetConsoleCtrlHandler(handler,True))
    command=command_override if command_override is not None else (['operation','watch',params['operation_id'],'--state-dir',params['state_directory']] if watch else ['image','acquire',params['phase']])
    if command_override is not None or watch:pass
    elif params['phase']=='prepare':command += [params['source'],params['destination'],'--map',params['map'],'--state-dir',params['state_directory']]
    else:
        command += ['--definition-json',json.dumps(params['definition'],separators=(',',':'),ensure_ascii=False),
            '--definition-digest',params['definition_digest']]
        for flag in ('source-read','destination-write','map-write','host-effects'):command += ['--allow-'+flag]
    argv=[exe,'shell','--terminal=linear'] if frontend=='shell' else [exe,'--tui','--terminal=linear',*command]
    def observe_text():
        if not watch:return current_text()
        handle=active()
        try:
            dimensions=info(handle);count=dimensions.size.X*max(dimensions.cursor.Y+1,dimensions.window.Bottom+1)
            assert 0<count<=2880000
            parts=[];at=0
            while at<count:
                size=min(count-at,60000);buffer=C.create_unicode_buffer(size+1);got=w.DWORD()
                checked(k.ReadConsoleOutputCharacterW(handle,buffer,size,Coord(at%dimensions.size.X,at//dimensions.size.X),C.byref(got)))
                assert got.value>0;parts.append(buffer[:got.value]);at+=got.value
            text=''.join(parts)
            return '\n'.join(text[i:i+dimensions.size.X].rstrip() for i in range(0,len(text),dimensions.size.X))
        finally:k.CloseHandle(handle)
    def response(text):
        compact=''.join(line.strip() for line in text.splitlines());decoder=json.JSONDecoder()
        for at,char in enumerate(compact):
            if char!='{':continue
            try:value,_=decoder.raw_decode(compact[at:])
            except ValueError:continue
            if isinstance(value,dict) and value.get('schema')=='org.disked.response/1':return value
    def wait(predicate):
        end=time.monotonic()+30
        while time.monotonic()<end:
            text=observe_text();value=predicate(text)
            if value:return value
            assert process.poll() is None,'owned TUI exited: '+text
            time.sleep(.02)
        raise AssertionError('bounded console observation expired: '+observe_text())
    try:
        process=subprocess.Popen(argv,close_fds=False)
        wait(lambda t:'disked>' in t if frontend=='shell' else 'TYPED FORM' in t)
        if frontend=='shell':
            line=' '.join('"'+word.replace('"','""')+'"' for word in command)
            assert len(line.encode())<=65536
            for char in line:
                units=char.encode('utf-16-le')
                for at in range(0,len(units),2):key(0,chr(int.from_bytes(units[at:at+2],'little')))
        assert response(observe_text()) is None
        key(13,'\r');time.sleep(.1);assert response(observe_text()) is None
        key(0x78);wait(lambda t:'F9 submits:' in t if frontend=='shell' else 'REQUEST REVIEW' in t)
        assert response(observe_text()) is None
        if frontend=='shell':assert '"expected_revision": null' in observe_text()
        key(0x78);value=wait(response);report.update(frontend=frontend,response=value,display=observe_text(),inert_review=True)
        key(0x79);assert process.wait(timeout=8)==0
        after=snapshot();report['restored']={f:before[f]==after[f] for f in ('handles','modes','codepages','buffer','attributes','cursor_style')}
        assert all(report['restored'].values())
    finally:
        if process is not None and process.poll() is None:process.kill();process.wait(timeout=5)
        k.SetConsoleCtrlHandler(handler,False)


if __name__=='__main__':
    report={};code=0
    try:run(sys.argv[1],json.loads(Path(sys.argv[2]).read_bytes()),report,sys.argv[4] if len(sys.argv)>4 else 'tui')
    except Exception as e:report['fixture_error']=str(e);code=1
    Path(sys.argv[3]).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(code)
