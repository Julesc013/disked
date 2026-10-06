"""Inspect only the hidden native window launched by this fixture.

No input is sent to the foreground desktop and no global setting is changed.
"""
import ctypes as C
from ctypes import wintypes as W
import json
import msvcrt
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import time
import uuid
import zlib

U=C.WinDLL('user32',use_last_error=True);G=C.WinDLL('gdi32',use_last_error=True);K=C.WinDLL('kernel32',use_last_error=True)
PTR=C.c_void_p;RESULT=C.c_ssize_t;WP=C.c_size_t;LP=C.c_ssize_t
CALLBACK=C.WINFUNCTYPE(W.BOOL,W.HWND,LP)
def bind(dll,name,result,args):
    f=getattr(dll,name);f.restype=result;f.argtypes=args;return f
bind(U,'EnumWindows',W.BOOL,[CALLBACK,LP]);bind(U,'EnumChildWindows',W.BOOL,[W.HWND,CALLBACK,LP])
bind(U,'CreateDesktopW',W.HANDLE,[W.LPCWSTR,W.LPCWSTR,PTR,W.DWORD,W.DWORD,PTR])
bind(U,'CloseDesktop',W.BOOL,[W.HANDLE]);bind(U,'EnumDesktopWindows',W.BOOL,[W.HANDLE,CALLBACK,LP])
bind(U,'GetThreadDesktop',W.HANDLE,[W.DWORD]);bind(U,'SetThreadDesktop',W.BOOL,[W.HANDLE])
bind(K,'GetCurrentThreadId',W.DWORD,[])
bind(U,'GetWindowThreadProcessId',W.DWORD,[W.HWND,C.POINTER(W.DWORD)])
bind(U,'GetClassNameW',C.c_int,[W.HWND,W.LPWSTR,C.c_int])
bind(U,'GetDlgCtrlID',C.c_int,[W.HWND]);bind(U,'GetDlgItem',W.HWND,[W.HWND,C.c_int])
bind(U,'SendMessageTimeoutW',RESULT,[W.HWND,W.UINT,WP,LP,W.UINT,W.UINT,C.POINTER(WP)])
bind(U,'PostMessageW',W.BOOL,[W.HWND,W.UINT,WP,LP]);bind(U,'IsWindowEnabled',W.BOOL,[W.HWND])
bind(U,'IsWindowVisible',W.BOOL,[W.HWND])
bind(U,'GetWindowRect',W.BOOL,[W.HWND,C.POINTER(W.RECT)]);bind(U,'GetClientRect',W.BOOL,[W.HWND,C.POINTER(W.RECT)])
bind(U,'PrintWindow',W.BOOL,[W.HWND,W.HDC,W.UINT]);bind(U,'GetSysColor',W.DWORD,[C.c_int])
bind(U,'SetWindowPos',W.BOOL,[W.HWND,W.HWND,C.c_int,C.c_int,C.c_int,C.c_int,W.UINT])
bind(G,'CreateCompatibleDC',W.HDC,[W.HDC]);bind(G,'DeleteDC',W.BOOL,[W.HDC])
bind(G,'CreateDIBSection',PTR,[W.HDC,PTR,W.UINT,C.POINTER(PTR),W.HANDLE,W.DWORD])
bind(G,'SelectObject',PTR,[W.HDC,PTR]);bind(G,'DeleteObject',W.BOOL,[PTR])
bind(G,'GdiFlush',W.BOOL,[])
bind(K,'CreateToolhelp32Snapshot',W.HANDLE,[W.DWORD,W.DWORD]);bind(K,'CloseHandle',W.BOOL,[W.HANDLE])

class GUIINFO(C.Structure):
    _fields_=[('cbSize',W.DWORD),('flags',W.DWORD),('active',W.HWND),('focus',W.HWND),('capture',W.HWND),('menu',W.HWND),('move',W.HWND),('caret',W.HWND),('caretRect',W.RECT)]
