"""Image journeys in a new hidden test-owned console, never the user's console."""
import ctypes as C
import json
from pathlib import Path
import subprocess
import sys
import time
from console_tui_fixture import k,w,Callback,checked,configure,snapshot,key,active,info,Coord

def current_text():
    handle=active()
    try:
        value=info(handle);count=value.size.X*max(value.cursor.Y+1,value.window.Bottom+1)
        # This fixture configures exactly 240 columns and 1000 rows. The shared
        # small-console observer's 64K character prefix cannot cover an image
        # receipt padded into that console; inspect the whole bounded fixture.
        assert 0<count<=240000
        buffer=C.create_unicode_buffer(count+1);got=w.DWORD()
        checked(k.ReadConsoleOutputCharacterW(handle,buffer,count,Coord(0,0),C.byref(got)))
        return '\n'.join(buffer[i:min(i+value.size.X,got.value)].rstrip() for i in range(0,got.value,value.size.X))
    finally:k.CloseHandle(handle)

def run(exe,frontend,command,path,unit,report):
    configure(k.GetStdHandle(-11),240,25);before=snapshot();process=None
    handler=Callback(lambda _:True);checked(k.SetConsoleCtrlHandler(handler,True))
    flags=['shell','--terminal=linear'] if frontend=='shell' else ['--tui','--terminal=linear',*command.split('.'),path,'--logical-block-bytes',unit]
    def wait(predicate):
        end=time.monotonic()+10
        while time.monotonic()<end:
            text=current_text();value=predicate(text)
            if value:return value
            if process.poll() is not None:raise AssertionError('Console exited: '+str(process.returncode)+'\n'+text)
            time.sleep(.02)
        raise AssertionError('Console observation timed out\n'+current_text())
    def response(text):
        # Fixture values have no significant leading/trailing spaces. Remove
        # console padding and wrap boundaries before decoding the escaped JSON.
        compact=''.join(line.strip() for line in text.splitlines());decoder=json.JSONDecoder()
        for at,char in enumerate(compact):
            if char!='{':continue
            try:value,_=decoder.raw_decode(compact[at:])
            except ValueError:continue
            if isinstance(value,dict) and value.get('schema')=='org.disked.response/1':return value
        return None
    try:
        process=subprocess.Popen([exe,*flags],close_fds=False)
        if frontend=='shell':
            wait(lambda t:'disked>' in t)
            line=' '.join(command.split('.'))+' "'+path+'" --logical-block-bytes '+unit
            for char in line:
                encoded=char.encode('utf-16-le')
                for at in range(0,len(encoded),2):key(0,chr(int.from_bytes(encoded[at:at+2],'little')))
            key(13,'\r');time.sleep(.1);assert response(current_text()) is None,'Enter submitted inert editor'
            key(0x78);wait(lambda t:'F9 submits:' in t)
        else:
            wait(lambda t:'TYPED FORM' in t);key(13,'\r');time.sleep(.1)
            assert response(current_text()) is None,'Enter submitted inert form'
            key(0x78);wait(lambda t:'REQUEST REVIEW' in t)
        assert response(current_text()) is None,'Review executed the source'
        key(0x78);value=wait(response);report.update(frontend=frontend,command=command,response=value,display=current_text())
        key(0x79);assert process.wait(timeout=8)==0
        after=snapshot();report['restored']={field:before[field]==after[field] for field in ['handles','modes','codepages','buffer','attributes','cursor_style']}
        assert all(report['restored'].values()),report['restored']
    finally:
        if process is not None and process.poll() is None:process.kill();process.wait(timeout=5)
        k.SetConsoleCtrlHandler(handler,False)

if __name__=='__main__':
    result={};code=0
    try:run(*sys.argv[1:6],result)
    except Exception as error:result['fixture_error']=str(error);code=1
    Path(sys.argv[6]).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(code)
