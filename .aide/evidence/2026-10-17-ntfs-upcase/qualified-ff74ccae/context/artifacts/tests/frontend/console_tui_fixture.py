"""Private hidden console harness; no attachment to a user/parent console."""
import ctypes as c
from ctypes import wintypes as w
import json
from pathlib import Path
import subprocess
import sys
import time

class Coord(c.Structure):_fields_=[('X',w.SHORT),('Y',w.SHORT)]
class Rect(c.Structure):_fields_=[('Left',w.SHORT),('Top',w.SHORT),('Right',w.SHORT),('Bottom',w.SHORT)]
class Info(c.Structure):_fields_=[('size',Coord),('cursor',Coord),('attributes',w.WORD),('window',Rect),('maximum',Coord)]
class Cursor(c.Structure):_fields_=[('size',w.DWORD),('visible',w.BOOL)]
class Key(c.Structure):_fields_=[('down',w.BOOL),('repeat',w.WORD),('vk',w.WORD),('scan',w.WORD),('char',w.WCHAR),('control',w.DWORD)]
class Event(c.Union):_fields_=[('key',Key),('padding',w.DWORD*4)]
class Record(c.Structure):_fields_=[('type',w.WORD),('event',Event)]
k=c.WinDLL('kernel32',use_last_error=True)
def api(name,args,rest=w.BOOL):fn=getattr(k,name);fn.argtypes=args;fn.restype=rest;return fn
api('GetStdHandle',[w.DWORD],w.HANDLE)
api('CreateFileW',[w.LPCWSTR,w.DWORD,w.DWORD,c.c_void_p,w.DWORD,w.DWORD,w.HANDLE],w.HANDLE)
api('CloseHandle',[w.HANDLE]);api('GetConsoleMode',[w.HANDLE,c.POINTER(w.DWORD)]);api('SetConsoleMode',[w.HANDLE,w.DWORD])
api('CreateConsoleScreenBuffer',[w.DWORD,w.DWORD,c.c_void_p,w.DWORD,c.c_void_p],w.HANDLE)
api('SetHandleInformation',[w.HANDLE,w.DWORD,w.DWORD])
api('GetConsoleScreenBufferInfo',[w.HANDLE,c.POINTER(Info)]);api('GetConsoleCursorInfo',[w.HANDLE,c.POINTER(Cursor)])
api('SetConsoleActiveScreenBuffer',[w.HANDLE]);api('SetConsoleScreenBufferSize',[w.HANDLE,Coord]);api('SetConsoleWindowInfo',[w.HANDLE,w.BOOL,c.POINTER(Rect)])
api('ReadConsoleOutputCharacterW',[w.HANDLE,w.LPWSTR,w.DWORD,Coord,c.POINTER(w.DWORD)])
api('WriteConsoleW',[w.HANDLE,w.LPCWSTR,w.DWORD,c.POINTER(w.DWORD),c.c_void_p])
api('WriteConsoleInputW',[w.HANDLE,c.POINTER(Record),w.DWORD,c.POINTER(w.DWORD)])
api('GenerateConsoleCtrlEvent',[w.DWORD,w.DWORD])
Callback=c.WINFUNCTYPE(w.BOOL,w.DWORD);api('SetConsoleCtrlHandler',[Callback,w.BOOL])
def checked(ok):
    if not ok:raise c.WinError(c.get_last_error())
def active():
    handle=k.CreateFileW('CONOUT$',0xc0000000,3,None,3,0,None)
    if handle==c.c_void_p(-1).value:raise c.WinError(c.get_last_error())
    return handle
def info(handle):
    result=Info();checked(k.GetConsoleScreenBufferInfo(handle,c.byref(result)));return result
def mode(handle):
    value=w.DWORD();checked(k.GetConsoleMode(handle,c.byref(value)));return value.value
def read(handle):
    value=info(handle);count=min(value.size.X*max(value.cursor.Y+1,value.window.Bottom+1),65536)
    buffer=c.create_unicode_buffer(count+1);got=w.DWORD();checked(k.ReadConsoleOutputCharacterW(handle,buffer,count,Coord(0,0),c.byref(got)))
    return '\n'.join(buffer[i:min(i+value.size.X,got.value)].rstrip() for i in range(0,got.value,value.size.X))
