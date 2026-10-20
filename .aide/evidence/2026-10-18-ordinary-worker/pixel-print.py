"""Print only the independently specified owned popup; never read a display DC."""
import ctypes as C
from ctypes import wintypes as T
import hashlib
import json
import re
import socket
import struct
import sys

METHOD='owned-print-control/1'


def capture(window,pid,desktop):
    if (socket.gethostname().casefold()!='blackglass-hyperv' or
            type(window) is not int or not 0<window<2**64 or
            type(pid) is not int or not 0<pid<2**32 or
            not re.fullmatch(r'DiskEdTest-[0-9a-f]{32}',desktop)):
        raise ValueError('Owned guest control identity required')
    u=C.WinDLL('user32',use_last_error=True);g=C.WinDLL('gdi32',use_last_error=True)
    k=C.WinDLL('kernel32',use_last_error=True)
    def bind(dll,name,result,*args):
        f=getattr(dll,name);f.restype=result;f.argtypes=list(args);return f
    def checked(value):
        if not value:raise C.WinError(C.get_last_error())
        return value
    bind(k,'GetCurrentThreadId',T.DWORD)
    bind(u,'GetThreadDesktop',T.HANDLE,T.DWORD)
    bind(u,'OpenDesktopW',T.HANDLE,T.LPCWSTR,T.DWORD,T.BOOL,T.DWORD)
    bind(u,'SetThreadDesktop',T.BOOL,T.HANDLE);bind(u,'CloseDesktop',T.BOOL,T.HANDLE)
    bind(u,'SetThreadDpiAwarenessContext',T.HANDLE,T.HANDLE)
    bind(u,'GetWindowThreadProcessId',T.DWORD,T.HWND,C.POINTER(T.DWORD))
    bind(u,'GetUserObjectInformationW',T.BOOL,T.HANDLE,T.INT,T.LPVOID,T.DWORD,C.POINTER(T.DWORD))
    bind(u,'GetClassNameW',C.c_int,T.HWND,T.LPWSTR,C.c_int)
    bind(u,'GetWindowRect',T.BOOL,T.HWND,C.POINTER(T.RECT))
    bind(u,'GetClientRect',T.BOOL,T.HWND,C.POINTER(T.RECT))
    bind(u,'PrintWindow',T.BOOL,T.HWND,T.HDC,T.UINT)
    bind(g,'CreateCompatibleDC',T.HDC,T.HDC)
    bind(g,'CreateDIBSection',T.HANDLE,T.HDC,T.LPVOID,T.UINT,C.POINTER(T.LPVOID),T.HANDLE,T.DWORD)
    bind(g,'SelectObject',T.HANDLE,T.HDC,T.HANDLE)
    bind(g,'DeleteObject',T.BOOL,T.HANDLE);bind(g,'DeleteDC',T.BOOL,T.HDC)
    bind(g,'GdiFlush',T.BOOL)
    previous=u.GetThreadDesktop(k.GetCurrentThreadId())
    dpi=checked(u.SetThreadDpiAwarenessContext(T.HANDLE(-4)))
    target=checked(u.OpenDesktopW(desktop,0,False,0xf01ff))
    dc=bitmap=old=None
    try:
        checked(u.SetThreadDesktop(target))
        owner=T.DWORD();thread=checked(u.GetWindowThreadProcessId(window,C.byref(owner)))
        name=C.create_unicode_buffer(256);needed=T.DWORD()
        checked(u.GetUserObjectInformationW(u.GetThreadDesktop(thread),2,name,C.sizeof(name),C.byref(needed)))
        if owner.value!=pid or name.value!=desktop:raise ValueError('Control window binding differs')
        cls=C.create_unicode_buffer(128);checked(u.GetClassNameW(window,cls,len(cls)))
        if cls.value!='DiskEdPixelOriginControl':raise ValueError('Only the preflight control class is admitted')
        before=T.RECT();client=T.RECT()
        checked(u.GetWindowRect(window,C.byref(before)));checked(u.GetClientRect(window,C.byref(client)))
        if ((before.right-before.left,before.bottom-before.top)!=(240,96) or
                (client.left,client.top,client.right,client.bottom)!=(0,0,240,96)):
            raise ValueError('Predeclared control geometry differs')
        dc=checked(g.CreateCompatibleDC(None));bits=T.LPVOID()
        info=C.create_string_buffer(struct.pack('<IiiHHIIiiII',40,240,-96,1,32,0,92160,0,0,0,0))
        bitmap=checked(g.CreateDIBSection(dc,info,0,C.byref(bits),None,0))
        checked(bits);old=checked(g.SelectObject(dc,bitmap))
        if old==C.c_void_p(-1).value:raise C.WinError(C.get_last_error())
        C.memset(bits,0,92160)
        C.set_last_error(0);printed=bool(u.PrintWindow(window,dc,0));error=0 if printed else C.get_last_error()
        checked(g.GdiFlush());body=C.string_at(bits,92160)
        after=T.RECT();after_pid=T.DWORD()
        checked(u.GetWindowRect(window,C.byref(after)));checked(u.GetWindowThreadProcessId(window,C.byref(after_pid)))
        rect=lambda value:tuple(getattr(value,key) for key in ('left','top','right','bottom'))
        if rect(before)!=rect(after) or after_pid.value!=pid:raise ValueError('Control changed during printing')
        from target import identity
        producer=identity()
        return dict(window=window,pid=pid,desktop=desktop,width=240,height=96,method=METHOD,
                    bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),api_succeeded=printed,
                    api_error=error,display_dc_read=False,desktop_switched=False,
                    producer_identity=producer),body
    finally:
        if old not in (None,C.c_void_p(-1).value) and dc:g.SelectObject(dc,old)
        if bitmap:g.DeleteObject(bitmap)
        if dc:g.DeleteDC(dc)
        checked(u.SetThreadDesktop(previous));checked(u.CloseDesktop(target))
        checked(u.SetThreadDpiAwarenessContext(dpi))


if __name__=='__main__':
    if len(sys.argv)!=4:raise ValueError('Exact window/process/desktop arguments required')
    header,body=capture(int(sys.argv[1]),int(sys.argv[2]),sys.argv[3])
    sys.stdout.buffer.write(json.dumps(header).encode()+b'\n'+body)