bind(U,'GetGUIThreadInfo',W.BOOL,[W.DWORD,C.POINTER(GUIINFO)])
class MODULE(C.Structure):
    _fields_=[('dwSize',W.DWORD),('id',W.DWORD),('pid',W.DWORD),('globalUsage',W.DWORD),('processUsage',W.DWORD),('base',PTR),('size',W.DWORD),('module',W.HMODULE),('name',W.WCHAR*256),('path',W.WCHAR*260)]
bind(K,'Module32FirstW',W.BOOL,[W.HANDLE,C.POINTER(MODULE)]);bind(K,'Module32NextW',W.BOOL,[W.HANDLE,C.POINTER(MODULE)])
class STARTUP(C.Structure):
    _fields_=[('cb',W.DWORD),('reserved',W.LPWSTR),('desktop',W.LPWSTR),('title',W.LPWSTR),
              ('x',W.DWORD),('y',W.DWORD),('width',W.DWORD),('height',W.DWORD),('charsX',W.DWORD),('charsY',W.DWORD),
              ('fill',W.DWORD),('flags',W.DWORD),('show',W.WORD),('reserved2size',W.WORD),('reserved2',PTR),
              ('input',W.HANDLE),('output',W.HANDLE),('error',W.HANDLE)]
class PROCESS(C.Structure):
    _fields_=[('process',W.HANDLE),('thread',W.HANDLE),('pid',W.DWORD),('tid',W.DWORD)]
bind(K,'CreateProcessW',W.BOOL,[W.LPCWSTR,W.LPWSTR,PTR,PTR,W.BOOL,W.DWORD,PTR,W.LPCWSTR,C.POINTER(STARTUP),C.POINTER(PROCESS)])
bind(K,'WaitForSingleObject',W.DWORD,[W.HANDLE,W.DWORD]);bind(K,'GetExitCodeProcess',W.BOOL,[W.HANDLE,C.POINTER(W.DWORD)])
bind(K,'TerminateProcess',W.BOOL,[W.HANDLE,W.UINT])
class DesktopProcess:
    """CreateProcess wrapper because subprocess.STARTUPINFO omits lpDesktop."""
    def __init__(self,args,cwd,desktop):
        ir,iw=os.pipe();orr,ow=os.pipe();er,ew=os.pipe();info=PROCESS();startup=STARTUP();startup.cb=C.sizeof(startup)
        startup.desktop=desktop;startup.flags=0x101;startup.show=4
        for fd in [ir,ow,ew]:os.set_inheritable(fd,True)
        startup.input=msvcrt.get_osfhandle(ir);startup.output=msvcrt.get_osfhandle(ow);startup.error=msvcrt.get_osfhandle(ew)
        try:
            command=C.create_unicode_buffer(subprocess.list2cmdline(args))
            if not K.CreateProcessW(args[0],command,None,None,True,0,None,cwd,C.byref(startup),C.byref(info)):
                raise OSError(C.get_last_error(),'test GUI process')
        except BaseException:
            for fd in [iw,orr,er]:os.close(fd)
            raise
        finally:
            for fd in [ir,ow,ew]:os.close(fd)
        K.CloseHandle(info.thread);self.handle=info.process;self.pid=info.pid;self.returncode=None
        self.stdin=os.fdopen(iw,'wb');self.stdout=os.fdopen(orr,'rb');self.stderr=os.fdopen(er,'rb')
    def poll(self):
        if self.returncode is None and K.WaitForSingleObject(self.handle,0)==0:
            code=W.DWORD();assert K.GetExitCodeProcess(self.handle,C.byref(code));self.returncode=code.value
        return self.returncode
    def kill(self):K.TerminateProcess(self.handle,99)
    def communicate(self,timeout=5):
        self.stdin.close()
        if K.WaitForSingleObject(self.handle,int(timeout*1000))!=0:raise subprocess.TimeoutExpired('test GUI',timeout)
        self.poll();out=self.stdout.read();err=self.stderr.read();self.stdout.close();self.stderr.close();K.CloseHandle(self.handle)
        return out,err
