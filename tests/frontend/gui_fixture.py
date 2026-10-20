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
import sys
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
bind(U,'GetProcessWindowStation',W.HANDLE,[])
bind(U,'GetUserObjectInformationW',W.BOOL,[W.HANDLE,W.INT,PTR,W.DWORD,C.POINTER(W.DWORD)])
bind(K,'GetCurrentThreadId',W.DWORD,[])
bind(U,'GetWindowThreadProcessId',W.DWORD,[W.HWND,C.POINTER(W.DWORD)])
bind(U,'GetClassNameW',C.c_int,[W.HWND,W.LPWSTR,C.c_int])
bind(U,'GetDlgCtrlID',C.c_int,[W.HWND]);bind(U,'GetDlgItem',W.HWND,[W.HWND,C.c_int])
bind(U,'SendMessageTimeoutW',RESULT,[W.HWND,W.UINT,WP,LP,W.UINT,W.UINT,C.POINTER(WP)])
bind(U,'PostMessageW',W.BOOL,[W.HWND,W.UINT,WP,LP]);bind(U,'IsWindowEnabled',W.BOOL,[W.HWND])
bind(U,'IsWindowVisible',W.BOOL,[W.HWND])
bind(U,'GetWindowRect',W.BOOL,[W.HWND,C.POINTER(W.RECT)]);bind(U,'GetClientRect',W.BOOL,[W.HWND,C.POINTER(W.RECT)])
bind(U,'ClientToScreen',W.BOOL,[W.HWND,C.POINTER(W.POINT)])
bind(U,'RedrawWindow',W.BOOL,[W.HWND,PTR,W.HANDLE,W.UINT])
bind(U,'PrintWindow',W.BOOL,[W.HWND,W.HDC,W.UINT]);bind(U,'GetSysColor',W.DWORD,[C.c_int])
bind(U,'SetWindowPos',W.BOOL,[W.HWND,W.HWND,C.c_int,C.c_int,C.c_int,C.c_int,W.UINT])
bind(G,'CreateCompatibleDC',W.HDC,[W.HDC]);bind(G,'DeleteDC',W.BOOL,[W.HDC])
bind(G,'CreateDIBSection',PTR,[W.HDC,PTR,W.UINT,C.POINTER(PTR),W.HANDLE,W.DWORD])
bind(G,'SelectObject',PTR,[W.HDC,PTR]);bind(G,'DeleteObject',W.BOOL,[PTR])
bind(G,'GdiFlush',W.BOOL,[])
bind(K,'CreateToolhelp32Snapshot',W.HANDLE,[W.DWORD,W.DWORD]);bind(K,'CloseHandle',W.BOOL,[W.HANDLE])

def capture_client_content(payload,width,height,box):
    """Reject a uniform client while ignoring title/frame pixels and DIB alpha.

    This is a private evidence guard, not proof of text, layout or accessibility.
    The live caller measures the client rectangle on its own window.
    """
    left,top,right,bottom=box
    if len(payload)!=width*height*4 or not (0<=left<right<=width and 0<=top<bottom<=height):
        raise ValueError('capture_geometry')
    first=None
    for y in range(top,bottom):
        for (pixel,) in struct.iter_unpack('<I',payload[(y*width+left)*4:(y*width+right)*4]):
            color=pixel & 0xffffff
            if first is None:first=color
            elif color!=first:return True
    return False

def capture_background_matches(payload,width,height,color):
    """The native GUI's unused client perimeter has its solid class background."""
    if (type(width) is not int or type(height) is not int or not 0<width<=4096 or not 0<height<=4096 or
            len(payload)!=width*height*4 or type(color) is not int or not 0<=color<=0xffffff):raise ValueError('capture_background_geometry')
    expected=bytes([(color>>16)&255,(color>>8)&255,color&255])
    edges=set(range(width))|set(range((height-1)*width,height*width))
    edges.update(y*width for y in range(height));edges.update(y*width+width-1 for y in range(height))
    return all(payload[index*4:index*4+3]==expected for index in edges)


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

