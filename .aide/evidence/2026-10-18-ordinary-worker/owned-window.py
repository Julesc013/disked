"""Guest coordinator control: print one verified job-owned hidden-desktop window.

The caller pins the process and verifies membership in its live job. This helper
rechecks the window/process/desktop binding. No screen DC or foreground input.
"""
import ctypes as C
from ctypes import wintypes as T
import json
import re
import socket
import struct
import sys


def capture(window, pid, desktop):
    if (socket.gethostname().casefold() != 'blackglass-hyperv' or
            not re.fullmatch(r'Proof-[0-9a-f]{32}', desktop) or
            type(window) is not int or not 0 < window < 2**64 or
            type(pid) is not int or not 0 < pid < 2**32):
        raise ValueError('Owned guest window identity required')
    u=C.WinDLL('user32',use_last_error=True)
    g=C.WinDLL('gdi32',use_last_error=True)
    k=C.WinDLL('kernel32',use_last_error=True)
    k.GetCurrentThreadId.restype=T.DWORD
    def bind(dll,name,result,*args):
        fn=getattr(dll,name);fn.restype=result;fn.argtypes=list(args);return fn
    bind(u,'OpenDesktopW',T.HANDLE,T.LPCWSTR,T.DWORD,T.BOOL,T.DWORD)
    bind(u,'CloseDesktop',T.BOOL,T.HANDLE)
    bind(u,'SetThreadDesktop',T.BOOL,T.HANDLE)
    bind(u,'GetWindowThreadProcessId',T.DWORD,T.HWND,C.POINTER(T.DWORD))
    bind(u,'GetThreadDesktop',T.HANDLE,T.DWORD)
    bind(u,'GetUserObjectInformationW',T.BOOL,T.HANDLE,C.c_int,T.LPVOID,T.DWORD,C.POINTER(T.DWORD))
    bind(u,'GetWindowRect',T.BOOL,T.HWND,C.POINTER(T.RECT))
    bind(u,'PrintWindow',T.BOOL,T.HWND,T.HDC,T.UINT)
    bind(u,'RedrawWindow',T.BOOL,T.HWND,T.LPVOID,T.HANDLE,T.UINT)
    bind(g,'CreateCompatibleDC',T.HDC,T.HDC)
    bind(g,'CreateDIBSection',T.HBITMAP,T.HDC,T.LPVOID,T.UINT,C.POINTER(T.LPVOID),T.HANDLE,T.DWORD)
    bind(g,'SelectObject',T.HANDLE,T.HDC,T.HANDLE)
    bind(g,'DeleteObject',T.BOOL,T.HANDLE)
    bind(g,'DeleteDC',T.BOOL,T.HDC)
    bind(g,'GdiFlush',T.BOOL)
    previous=u.GetThreadDesktop(k.GetCurrentThreadId())
    target=u.OpenDesktopW(desktop,0,False,0xf01ff)
    if not target:raise C.WinError(C.get_last_error())
    dc=bitmap=old=None
    try:
        if not u.SetThreadDesktop(target):raise C.WinError(C.get_last_error())
        owner=T.DWORD();thread=u.GetWindowThreadProcessId(window,C.byref(owner))
        if not thread or owner.value!=pid:raise ValueError('Window process differs')
        name=C.create_unicode_buffer(256);needed=T.DWORD()
        if not u.GetUserObjectInformationW(u.GetThreadDesktop(thread),2,name,C.sizeof(name),C.byref(needed)):
            raise C.WinError(C.get_last_error())
        if name.value!=desktop:raise ValueError('Window desktop differs')
        bounds=T.RECT()
        if not u.GetWindowRect(window,C.byref(bounds)):raise C.WinError(C.get_last_error())
        width,height=bounds.right-bounds.left,bounds.bottom-bounds.top
        if not 0<width<=4096 or not 0<height<=4096 or width*height>4194304:
            raise ValueError('Window capture dimensions exceed bound')
        header=C.create_string_buffer(struct.pack('<IiiHHIIiiII',40,width,-height,1,32,0,width*height*4,0,0,0,0))
        bits=T.LPVOID();dc=g.CreateCompatibleDC(None)
        if not dc:raise C.WinError(C.get_last_error())
        bitmap=g.CreateDIBSection(dc,header,0,C.byref(bits),None,0)
        if not bitmap or not bits:raise C.WinError(C.get_last_error())
        old=g.SelectObject(dc,bitmap)
        if old in (None,C.c_void_p(-1).value):raise C.WinError(C.get_last_error())
        if not u.RedrawWindow(window,None,None,0x585):raise C.WinError(C.get_last_error())
        printed=u.PrintWindow(window,dc,0)
        g.GdiFlush();body=C.string_at(bits,width*height*4)
        rgb={value[0]&0xffffff for value in struct.iter_unpack('<I',body)}
        return dict(window=window,pid=pid,desktop=desktop,width=width,height=height,
                    printed=bool(printed),rgb_colors=len(rgb),varied=len(rgb)>1,first_bgr=body[:3].hex())
    finally:
        if old not in (None,C.c_void_p(-1).value):g.SelectObject(dc,old)
        if bitmap:g.DeleteObject(bitmap)
        if dc:g.DeleteDC(dc)
        if not u.SetThreadDesktop(previous):raise C.WinError(C.get_last_error())
        u.CloseDesktop(target)


if __name__=='__main__':
    if len(sys.argv)!=4:raise ValueError('Exact window/process/desktop arguments required')
    print(json.dumps(capture(int(sys.argv[1]),int(sys.argv[2]),sys.argv[3])))