def current_text():
    handle=active()
    try:return read(handle)
    finally:k.CloseHandle(handle)
def snapshot():
    out=k.GetStdHandle(-11);value=info(out);cursor=Cursor();checked(k.GetConsoleCursorInfo(out,c.byref(cursor)))
    return dict(handles=[k.GetStdHandle(n) for n in [-10,-11,-12]],modes=[mode(k.GetStdHandle(n)) for n in [-10,-11,-12]],
        codepages=[k.GetConsoleCP(),k.GetConsoleOutputCP()],buffer=[value.size.X,value.size.Y],
        viewport=[value.window.Left,value.window.Top,value.window.Right,value.window.Bottom],attributes=value.attributes,
        cursor_style=[cursor.size,bool(cursor.visible)],cursor=[value.cursor.X,value.cursor.Y],content=read(out))
def configure(handle,columns,rows):
    old=info(handle);small=Rect(0,0,min(columns,old.window.Right-old.window.Left+1)-1,min(rows,old.window.Bottom-old.window.Top+1)-1)
    checked(k.SetConsoleWindowInfo(handle,True,c.byref(small)))
    checked(k.SetConsoleScreenBufferSize(handle,Coord(columns,1000)))
    rect=Rect(0,0,columns-1,rows-1);checked(k.SetConsoleWindowInfo(handle,True,c.byref(rect)))
def key(vk,char='\0',down=True,up=True,control=0,repeat=1):
    events=[]
    if down:
        r=Record();r.type=1;r.event.key=Key(True,repeat,vk,0,char,control);events.append(r)
    if up:
        r=Record();r.type=1;r.event.key=Key(False,1,vk,0,char,control);events.append(r)
    records=(Record*len(events))(*events);written=w.DWORD();checked(k.WriteConsoleInputW(k.GetStdHandle(-10),records,len(events),c.byref(written)))
    if written.value!=len(events):raise RuntimeError('Incomplete injected input')