def modules(pid):
    for _ in range(40):
        handle=K.CreateToolhelp32Snapshot(0x18,pid)
        if handle!=C.c_void_p(-1).value or C.get_last_error()!=24:break
        time.sleep(.02) # ERROR_BAD_LENGTH: loader changed during the snapshot.
    if handle==C.c_void_p(-1).value:raise OSError(C.get_last_error(),'module snapshot')
    try:
        row=MODULE();row.dwSize=C.sizeof(row);result={};more=K.Module32FirstW(handle,C.byref(row))
        if not more:raise OSError(C.get_last_error(),'module first')
        while more:
            result[row.name.lower()]=row.path;more=K.Module32NextW(handle,C.byref(row))
        return result
    finally:K.CloseHandle(handle)

def send(hwnd,message,wp=0,lp=0):
    result=WP()
    if not U.SendMessageTimeoutW(hwnd,message,wp,lp,2,3000,C.byref(result)):raise OSError(C.get_last_error(),'window message')
    return RESULT(result.value).value
def caption(hwnd):
    size=send(hwnd,0xE)
    if size>1048576:raise ValueError('unbounded window text')
    buffer=C.create_unicode_buffer(size+1);send(hwnd,0xD,size+1,C.addressof(buffer));return buffer.value
def classname(hwnd):
    buffer=C.create_unicode_buffer(256);U.GetClassNameW(hwnd,buffer,256);return buffer.value
def wait(predicate,seconds=8):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        result=predicate()
        if result:return result
        time.sleep(.02)
    raise TimeoutError('native window observation')