def owned_desktop():
    """New hidden desktop, explicitly owned by this user and SYSTEM.

    NULL security inherits the station's entries, which need not admit this
    restricted user when a child opens the desktop during User32 startup.
    """
    station=C.create_unicode_buffer(1024);needed=W.DWORD()
    if not U.GetUserObjectInformationW(U.GetProcessWindowStation(),2,station,C.sizeof(station),C.byref(needed)):
        raise C.WinError(C.get_last_error())
    if not station.value or '\\' in station.value:raise ValueError('Invalid current window station name')
    A=C.WinDLL('advapi32',use_last_error=True)
    bind(K,'GetCurrentProcess',W.HANDLE,[]);bind(K,'LocalFree',PTR,[PTR])
    bind(A,'OpenProcessToken',W.BOOL,[W.HANDLE,W.DWORD,C.POINTER(W.HANDLE)])
    bind(A,'GetTokenInformation',W.BOOL,[W.HANDLE,C.c_int,PTR,W.DWORD,C.POINTER(W.DWORD)])
    bind(A,'ConvertSidToStringSidW',W.BOOL,[PTR,C.POINTER(W.LPWSTR)])
    bind(A,'ConvertStringSecurityDescriptorToSecurityDescriptorW',W.BOOL,[W.LPCWSTR,W.DWORD,C.POINTER(PTR),PTR])
    class Attributes(C.Structure):_fields_=[('length',W.DWORD),('descriptor',PTR),('inherit',W.BOOL)]
    token=W.HANDLE();text=W.LPWSTR();descriptor=PTR()
    try:
        if not A.OpenProcessToken(K.GetCurrentProcess(),8,C.byref(token)):raise C.WinError(C.get_last_error())
        size=W.DWORD();A.GetTokenInformation(token,1,None,0,C.byref(size))
        if not 0<size.value<=4096:raise ValueError('Test desktop token bound')
        data=C.create_string_buffer(size.value)
        if not A.GetTokenInformation(token,1,data,size,C.byref(size)):raise C.WinError(C.get_last_error())
        sid=C.cast(data,C.POINTER(PTR))[0]
        if not A.ConvertSidToStringSidW(sid,C.byref(text)):raise C.WinError(C.get_last_error())
        sddl='D:P(A;;0xf01ff;;;SY)(A;;0xf01ff;;;'+text.value+')S:(ML;;NW;;;ME)'
        coordinator=os.environ.get('DISKED_WINDOW_CAPTURE_COORDINATOR_SID')
        if coordinator:
            import re
            if not re.fullmatch(r'S-1-5-21-(?:[0-9]+-){3}[0-9]+',coordinator):raise ValueError('Capture coordinator SID')
            sddl=sddl.replace('S:(ML;', '(A;;0xf01ff;;;'+coordinator+')S:(ML;')
        if not A.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl,1,C.byref(descriptor),None):raise C.WinError(C.get_last_error())
        attributes=Attributes(C.sizeof(Attributes),descriptor,False);name='DiskEdTest-'+uuid.uuid4().hex
        desktop=U.CreateDesktopW(name,None,None,0,0xf01ff,C.byref(attributes))
        if not desktop:raise C.WinError(C.get_last_error())
        return desktop,station.value+'\\'+name
    finally:
        if descriptor:K.LocalFree(descriptor)
        if text:K.LocalFree(C.cast(text,PTR))
        if token:K.CloseHandle(token)

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

def write_capture(path,payload,width,height):
    if len(payload)!=width*height*4:raise ValueError('Capture output length')
    if Path(path).suffix.lower()=='.png':
        def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
        rows=bytearray()
        for y in range(height):
            rows.append(0);row=payload[y*width*4:(y+1)*width*4];rgb=bytearray(width*3)
            rgb[0::3]=row[2::4];rgb[1::3]=row[1::4];rgb[2::3]=row[0::4];rows.extend(rgb)
        Path(path).write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b''))
    else:
        header=struct.pack('<IiiHHIIiiII',40,width,-height,1,32,0,width*height*4,0,0,0,0)
        Path(path).write_bytes(struct.pack('<2sIHHI',b'BM',54+len(payload),0,0,54)+header+payload)


