"""Owned borderless control with explicit WM_PAINT/WM_PRINT drawing, two phases."""
import ctypes as C
from ctypes import wintypes as T
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sys
import threading
import time
import uuid


def main():
    if socket.gethostname().casefold()!='blackglass-hyperv':
        raise ValueError('Pixel control is guest-only')
    seed=os.environ['DISKED_PIXEL_CHALLENGE']
    if not re.fullmatch('[0-9a-f]{32}',seed):raise ValueError('Fixed challenge required')
    colors=[[hashlib.sha256(b'DiskEd pixel-origin/1\0'+bytes.fromhex(seed)+bytes((phase,i))).digest()[:3]
             for i in range(16)] for phase in (0,1)]
    sys.path.insert(0,str(Path(__file__).parent/'source/tests/frontend'))
    import gui_fixture as fixture
    u,g,k=fixture.U,fixture.G,fixture.K
    def bind(dll,name,result,*args):
        f=getattr(dll,name);f.restype=result;f.argtypes=list(args);return f
    def checked(value):
        if not value:raise C.WinError(C.get_last_error())
        return value
    callback=C.WINFUNCTYPE(C.c_ssize_t,T.HWND,T.UINT,C.c_size_t,C.c_ssize_t)
    class WindowClass(C.Structure):
        _fields_=[('size',T.UINT),('style',T.UINT),('proc',callback),('class_extra',C.c_int),
                  ('window_extra',C.c_int),('instance',T.HINSTANCE),('icon',T.HANDLE),
                  ('cursor',T.HANDLE),('background',T.HBRUSH),('menu',T.LPCWSTR),
                  ('name',T.LPCWSTR),('small_icon',T.HANDLE)]
    class Paint(C.Structure):
        _fields_=[('dc',T.HDC),('erase',T.BOOL),('rect',T.RECT),('restore',T.BOOL),
                  ('update',T.BOOL),('reserved',T.BYTE*32)]
    bind(k,'GetModuleHandleW',T.HINSTANCE,T.LPCWSTR)
    bind(u,'RegisterClassExW',T.ATOM,C.POINTER(WindowClass))
    bind(u,'UnregisterClassW',T.BOOL,T.LPCWSTR,T.HINSTANCE)
    bind(u,'DefWindowProcW',C.c_ssize_t,T.HWND,T.UINT,C.c_size_t,C.c_ssize_t)
    bind(u,'CreateWindowExW',T.HWND,T.DWORD,T.LPCWSTR,T.LPCWSTR,T.DWORD,C.c_int,C.c_int,
         C.c_int,C.c_int,T.HWND,T.HMENU,T.HINSTANCE,T.LPVOID)
    bind(u,'DestroyWindow',T.BOOL,T.HWND)
    bind(u,'IsWindow',T.BOOL,T.HWND)
    bind(u,'BeginPaint',T.HDC,T.HWND,C.POINTER(Paint));bind(u,'EndPaint',T.BOOL,T.HWND,C.POINTER(Paint))
    bind(u,'FillRect',C.c_int,T.HDC,C.POINTER(T.RECT),T.HBRUSH)
    bind(g,'CreateSolidBrush',T.HBRUSH,T.DWORD);bind(g,'GetObjectType',T.DWORD,T.HANDLE)
    bind(u,'GetMessageW',C.c_int,C.POINTER(T.MSG),T.HWND,T.UINT,T.UINT)
    bind(u,'TranslateMessage',T.BOOL,C.POINTER(T.MSG));bind(u,'DispatchMessageW',C.c_ssize_t,C.POINTER(T.MSG))
    bind(u,'PostQuitMessage',None,C.c_int)
    bind(u,'SetTimer',C.c_size_t,T.HWND,C.c_size_t,T.UINT,T.LPVOID)
    bind(u,'KillTimer',T.BOOL,T.HWND,C.c_size_t)
    bind(u,'SetThreadDpiAwarenessContext',T.HANDLE,T.HANDLE)
    previous=u.GetThreadDesktop(k.GetCurrentThreadId());dpi=checked(u.SetThreadDpiAwarenessContext(T.HANDLE(-4)))
    desktop,full_name=fixture.owned_desktop();checked(u.SetThreadDesktop(desktop))
    phase=0;ready=threading.Event();report=dict(phases=[],paint_calls=[],display_dc_read=False,desktop_switched=False)
    hwnd=None;runner=None;atom=None;instance=k.GetModuleHandleW(None)

    def draw(dc,message):
        success=0;errors=[]
        printing=message in (0x317,0x318)
        path=Path(os.environ['TEMP'])/('pixel-paint-'+str(phase)+'.json')
        if printing:
            path.write_text(json.dumps(dict(phase=phase,message=message,entered=True,
                dc_type=g.GetObjectType(dc),draw_completed=False))+'\n',encoding='utf-8',newline='\n')
        for i,rgb in enumerate(colors[phase]):
            brush=checked(g.CreateSolidBrush(rgb[0]|rgb[1]<<8|rgb[2]<<16))
            try:
                x=(i%4)*60;y=(i//4)*24;rect=T.RECT(x,y,x+60,y+24);C.set_last_error(0)
                if u.FillRect(dc,C.byref(rect),brush):success+=1
                else:errors.append(C.get_last_error())
            finally:g.DeleteObject(brush)
        if printing:
            row=dict(phase=phase,message=message,entered=True,draw_completed=True,
                     dc_type=g.GetObjectType(dc),filled_tiles=success,errors=errors)
            report['paint_calls'].append(row)
            if len(report['paint_calls'])>8:raise ValueError('Print message count bound')
            path.write_text(json.dumps(row)+'\n',encoding='utf-8',newline='\n')
        return success==16

    @callback
    def procedure(window,message,wp,lp):
        nonlocal phase
        try:
            if message==0x8001:
                if wp not in (0,1):raise ValueError('Invalid phase')
                phase=wp;checked(u.RedrawWindow(window,None,None,0x185));ready.set();return 0
            if message==0xf:
                paint=Paint();dc=checked(u.BeginPaint(window,C.byref(paint)))
                try:draw(dc,message)
                finally:u.EndPaint(window,C.byref(paint))
                return 0
            if message in (0x317,0x318):draw(T.HDC(wp),message);g.GdiFlush();return 0
            if message==0x113:
                report['error']='Control deadline';u.DestroyWindow(window);return 0
            if message==0x10:u.DestroyWindow(window);return 0
            if message==2:u.PostQuitMessage(0);return 0
            return u.DefWindowProcW(window,message,wp,lp)
        except BaseException as error:
            report['error']=repr(error);u.PostQuitMessage(1);ready.set();return 0

    def request_pixels():
        prior=u.GetThreadDesktop(k.GetCurrentThreadId())
        try:
            checked(u.SetThreadDesktop(desktop))
            root=Path(os.environ['DISKED_WINDOW_CAPTURE_ROOT'])
            if root.resolve()!=Path(os.environ['TEMP']).resolve():raise ValueError('Owned temp required')
            for requested in (0,1):
                ready.clear();checked(u.PostMessageW(hwnd,0x8001,requested,0))
                if not ready.wait(3) or report.get('error'):raise RuntimeError('Control paint not ready')
                ident=uuid.uuid4().hex;request=root/('window-capture-request-'+ident+'.json')
                response=root/('window-capture-response-'+ident+'.json');nonce=os.environ['DISKED_WINDOW_CAPTURE_NONCE']
                with request.open('x',encoding='utf-8') as stream:
                    json.dump(dict(nonce=nonce,id=ident,window=hwnd,pid=os.getpid(),desktop=full_name.split('\\')[-1]),stream)
                request.with_suffix('.ready').touch(exist_ok=False);until=time.monotonic()+12
                while not response.with_suffix('.ready').exists():
                    if time.monotonic()>until:raise TimeoutError('Control producer reply')
                    time.sleep(.02)
                if response.stat().st_size>4096 or response.with_suffix('.bgra').stat().st_size!=92160:raise ValueError('Reply size')
                value=json.loads(response.read_bytes());body=response.with_suffix('.bgra').read_bytes()
                if (value['nonce']!=nonce or value['id']!=ident or value['window']!=hwnd or value['pid']!=os.getpid() or
                        value['desktop']!=full_name.split('\\')[-1] or value['method']!='owned-wm-print-control/1' or
                        (value['width'],value['height'])!=(240,96) or value['bytes']!=92160 or
                        value['sha256']!=hashlib.sha256(body).hexdigest()):raise ValueError('Reply identity or bytes')
                report['phases'].append(dict(phase=requested,bytes=len(body),sha256=value['sha256']))
                for path in (response,response.with_suffix('.bgra'),response.with_suffix('.ready')):path.unlink()
        except BaseException as error:report['error']=repr(error)
        finally:
            u.PostMessageW(hwnd,0x10,0,0)
            if not u.SetThreadDesktop(prior):report['error']='Request-thread desktop restoration failed'

    try:
        definition=WindowClass(C.sizeof(WindowClass),0,procedure,0,0,instance,None,None,None,None,'DiskEdPixelOriginControl',None)
        atom=checked(u.RegisterClassExW(C.byref(definition)))
        hwnd=checked(u.CreateWindowExW(0,definition.name,'Owned pixel-origin control',0x90000000,
                                       0,0,240,96,None,None,instance,None))
        checked(u.SetTimer(hwnd,1,20000,None))
        runner=threading.Thread(target=request_pixels,daemon=True);runner.start()
        message=T.MSG()
        while True:
            code=u.GetMessageW(C.byref(message),None,0,0)
            if code==-1:raise C.WinError(C.get_last_error())
            if code==0:break
            u.TranslateMessage(C.byref(message));u.DispatchMessageW(C.byref(message))
        runner.join(2)
        if runner.is_alive():raise RuntimeError('Control request thread did not retire')
        report['passed']=not report.get('error') and len(report['phases'])==2
        print(json.dumps(report))
        return 0 if report['passed'] else 1
    finally:
        if hwnd and u.IsWindow(hwnd):u.KillTimer(hwnd,1);u.DestroyWindow(hwnd)
        if atom:u.UnregisterClassW('DiskEdPixelOriginControl',instance)
        checked(u.SetThreadDesktop(previous));checked(u.CloseDesktop(desktop))
        checked(u.SetThreadDpiAwarenessContext(dpi))


if __name__=='__main__':raise SystemExit(main())