class Gui:
    def __init__(self,exe,args=None,render=False):
        self.temp=tempfile.TemporaryDirectory(prefix='disked-gui-');self.window=None;self.desktop=None;self.previous_desktop=None
        startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
        if render:
            # The desktop is never switched onto the user's display. Windows
            # can paint real controls there without capturing another app.
            name='DiskEdTest-'+uuid.uuid4().hex;self.desktop=U.CreateDesktopW(name,None,None,0,0x1FF,None)
            if not self.desktop:raise OSError(C.get_last_error(),'test desktop')
            self.previous_desktop=U.GetThreadDesktop(K.GetCurrentThreadId())
            if not U.SetThreadDesktop(self.desktop):raise OSError(C.get_last_error(),'test thread desktop')
            startup.lpDesktop='WinSta0\\'+name;startup.wShowWindow=4
        argv=[str(exe),*(args or ['gui'])]
        if render:self.process=DesktopProcess(argv,self.temp.name,startup.lpDesktop)
        else:self.process=subprocess.Popen(argv,cwd=self.temp.name,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,startupinfo=startup)
        try:self.window=wait(self.find)
        except BaseException:self.close();raise
    def find(self):
        if self.process.poll() is not None:raise RuntimeError('GUI exited: '+str(self.process.returncode)+' '+self.process.stderr.read().decode(errors='replace'))
        windows=[]
        @CALLBACK
        def check(hwnd,_):
            pid=W.DWORD();U.GetWindowThreadProcessId(hwnd,C.byref(pid))
            if pid.value==self.process.pid and classname(hwnd)=='DiskEd.Native.Fake.1' and U.GetDlgItem(hwnd,103):
                if not self.desktop or U.IsWindowVisible(hwnd):windows.append(hwnd)
            return True
        if self.desktop:U.EnumDesktopWindows(self.desktop,check,0)
        else:U.EnumWindows(check,0)
        return windows[0] if windows else None
    def child(self,id):
        child=U.GetDlgItem(self.window,id)
        if not child:raise AssertionError('missing child '+str(id))
        return child
    def text(self,id):return caption(self.child(id))
    def details(self):return json.loads(self.text(101))
    def click(self,id):send(self.child(id),0xF5)
    def set(self,id,value):
        buffer=C.create_unicode_buffer(value);send(self.child(id),0xC,0,C.addressof(buffer))
    def list_ids(self):
        child=self.child(100);count=send(child,0x18B);result=[]
        for i in range(count):
            size=send(child,0x18A,i);buffer=C.create_unicode_buffer(size+1);send(child,0x189,i,C.addressof(buffer));result.append(buffer.value)
        return result
    def choose(self,index):
        send(self.child(100),0x186,index);send(self.window,0x111,(1<<16)|100,self.child(100))
    def focus(self):
        info=GUIINFO();info.cbSize=C.sizeof(info);thread=U.GetWindowThreadProcessId(self.window,None)
        if not U.GetGUIThreadInfo(thread,C.byref(info)):raise OSError(C.get_last_error(),'GUI thread info')
        return info.focus
    def key(self,key,hwnd=None,repeat=False):
        target=hwnd or self.focus() or self.child(100)
        if not U.PostMessageW(target,0x100,key,1|((1<<30) if repeat else 0)):raise OSError(C.get_last_error(),'key down')
        if not U.PostMessageW(target,0x101,key,(1<<30)|(1<<31)|1):raise OSError(C.get_last_error(),'key up')
        # A synchronous round trip observes messages already dispatched; wait
        # for asynchronous keyboard processing before inspecting its effect.
        time.sleep(.04)
    def observation(self):
        children=[]
        @CALLBACK
        def collect(hwnd,_):
            children.append(dict(id=U.GetDlgCtrlID(hwnd),role=classname(hwnd),enabled=bool(U.IsWindowEnabled(hwnd)),font=send(hwnd,0x31)));return True
        U.EnumChildWindows(self.window,collect,0)
        return dict(pid=self.process.pid,title=caption(self.window),children=children,notice=self.text(103),modules=modules(self.process.pid),
                    colors={str(i):U.GetSysColor(i) for i in [5,8,15,18]},created_files=[p.name for p in Path(self.temp.name).iterdir()])
    def screenshot(self,path):
        rect=W.RECT();assert U.GetWindowRect(self.window,C.byref(rect));w=rect.right-rect.left;h=rect.bottom-rect.top
        assert 0<w<=4096 and 0<h<=4096
        header=struct.pack('<IiiHHIIiiII',40,w,-h,1,32,0,w*h*4,0,0,0,0)
        info=C.create_string_buffer(header);bits=PTR();dc=G.CreateCompatibleDC(None)
        bitmap=G.CreateDIBSection(dc,info,0,C.byref(bits),None,0);old=G.SelectObject(dc,bitmap)
        try:
            assert bitmap
            def painted():
                assert U.PrintWindow(self.window,dc,2);G.GdiFlush()
                value=C.string_at(bits,w*h*4)
                return value if len(set(struct.iter_unpack('<I',value)))>10 else None
            payload=wait(painted,3)
            if Path(path).suffix.lower()=='.png':
                def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
                rows=bytearray()
                for y in range(h):
                    rows.append(0);row=payload[y*w*4:(y+1)*w*4];rgb=bytearray(w*3)
                    rgb[0::3]=row[2::4];rgb[1::3]=row[1::4];rgb[2::3]=row[0::4];rows.extend(rgb)
                Path(path).write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b''))
            else:Path(path).write_bytes(struct.pack('<2sIHHI',b'BM',54+len(payload),0,0,54)+header+payload)
        finally:G.SelectObject(dc,old);G.DeleteObject(bitmap);G.DeleteDC(dc)
    def close(self):
        if self.window and self.process.poll() is None:U.PostMessageW(self.window,0x10,0,0)
        try:
            self.output,self.error=self.process.communicate(timeout=5);self.code=self.process.returncode
        except subprocess.TimeoutExpired:self.process.kill();self.output,self.error=self.process.communicate();self.code=self.process.returncode
        self.created_files=[p.name for p in Path(self.temp.name).iterdir()];self.temp.cleanup()
        if self.desktop:
            assert U.SetThreadDesktop(self.previous_desktop)
            assert U.CloseDesktop(self.desktop);self.desktop=None