class Gui:
    def __init__(self,exe,args=None,render=False):
        self.temp=tempfile.TemporaryDirectory(prefix='disked-gui-');self.window=None;self.desktop=None;self.previous_desktop=None
        startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
        if render:
            # The desktop is never switched onto the user's display. Windows
            # can paint real controls there without capturing another app.
            self.desktop,startup.lpDesktop=owned_desktop()
            self.previous_desktop=U.GetThreadDesktop(K.GetCurrentThreadId())
            if not U.SetThreadDesktop(self.desktop):raise OSError(C.get_last_error(),'test thread desktop')
            startup.wShowWindow=4
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
    def set_field(self,name,value):
        # Locate the rendered semantic label; schema mode controls can add pages.
        for _ in range(8):
            if not U.IsWindowEnabled(self.child(113)):break
            self.click(113)
        for _ in range(8):
            for index in range(2):
                label=self.child(220+index)
                if U.IsWindowVisible(label) and caption(label).split(' ',1)[-1]==name:
                    self.set(200+index,value);return
            if not U.IsWindowEnabled(self.child(114)):break
            self.click(114)
        raise AssertionError('No rendered field named '+name)
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
        pid=W.DWORD();assert U.GetWindowThreadProcessId(self.window,C.byref(pid))
        assert self.process.poll() is None and pid.value==self.process.pid
        rect=W.RECT();assert U.GetWindowRect(self.window,C.byref(rect));w=rect.right-rect.left;h=rect.bottom-rect.top
        assert 0<w<=4096 and 0<h<=4096
        client=W.RECT();origin=W.POINT();assert U.GetClientRect(self.window,C.byref(client)) and U.ClientToScreen(self.window,C.byref(origin))
        left=origin.x-rect.left;top=origin.y-rect.top
        box=(left,top,left+client.right-client.left,top+client.bottom-client.top)
        cooperative=bool(os.environ.get('DISKED_WINDOW_CAPTURE_ROOT'))
        base_x,base_y=rect.left,rect.top
        if cooperative:w,h=client.right,client.bottom;box=(0,0,w,h);base_x,base_y=origin.x,origin.y
        captions=[];caption_details=[]
        @CALLBACK
        def button(hwnd,_):
            if classname(hwnd)=='Button' and U.IsWindowVisible(hwnd) and caption(hwnd).strip():
                bounds=W.RECT();assert U.GetWindowRect(hwnd,C.byref(bounds))
                # Exclude button borders/focus rings: they can be painted even
                # when a declared caption is absent from PrintWindow output.
                region=(max(box[0],bounds.left-base_x+6),max(box[1],bounds.top-base_y+6),
                    min(box[2],bounds.right-base_x-6),min(box[3],bounds.bottom-base_y-6))
                if region[0]<region[2] and region[1]<region[3]:
                    captions.append(region);caption_details.append(dict(id=U.GetDlgCtrlID(hwnd),text=caption(hwnd),bounds=list(region)))
            return True
        assert U.EnumChildWindows(self.window,button,0)
        if cooperative:
            sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
            from support.window_capture import capture,METHOD
            name=C.create_unicode_buffer(256);needed=W.DWORD();thread=U.GetWindowThreadProcessId(self.window,C.byref(pid))
            assert U.GetUserObjectInformationW(U.GetThreadDesktop(thread),2,name,C.sizeof(name),C.byref(needed))
            assert U.RedrawWindow(self.window,None,None,0x585)
            payload,receipt=capture(self.window,pid.value,name.value,w,h,metadata=True)
            # Save the actual observation before evaluating it. The campaign
            # archives the build output even when a caption assertion fails.
            write_capture(path,payload,w,h)
            client_painted=capture_client_content(payload,w,h,box)
            background_color=U.GetSysColor(15);background_matches=capture_background_matches(payload,w,h,background_color)
            regions=[dict(row,painted=capture_client_content(payload,w,h,b)) for row,b in zip(caption_details,captions)]
            Path(path).with_suffix('.capture.json').write_text(json.dumps(dict(width=w,height=h,client_box=list(box),
                client_painted=client_painted,background_color=background_color,background_matches=background_matches,caption_regions=regions,frame_bounds=[rect.left,rect.top,rect.right,rect.bottom],
                capture_receipt=receipt),indent=2)+'\n',encoding='utf-8',newline='\n')
            assert receipt['client_box']==list(box) and receipt['frame_bounds']==[rect.left,rect.top,rect.right,rect.bottom]
            assert client_painted and background_matches and all(row['painted'] for row in regions),'Cooperative client/caption/background pixels incomplete'
            import hashlib
            return dict(width=w,height=h,client_box=list(box),caption_boxes=[list(b) for b in captions],frame_bounds=receipt['frame_bounds'],
                background_color=background_color,background_matches=background_matches,capture_method=METHOD,pixels_sha256=hashlib.sha256(payload).hexdigest(),capture_receipt=receipt)
        header=struct.pack('<IiiHHIIiiII',40,w,-h,1,32,0,w*h*4,0,0,0,0)
        info=C.create_string_buffer(header);bits=PTR();dc=G.CreateCompatibleDC(None)
        assert dc,('CreateCompatibleDC',C.get_last_error())
        bitmap=G.CreateDIBSection(dc,info,0,C.byref(bits),None,0);old=None
        try:
            assert bitmap and bits,('CreateDIBSection',C.get_last_error())
            old=G.SelectObject(dc,bitmap)
            assert old not in (None,C.c_void_p(-1).value),('SelectObject',C.get_last_error())
            paint_status={}
            def painted():
                # Invalidate/erase/frame/all children, then process owned paint.
                # A successful PrintWindow can otherwise contain only a frame.
                assert U.RedrawWindow(self.window,None,None,0x585)
                assert U.PrintWindow(self.window,dc,0);G.GdiFlush()
                value=C.string_at(bits,w*h*4)
                client_ok=capture_client_content(value,w,h,box)
                caption_ok=[capture_client_content(value,w,h,b) for b in captions]
                paint_status.update(capture=Path(path).name,print_flags=0,
                    capture_method='PrintWindow',width=w,height=h,client_box=box,client_painted=client_ok,
                    caption_boxes=captions,caption_painted=caption_ok,whole_window_varied=capture_client_content(value,w,h,(0,0,w,h)),first_bgr=value[:3].hex())
                return value if client_ok and all(caption_ok) else None
            try:payload=wait(painted,3)
            except TimeoutError as error:
                # Diagnostic-only alternatives never replace a failed capture.
                # All requests address this fixture's own window and memory DC.
                alternatives=[]
                for method in ('PrintWindow0','PrintWindow2','WM_PRINT'):
                    C.memset(bits,0,w*h*4)
                    assert U.RedrawWindow(self.window,None,None,0x585)
                    if method=='WM_PRINT':send(self.window,0x317,dc,0x1e)
                    else:assert U.PrintWindow(self.window,dc,0 if method=='PrintWindow0' else 2)
                    G.GdiFlush();value=C.string_at(bits,w*h*4)
                    alternatives.append(dict(method=method,client_painted=capture_client_content(value,w,h,box),
                        caption_painted=[capture_client_content(value,w,h,b) for b in captions]))
                paint_status['diagnostic_only_profiles']=alternatives
                raise AssertionError('Owned window capture content incomplete: '+json.dumps(paint_status)) from error
            write_capture(path,payload,w,h)
            import hashlib
            return dict(width=w,height=h,client_box=list(box),caption_boxes=[list(b) for b in captions],
                capture_method=paint_status['capture_method'],pixels_sha256=hashlib.sha256(payload).hexdigest())
        finally:
            if old not in (None,C.c_void_p(-1).value):G.SelectObject(dc,old)
            if bitmap:G.DeleteObject(bitmap)
            G.DeleteDC(dc)
    def close(self):
        if self.window and self.process.poll() is None:U.PostMessageW(self.window,0x10,0,0)
        try:
            self.output,self.error=self.process.communicate(timeout=5);self.code=self.process.returncode
        except subprocess.TimeoutExpired:self.process.kill();self.output,self.error=self.process.communicate();self.code=self.process.returncode
        self.created_files=[p.name for p in Path(self.temp.name).iterdir()];self.temp.cleanup()
        if self.desktop:
            assert U.SetThreadDesktop(self.previous_desktop)
            assert U.CloseDesktop(self.desktop);self.desktop=None