def run(exe,case,report):
    out=k.GetStdHandle(-11);configure(out,40 if case=='small' else 80,8 if case=='small' else 25)
    text='CALLER BUFFER UNCHANGED\r\n';written=w.DWORD();checked(k.WriteConsoleW(out,text,len(text),c.byref(written),None))
    before=snapshot();frames=[];p=None;shadow=None;report.update(case=case,before=before,frames=frames)
    handler=Callback(lambda event: True);checked(k.SetConsoleCtrlHandler(handler,True))
    flags=['--tui']
    if case in ['linear','small']:flags+=['--terminal=linear' if case=='linear' else '--terminal=auto']
    if case=='form':flags+=['target','inspect','fake:alpha@1','--terminal=linear']
    if case=='health-form':flags+=['health','assess','fake:clone@1','--include-identifiers','--include-raw','--include-interpretations','--terminal=linear']
    if case=='mode-linear':flags+=['mode','explain','--terminal=linear']
    if case=='forced-small':
        configure(out,40,8);before=snapshot();flags+=['--terminal=screen']
    def wait_for(needle):
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            text=current_text()
            if needle in text:frames.append(dict(contains=needle,text=text));return text
            if p.poll() is not None:raise AssertionError('Exited before '+needle+': '+str(p.returncode)+'\n'+text)
            time.sleep(.03)
        raise AssertionError('Console did not show '+needle+'\n'+text)
    try:
        startup=None
        if case in ['inactive-output','wrong-input']:
            startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESTDHANDLES
            startup.hStdInput=out if case=='wrong-input' else k.GetStdHandle(-10)
            startup.hStdOutput=out;startup.hStdError=k.GetStdHandle(-12)
            if case=='inactive-output':
                shadow=k.CreateConsoleScreenBuffer(0xc0000000,3,None,1,None)
                if shadow==c.c_void_p(-1).value:raise c.WinError(c.get_last_error())
                checked(k.SetHandleInformation(shadow,1,1));startup.hStdOutput=shadow
        p=subprocess.Popen([exe,*flags],close_fds=False,startupinfo=startup)
        if case in ['fault','forced-small','wrong-input']:
            code=p.wait(timeout=8)
        else:
            wait_for('TYPED FORM' if case in ['form','mode-linear','health-form'] else 'TARGET INVENTORY')
            if case=='screen':
                key(13,'\r');wait_for('Request completed')
                key(0x71);wait_for('COMMAND EXPLORER');key(13,'\r');wait_for('TYPED FORM')
                key(0x78,up=False);wait_for('REQUEST REVIEW')
                key(0x78,up=False);time.sleep(.15)
                if 'REQUEST REVIEW' not in current_text():raise AssertionError('Repeated F9 submitted')
                key(0x78,down=False);key(0x78);wait_for('Request completed')
                key(0x75);wait_for('linear')
                key(0x75);wait_for('screen')
            elif case in ['form','mode-linear','health-form']:
                key(13,'\r');key(13,'\r');time.sleep(.1)
                if 'Request completed' in current_text():raise AssertionError('Pasted newline submitted form')
                key(0x78);wait_for('REQUEST REVIEW');key(0x78);wait_for('Request completed')
                if case=='mode-linear':wait_for('"prefer_linear": true');wait_for('"terminal_presentation": "linear"')
                if case=='health-form':
                    wait_for('42 Celsius');wait_for('compiled-fixture');wait_for('not_established')
            elif case=='resize':
                h=active()
                try:configure(h,40,8)
                finally:k.CloseHandle(h)
                wait_for('linear');wait_for('Omission:')
            elif case=='external-mode':
                checked(k.SetConsoleMode(k.GetStdHandle(-10),mode(k.GetStdHandle(-10))^0x20)) # unrelated INSERT bit
            if case=='ctrl-c':checked(k.GenerateConsoleCtrlEvent(0,0))
            elif case=='ctrl-key':key(ord('C'),'\x03',control=8)
            else:key(0x79)
            code=p.wait(timeout=8)
        after=snapshot();active_after=current_text()
        report.update(before=before,after=after,active_after=active_after,frames=frames,child_exit=code,case=case)
        if case in ['fault','forced-small','wrong-input']:
            if code!=(4 if case=='fault' else 3):raise AssertionError('Wrong failure exit '+str(code))
        elif code!=0:raise AssertionError('Wrong exit '+str(code))
        # Linear output advances the caller cursor/content; screen output does not,
        # except explicitly switching to linear or reporting an error after cleanup.
        for field in ['handles','codepages','buffer','attributes','cursor_style']:
            if before[field]!=after[field]:raise AssertionError('Caller changed: '+field)
        def extent(rect):return [rect[2]-rect[0]+1,rect[3]-rect[1]+1]
        if extent(before['viewport'])!=extent(after['viewport']):raise AssertionError('Caller viewport resized')
        if case not in ['linear','small','form','mode-linear','health-form','screen'] and before['viewport']!=after['viewport']:raise AssertionError('Caller viewport moved')
        expected=before['modes'][:]
        if case=='external-mode':expected[0]^=0x20
        if after['modes']!=expected:raise AssertionError('Input-mode restoration mismatch')
        if case in ['ctrl-c','ctrl-key','external-mode','resize','inactive-output']:
            if before['cursor']!=after['cursor'] or before['content']!=after['content']:raise AssertionError('Caller screen changed')
        if 'CALLER BUFFER UNCHANGED' not in active_after:raise AssertionError('Original active screen not restored')
    finally:
        if p is not None and p.poll() is None:p.kill();p.wait(timeout=5)
        # Fixture-only cleanup applies exclusively to this newly created console.
        k.SetConsoleActiveScreenBuffer(out);k.SetConsoleMode(k.GetStdHandle(-10),before['modes'][0]);k.SetConsoleCtrlHandler(handler,False)
        if shadow is not None and shadow!=c.c_void_p(-1).value:k.CloseHandle(shadow)


if __name__=='__main__':
    report={};code=0
    try:run(sys.argv[1],sys.argv[3],report)
    except Exception as error:report['fixture_error']=str(error);code=1
    Path(sys.argv[2]).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(code)
