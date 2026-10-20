"""Print only the independently specified owned popup; never read a display DC."""
import ctypes as C
from ctypes import wintypes as T
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import struct
import sys

METHOD='owned-ui-thread-control/1'


def capture(window,pid,desktop):
    if (socket.gethostname().casefold()!='blackglass-hyperv' or
            type(window) is not int or not 0<window<2**64 or
            type(pid) is not int or not 0<pid<2**32 or
            not re.fullmatch(r'DiskEdTest-[0-9a-f]{32}',desktop)):
        raise ValueError('Owned guest control identity required')
    u=C.WinDLL('user32',use_last_error=True)
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
    bind(u,'SendMessageTimeoutW',C.c_ssize_t,T.HWND,T.UINT,C.c_size_t,C.c_ssize_t,
         T.UINT,T.UINT,C.POINTER(C.c_size_t))
    bind(k,'CreateFileMappingW',T.HANDLE,T.HANDLE,T.LPVOID,T.DWORD,T.DWORD,T.DWORD,T.LPCWSTR)
    bind(k,'MapViewOfFile',T.LPVOID,T.HANDLE,T.DWORD,T.DWORD,T.DWORD,C.c_size_t)
    bind(k,'UnmapViewOfFile',T.BOOL,T.LPVOID);bind(k,'CloseHandle',T.BOOL,T.HANDLE)
    bind(k,'GetCurrentProcess',T.HANDLE)
    bind(k,'OpenProcess',T.HANDLE,T.DWORD,T.BOOL,T.DWORD)
    bind(k,'DuplicateHandle',T.BOOL,T.HANDLE,T.HANDLE,T.HANDLE,C.POINTER(T.HANDLE),T.DWORD,T.BOOL,T.DWORD)
    bind(u,'RegisterWindowMessageW',T.UINT,T.LPCWSTR)
    bind(u,'SetWindowsHookExW',T.HANDLE,C.c_int,T.LPVOID,T.HANDLE,T.DWORD)
    bind(u,'UnhookWindowsHookEx',T.BOOL,T.HANDLE)
    bind(u,'GetPropW',T.HANDLE,T.HWND,T.LPCWSTR)
    previous=u.GetThreadDesktop(k.GetCurrentThreadId())
    dpi=checked(u.SetThreadDpiAwarenessContext(T.HANDLE(-4)))
    target=checked(u.OpenDesktopW(desktop,0,False,0xf01ff))
    section=view=hook=process=None;module=None
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
        dll=Path(os.environ['DISKED_PIXEL_RENDER_DLL'])
        if not dll.is_absolute() or dll.name!='pixel-render.dll':raise ValueError('Exact fixture DLL required')
        digest=hashlib.sha256(dll.read_bytes()).hexdigest()
        if digest!=os.environ['DISKED_PIXEL_RENDER_SHA256']:raise ValueError('Fixture DLL identity differs')
        # The coordinator pins this code read-only until target job retirement.
        module=C.WinDLL(str(dll),winmode=0x1100,use_last_error=True)
        first=int.from_bytes(os.urandom(8),'little');second=0
        C.set_last_error(0)
        section=checked(k.CreateFileMappingW(T.HANDLE(-1),None,4,0,96+92160,None))
        view=checked(k.MapViewOfFile(section,6,0,0,96+92160))
        C.memset(view,0,96+92160)
        frame=struct.Struct('<IIQIIIIQQIIII32x')
        prefix=frame.pack(0x50454444,1,window,pid,240,96,92160,first,second,0,0,0,0)
        C.memmove(view,prefix,96)
        process=checked(k.OpenProcess(0x40,False,pid)) # only this validated owned target
        remote=T.HANDLE()
        checked(k.DuplicateHandle(k.GetCurrentProcess(),section,process,C.byref(remote),6,False,0))
        request=checked(u.RegisterWindowMessageW('DiskEd.OwnedPixelFixture/1'))
        # Nonzero,previously validated exact owned UI thread. Never global.
        hook=checked(u.SetWindowsHookExW(4,C.cast(module.OwnedPixelHook,T.LPVOID),module._handle,thread))
        answer=C.c_size_t();C.set_last_error(0)
        printed=bool(u.SendMessageTimeoutW(window,request,remote.value,C.c_ssize_t(first).value,2,3000,C.byref(answer)))
        error=0 if printed else C.get_last_error()
        # Even a timeout goes through finally and owned job retirement. Never
        # infer callback quiescence merely from UnhookWindowsHookEx success.
        observed=frame.unpack(C.string_at(view,96))
        if observed[:9]!=frame.unpack(prefix)[:9]:raise ValueError('Render header identity changed')
        status,render_error,renderer_pid,renderer_thread=observed[9:]
        if not printed or status!=2 or render_error or (renderer_pid,renderer_thread)!=(pid,thread):
            load_message=checked(u.RegisterWindowMessageW('DiskEd.OwnedPixelFixture.LoadDiagnostic/1'))
            direct=bool(u.SendMessageTimeoutW(window,load_message,0,0,2,3000,C.byref(answer)))
            diagnostic={key:u.GetPropW(window,'DiskEd.PixelFixture.'+key) for key in
                        ('HookMessage','Request','Stage','MapError','ModuleLoaded','DirectLoad')}
            diagnostic.update(request=request,printed=printed,error=error,status=status,
                              render_error=render_error,renderer_pid=renderer_pid,renderer_thread=renderer_thread,
                              direct_diagnostic_delivered=direct)
            raise RuntimeError('Owned UI-thread render failed: '+repr(diagnostic))
        body=C.string_at(view+96,92160)
        after=T.RECT();after_pid=T.DWORD()
        checked(u.GetWindowRect(window,C.byref(after)));checked(u.GetWindowThreadProcessId(window,C.byref(after_pid)))
        rect=lambda value:tuple(getattr(value,key) for key in ('left','top','right','bottom'))
        if rect(before)!=rect(after) or after_pid.value!=pid:raise ValueError('Control changed during printing')
        from target import identity
        producer=identity()
        return dict(window=window,pid=pid,desktop=desktop,width=240,height=96,method=METHOD,
                    bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),api_succeeded=printed,
                    api_error=error,api_name='Owned UI-thread memory-DIB/WM_PRINT',
                    renderer_pid=renderer_pid,renderer_thread=renderer_thread,
                    fixture_dll_sha256=digest,fixture_hook_scope='exact-owned-ui-thread',
                    display_dc_read=False,desktop_switched=False,
                    producer_identity=producer),body
    finally:
        if hook:checked(u.UnhookWindowsHookEx(hook))
        if view:checked(k.UnmapViewOfFile(view))
        if section:checked(k.CloseHandle(section))
        if process:checked(k.CloseHandle(process))
        checked(u.SetThreadDesktop(previous));checked(u.CloseDesktop(target))
        checked(u.SetThreadDpiAwarenessContext(dpi))


if __name__=='__main__':
    if len(sys.argv)!=4:raise ValueError('Exact window/process/desktop arguments required')
    header,body=capture(int(sys.argv[1]),int(sys.argv[2]),sys.argv[3])
    sys.stdout.buffer.write(json.dumps(header).encode()+b'\n'+body)
