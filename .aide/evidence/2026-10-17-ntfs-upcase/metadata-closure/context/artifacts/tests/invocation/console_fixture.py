"""Run only in a new hidden test-owned console. Never attaches to another console."""
import ctypes as c
from ctypes import wintypes as w
import json
from pathlib import Path
import subprocess
import sys

class Coord(c.Structure):_fields_=[('X',w.SHORT),('Y',w.SHORT)]
class Rect(c.Structure):_fields_=[('Left',w.SHORT),('Top',w.SHORT),('Right',w.SHORT),('Bottom',w.SHORT)]
class Info(c.Structure):_fields_=[('size',Coord),('cursor',Coord),('attributes',w.WORD),('window',Rect),('maximum',Coord)]
k=c.WinDLL('kernel32',use_last_error=True)
k.GetStdHandle.argtypes=[w.DWORD];k.GetStdHandle.restype=w.HANDLE
k.GetConsoleMode.argtypes=[w.HANDLE,c.POINTER(w.DWORD)];k.GetConsoleMode.restype=w.BOOL
k.GetConsoleScreenBufferInfo.argtypes=[w.HANDLE,c.POINTER(Info)];k.GetConsoleScreenBufferInfo.restype=w.BOOL
k.GetConsoleWindow.restype=w.HWND
k.ReadConsoleOutputCharacterW.argtypes=[w.HANDLE,w.LPWSTR,w.DWORD,Coord,c.POINTER(w.DWORD)];k.ReadConsoleOutputCharacterW.restype=w.BOOL

def snapshot():
    result={'window':k.GetConsoleWindow(),'input_cp':k.GetConsoleCP(),'output_cp':k.GetConsoleOutputCP()}
    for name,key in [('stdin',-10),('stdout',-11),('stderr',-12)]:
        handle=k.GetStdHandle(key);mode=w.DWORD()
        if not k.GetConsoleMode(handle,c.byref(mode)):raise RuntimeError('Fixture needs its own console')
        result[name]=[handle,mode.value]
    info=Info()
    if not k.GetConsoleScreenBufferInfo(k.GetStdHandle(-11),c.byref(info)):raise c.WinError(c.get_last_error())
    result['buffer']=[info.size.X,info.size.Y]
    result['viewport']=[info.window.Left,info.window.Top,info.window.Right,info.window.Bottom]
    return result,info

def run(exe,flags):
    before,start=snapshot()
    startup=None
    if '--fixture-wrong-input' in flags:
        flags.remove('--fixture-wrong-input')
        startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESTDHANDLES
        startup.hStdInput=k.GetStdHandle(-11);startup.hStdOutput=k.GetStdHandle(-11);startup.hStdError=k.GetStdHandle(-12)
    result=subprocess.run([exe,'mode','explain',*flags],timeout=10,startupinfo=startup,close_fds=False)
    after,end=snapshot()
    count=(end.cursor.Y-start.cursor.Y)*start.size.X+end.cursor.X-start.cursor.X
    if not 0<count<=8192:raise RuntimeError('Unexpected bounded console output size: '+str(count))
    buffer=c.create_unicode_buffer(count+1);read=w.DWORD()
    if not k.ReadConsoleOutputCharacterW(k.GetStdHandle(-11),buffer,count,start.cursor,c.byref(read)):raise c.WinError(c.get_last_error())
    return dict(before=before,after=after,child_exit=result.returncode,output=buffer[:read.value])

try:
    value=run(sys.argv[1],sys.argv[3:]);code=0
except Exception as error:
    value={'fixture_error':str(error)};code=1
Path(sys.argv[2]).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
raise SystemExit(code)
