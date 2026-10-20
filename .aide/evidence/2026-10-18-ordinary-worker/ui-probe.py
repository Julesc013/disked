"""Observe owned private-desktop and console startup; no product qualification."""
import ctypes as C
from ctypes import wintypes as T
import json
from pathlib import Path
import subprocess
import sys
import os
import struct
import time

k = C.WinDLL('kernel32', use_last_error=True)
k.LoadLibraryExW.argtypes = [T.LPCWSTR, T.HANDLE, T.DWORD]
k.LoadLibraryExW.restype = T.HMODULE
k.FreeLibrary.argtypes = [T.HMODULE]
report = dict(scope=__doc__, libraries=[])
def desktop_name():
    u=C.WinDLL('user32',use_last_error=True)
    k.GetCurrentThreadId.restype=T.DWORD
    u.GetThreadDesktop.argtypes=[T.DWORD];u.GetThreadDesktop.restype=T.HANDLE
    u.GetUserObjectInformationW.argtypes=[T.HANDLE,C.c_int,T.LPVOID,T.DWORD,C.POINTER(T.DWORD)]
    text=C.create_unicode_buffer(1024);needed=T.DWORD()
    if not u.GetUserObjectInformationW(u.GetThreadDesktop(k.GetCurrentThreadId()),2,text,C.sizeof(text),C.byref(needed)):
        raise C.WinError(C.get_last_error())
    return text.value
if '--gdi-window-child' in sys.argv:
    u=C.WinDLL('user32',use_last_error=True)
    u.CreateWindowExW.argtypes=[T.DWORD,T.LPCWSTR,T.LPCWSTR,T.DWORD,C.c_int,C.c_int,C.c_int,C.c_int,T.HWND,T.HMENU,T.HINSTANCE,T.LPVOID];u.CreateWindowExW.restype=T.HWND
    u.GetMessageW.argtypes=[C.POINTER(T.MSG),T.HWND,T.UINT,T.UINT]
    u.TranslateMessage.argtypes=[C.POINTER(T.MSG)];u.DispatchMessageW.argtypes=[C.POINTER(T.MSG)];u.DispatchMessageW.restype=C.c_ssize_t
    window=u.CreateWindowExW(0,'STATIC','Owned print probe',0x90000000,0,0,240,96,None,None,None,None)
    if not window:raise C.WinError(C.get_last_error())
    button=u.CreateWindowExW(0,'BUTTON','Owned caption',0x50000000,10,30,160,35,window,None,None,None)
    if not button:raise C.WinError(C.get_last_error())
    # Trace the actual print-message boundary in this controlled window only.
    # Its diagnostic sentinel cannot satisfy a product screenshot assertion.
    g=C.WinDLL('gdi32',use_last_error=True)
    g.GetObjectType.argtypes=[T.HANDLE];g.GetObjectType.restype=T.DWORD
    g.GetClipBox.argtypes=[T.HDC,C.POINTER(T.RECT)];g.GetClipBox.restype=C.c_int
    g.SetPixelV.argtypes=[T.HDC,C.c_int,C.c_int,T.DWORD];g.SetPixelV.restype=T.BOOL
    g.GdiFlush.restype=T.BOOL
    callback=C.WINFUNCTYPE(C.c_ssize_t,T.HWND,T.UINT,T.WPARAM,T.LPARAM)
    u.SetWindowLongPtrW.argtypes=[T.HWND,C.c_int,C.c_void_p];u.SetWindowLongPtrW.restype=C.c_void_p
    u.CallWindowProcW.argtypes=[C.c_void_p,T.HWND,T.UINT,T.WPARAM,T.LPARAM];u.CallWindowProcW.restype=C.c_ssize_t
    trace=Path(os.environ['TEMP'])/('gdi-print-'+str(os.getpid())+'.json');events=[]
    @callback
    def observe(hwnd,kind,wparam,lparam):
        result=u.CallWindowProcW(original,hwnd,kind,wparam,lparam)
        if kind in (0x317,0x318):
            bounds=T.RECT();clip=g.GetClipBox(wparam,C.byref(bounds))
            events.append(dict(message=kind,flags=int(lparam),dc_type=g.GetObjectType(wparam),clip_type=clip,
                clip=[bounds.left,bounds.top,bounds.right,bounds.bottom],sentinel=bool(g.SetPixelV(wparam,1,1,0x00332211)),flushed=bool(g.GdiFlush())))
            trace.write_text(json.dumps(events[-8:]),encoding='utf-8')
        return result
    original=u.SetWindowLongPtrW(window,-4,C.cast(observe,C.c_void_p))
    if not original:raise C.WinError(C.get_last_error())
    print(json.dumps(dict(window=window,pid=os.getpid(),desktop=desktop_name())),flush=True)
    message=T.MSG()
    while u.GetMessageW(C.byref(message),None,0,0)>0:
        u.TranslateMessage(C.byref(message));u.DispatchMessageW(C.byref(message))
    sys.exit(0)
if '--station-limits' in sys.argv and '--console-child' not in sys.argv:
    # Isolate the application's named-object bootstrap refusal without another
    # product build or a namespace ACL change. Handles are owned and short lived.
    import target
    sid=target.identity()['user_sid']
    a=C.WinDLL('advapi32',use_last_error=True)
    a.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes=[T.LPCWSTR,T.DWORD,C.POINTER(T.LPVOID),T.LPVOID]
    a.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype=T.BOOL
    k.LocalFree.argtypes=[T.LPVOID];k.LocalFree.restype=T.LPVOID
    class Attributes(C.Structure):_fields_=[('length',T.DWORD),('descriptor',T.LPVOID),('inherit',T.BOOL)]
    descriptor=T.LPVOID()
    if not a.ConvertStringSecurityDescriptorToSecurityDescriptorW('D:P(A;;GA;;;'+sid+')',1,C.byref(descriptor),None):raise C.WinError(C.get_last_error())
    attributes=Attributes(C.sizeof(Attributes),descriptor,False)
    k.CloseHandle.argtypes=[T.HANDLE];k.CloseHandle.restype=T.BOOL
    k.CreateMutexW.argtypes=[C.POINTER(Attributes),T.BOOL,T.LPCWSTR];k.CreateMutexW.restype=T.HANDLE
    k.CreateJobObjectW.argtypes=[C.POINTER(Attributes),T.LPCWSTR];k.CreateJobObjectW.restype=T.HANDLE
    native=C.WinDLL('ntdll',use_last_error=True)
    native.NtQueryObject.argtypes=[T.HANDLE,C.c_int,T.LPVOID,T.DWORD,C.POINTER(T.DWORD)];native.NtQueryObject.restype=T.LONG
    class ObjectName(C.Structure):_fields_=[('length',T.USHORT),('maximum',T.USHORT),('text',T.LPVOID)]
    report['owned_kernel_object_startup']=[]
    try:
        for kind in ('mutex','job'):
            for named in (False,True):
                name=('DiskEd.Owned.Startup.'+sid+'.'+str(os.getpid())+'.'+kind) if named else None
                C.set_last_error(0)
                opened=k.CreateMutexW(C.byref(attributes),False,name) if kind=='mutex' else k.CreateJobObjectW(C.byref(attributes),name)
                error=C.get_last_error()
                row=dict(kind=kind,named=named,created=bool(opened),error=0 if opened else error)
                report['owned_kernel_object_startup'].append(row)
                if opened and named:
                    size=T.DWORD();native.NtQueryObject(opened,1,None,0,C.byref(size))
                    if not 0<size.value<=4096:raise ValueError('Owned object name bound')
                    buffer=C.create_string_buffer(size.value);status=native.NtQueryObject(opened,1,buffer,size,C.byref(size));row['name_status']=hex(status&0xffffffff)
                    if status==0:
                        value=ObjectName.from_buffer(buffer)
                        if value.length%2 or not value.text or not C.addressof(buffer)<=value.text<=value.text+value.length<=C.addressof(buffer)+size.value:raise ValueError('Owned object name range')
                        row['object_path']=C.wstring_at(value.text,value.length//2)
                if opened and not k.CloseHandle(opened):raise C.WinError(C.get_last_error())
    finally:k.LocalFree(descriptor)
    # Read access checks only: requesting CREATE_OBJECT on an open directory
    # does not create an object or change its security descriptor.
    class Unicode(C.Structure):_fields_=[('length',T.USHORT),('maximum',T.USHORT),('text',T.LPWSTR)]
    class ObjectAttributes(C.Structure):_fields_=[('length',T.ULONG),('root',T.HANDLE),('name',C.POINTER(Unicode)),('flags',T.ULONG),('security',T.LPVOID),('quality',T.LPVOID)]
    n=C.WinDLL('ntdll',use_last_error=True)
    n.NtOpenDirectoryObject.argtypes=[C.POINTER(T.HANDLE),T.DWORD,C.POINTER(ObjectAttributes)];n.NtOpenDirectoryObject.restype=T.LONG
    n.NtQuerySecurityObject.argtypes=[T.HANDLE,T.DWORD,T.LPVOID,T.DWORD,C.POINTER(T.DWORD)];n.NtQuerySecurityObject.restype=T.LONG
    a.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes=[T.LPVOID,T.DWORD,T.DWORD,C.POINTER(T.LPWSTR),T.LPVOID]
    a.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype=T.BOOL
    report['namespace_access']=[]
    for name in ('\\BaseNamedObjects','\\BaseNamedObjects\\Restricted','\\Sessions\\3\\BaseNamedObjects','\\Sessions\\3\\BaseNamedObjects\\Restricted'):
        text=C.create_unicode_buffer(name);value=Unicode(len(name)*2,C.sizeof(text),C.cast(text,T.LPWSTR))
        attrs=ObjectAttributes(C.sizeof(ObjectAttributes),None,C.pointer(value),0x40,None,None)
        for mask in (3,7,15,0x20003,0x10003,0x40003,0x80003):
            handle=T.HANDLE();status=n.NtOpenDirectoryObject(C.byref(handle),mask,C.byref(attrs))
            row=dict(path=name,access=mask,status=hex(status&0xffffffff));report['namespace_access'].append(row)
            try:
                if status==0 and mask&0x20000:
                    size=T.DWORD();n.NtQuerySecurityObject(handle,4,None,0,C.byref(size))
                    if not 0<size.value<=32768:raise ValueError('Namespace descriptor bound')
                    buffer=C.create_string_buffer(size.value);query=n.NtQuerySecurityObject(handle,4,buffer,size,C.byref(size));row['query_status']=hex(query&0xffffffff)
                    if query==0:
                        output=T.LPWSTR()
                        if not a.ConvertSecurityDescriptorToStringSecurityDescriptorW(buffer,1,4,C.byref(output),None):raise C.WinError(C.get_last_error())
                        try:row['dacl']=output.value
                        finally:k.LocalFree(C.cast(output,T.LPVOID))
            finally:
                if handle and not k.CloseHandle(handle):raise C.WinError(C.get_last_error())
if '--object-child' in sys.argv:
    print(json.dumps(report));sys.exit(0)
for name in ('user32.dll', 'gdi32.dll'):
    C.set_last_error(0)
    handle = k.LoadLibraryExW(name, None, 0x800)
    error = C.get_last_error()
    row = dict(name=name, loaded=bool(handle), error=0 if handle else error)
    try:
        if handle and name == 'user32.dll':
            u = C.WinDLL(name, handle=handle, use_last_error=True)
            u.GetProcessWindowStation.restype = T.HANDLE
            u.GetUserObjectInformationW.argtypes = [T.HANDLE, C.c_int, T.LPVOID, T.DWORD, C.POINTER(T.DWORD)]
            text, needed = C.create_unicode_buffer(1024), T.DWORD()
            ok = u.GetUserObjectInformationW(u.GetProcessWindowStation(), 2, text, C.sizeof(text), C.byref(needed))
            row['station'] = text.value if ok else None
            row['station_error'] = 0 if ok else C.get_last_error()
            u.CreateWindowExW.argtypes = [T.DWORD, T.LPCWSTR, T.LPCWSTR, T.DWORD,
                                         C.c_int, C.c_int, C.c_int, C.c_int,
                                         T.HWND, T.HMENU, T.HINSTANCE, T.LPVOID]
            u.CreateWindowExW.restype = T.HWND
            u.DestroyWindow.argtypes = [T.HWND]
            C.set_last_error(0)
            window = u.CreateWindowExW(0, 'STATIC', 'DiskEd owned probe', 0, 0, 0, 8, 8, None, None, None, None)
            row['window_created'] = bool(window)
            row['window_error'] = 0 if window else C.get_last_error()
            if window and not u.DestroyWindow(window):
                raise C.WinError(C.get_last_error())
            if '--station-limits' in sys.argv:
                if row['station']!='WinSta0':raise ValueError('Exact interactive station required')
                u.OpenWindowStationW.argtypes=[T.LPCWSTR,T.BOOL,T.DWORD];u.OpenWindowStationW.restype=T.HANDLE
                u.CloseWindowStation.argtypes=[T.HANDLE]
                row['station_access']=[]
                for label,mask in [('read_attributes',2),('delete',0x10000),('write_dacl',0x40000),
                                   ('write_owner',0x80000),('clipboard',4),('write_attributes',0x10),
                                   ('exit_windows',0x40),('read_screen',0x200)]:
                    C.set_last_error(0);opened=u.OpenWindowStationW('WinSta0',False,mask);error=C.get_last_error()
                    row['station_access'].append(dict(right=label,mask=mask,opened=bool(opened),error=0 if opened else error))
                    if opened and not u.CloseWindowStation(opened):raise C.WinError(C.get_last_error())
                u.OpenDesktopW.argtypes=[T.LPCWSTR,T.DWORD,T.BOOL,T.DWORD];u.OpenDesktopW.restype=T.HANDLE
                u.CloseDesktop.argtypes=[T.HANDLE]
                row['default_desktop_access']=[]
                for label,mask in [('read_objects',1),('hook_control',8),('write_objects',0x80),('switch_desktop',0x100)]:
                    C.set_last_error(0);opened=u.OpenDesktopW('Default',0,False,mask);error=C.get_last_error()
                    row['default_desktop_access'].append(dict(right=label,mask=mask,opened=bool(opened),error=0 if opened else error))
                    if opened and not u.CloseDesktop(opened):raise C.WinError(C.get_last_error())
        if handle and name=='gdi32.dll' and '--console-child' not in sys.argv:
            g=C.WinDLL(name,handle=handle,use_last_error=True);u=C.WinDLL('user32',use_last_error=True)
            g.CreateCompatibleDC.argtypes=[T.HDC];g.CreateCompatibleDC.restype=T.HDC
            g.CreateDIBSection.argtypes=[T.HDC,T.LPVOID,T.UINT,C.POINTER(T.LPVOID),T.HANDLE,T.DWORD];g.CreateDIBSection.restype=T.LPVOID
            g.SelectObject.argtypes=[T.HDC,T.LPVOID];g.SelectObject.restype=T.LPVOID
            g.DeleteObject.argtypes=[T.LPVOID];g.DeleteDC.argtypes=[T.HDC]
            g.SetPixelV.argtypes=[T.HDC,C.c_int,C.c_int,T.DWORD];g.GdiFlush.restype=T.BOOL
            u.CreateWindowExW.argtypes=[T.DWORD,T.LPCWSTR,T.LPCWSTR,T.DWORD,C.c_int,C.c_int,C.c_int,C.c_int,T.HWND,T.HMENU,T.HINSTANCE,T.LPVOID];u.CreateWindowExW.restype=T.HWND
            u.GetDC.argtypes=[T.HWND];u.GetDC.restype=T.HDC
            u.ReleaseDC.argtypes=[T.HWND,T.HDC];u.DestroyWindow.argtypes=[T.HWND]
            window=u.CreateWindowExW(0,'STATIC','Owned GDI format probe',0,0,0,8,8,None,None,None,None)
            reference=u.GetDC(window) if window else None;row['memory_drawing']=[]
            try:
                for label,source in [('default',None),('owned_window',reference)]:
                    if label=='owned_window' and not reference:
                        row['memory_drawing'].append(dict(reference=label,reference_available=False));continue
                    C.set_last_error(0);dc=g.CreateCompatibleDC(source);dc_error=C.get_last_error();bitmap=None;old=None;bits=T.LPVOID()
                    observed=dict(reference=label,dc_created=bool(dc),dc_error=0 if dc else dc_error)
                    try:
                        if dc:
                            info=C.create_string_buffer(struct.pack('<IiiHHIIiiII',40,4,-4,1,32,0,64,0,0,0,0))
                            C.set_last_error(0);bitmap=g.CreateDIBSection(dc,info,0,C.byref(bits),None,0)
                            observed.update(bitmap_created=bool(bitmap),bits_available=bool(bits),bitmap_error=0 if bitmap else C.get_last_error())
                            if bitmap and bits:
                                C.set_last_error(0);old=g.SelectObject(dc,bitmap)
                                selected=old not in (None,C.c_void_p(-1).value)
                                observed.update(selected=selected,selection_error=0 if selected else C.get_last_error())
                                if selected:
                                    C.memset(bits,0,64);observed['set_pixel']=bool(g.SetPixelV(dc,0,0,0x00332211));observed['flushed']=bool(g.GdiFlush())
                                    observed['bgr']=C.string_at(bits,3).hex();observed['expected_bgr']='332211'
                    finally:
                        if old not in (None,C.c_void_p(-1).value):g.SelectObject(dc,old)
                        if bitmap:g.DeleteObject(bitmap)
                        if dc:g.DeleteDC(dc)
                    row['memory_drawing'].append(observed)
                u.PrintWindow.argtypes=[T.HWND,T.HDC,T.UINT];u.PrintWindow.restype=T.BOOL
                u.SendMessageTimeoutW.argtypes=[T.HWND,T.UINT,C.c_size_t,C.c_ssize_t,T.UINT,T.UINT,C.POINTER(C.c_size_t)];u.SendMessageTimeoutW.restype=C.c_ssize_t
                u.RedrawWindow.argtypes=[T.HWND,T.LPVOID,T.HANDLE,T.UINT]
                def printing(hwnd,owner):
                    dc=g.CreateCompatibleDC(None);bits=T.LPVOID();bitmap=None;old=None
                    if not dc:raise C.WinError(C.get_last_error())
                    try:
                        info=C.create_string_buffer(struct.pack('<IiiHHIIiiII',40,240,-96,1,32,0,240*96*4,0,0,0,0))
                        bitmap=g.CreateDIBSection(dc,info,0,C.byref(bits),None,0)
                        if not bitmap or not bits:raise C.WinError(C.get_last_error())
                        old=g.SelectObject(dc,bitmap)
                        if old in (None,C.c_void_p(-1).value):raise C.WinError(C.get_last_error())
                        rows=[]
                        for method in ('PrintWindow0','PrintWindow2','WM_PRINT'):
                            C.memset(bits,0,240*96*4);u.RedrawWindow(hwnd,None,None,0x585);C.set_last_error(0)
                            if method=='WM_PRINT':
                                answer=C.c_size_t();ok=u.SendMessageTimeoutW(hwnd,0x317,dc,0x1e,2,1000,C.byref(answer))
                            else:ok=u.PrintWindow(hwnd,dc,0 if method=='PrintWindow0' else 2)
                            code=0 if ok else C.get_last_error();g.GdiFlush();body=C.string_at(bits,240*96*4)
                            colors=set(struct.iter_unpack('<I',body));rgb={p[0]&0xffffff for p in colors}
                            rows.append(dict(owner=owner,method=method,call_succeeded=bool(ok),error=code,
                                rgb_colors=len(rgb),varied=len(rgb)>1,first_bgr=body[:3].hex()))
                        return rows
                    finally:
                        if old not in (None,C.c_void_p(-1).value):g.SelectObject(dc,old)
                        if bitmap:g.DeleteObject(bitmap)
                        g.DeleteDC(dc)
                own=u.CreateWindowExW(0,'STATIC','Owned print probe',0x90000000,0,0,240,96,None,None,None,None)
                if not own:raise C.WinError(C.get_last_error())
                try:
                    button=u.CreateWindowExW(0,'BUTTON','Owned caption',0x50000000,10,30,160,35,own,None,None,None)
                    if not button:raise C.WinError(C.get_last_error())
                    row['printing']=printing(own,'same_process')
                finally:u.DestroyWindow(own)
                child=subprocess.Popen([sys.executable,'-B',__file__,'--gdi-window-child'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                try:
                    line=child.stdout.readline(4097)
                    warning=('Failed to find real location of '+sys.executable).encode()
                    if line.strip()==warning:line=child.stdout.readline(4097)
                    owned=json.loads(line);assert owned['pid']==child.pid and child.poll() is None
                    assert owned['desktop']==desktop_name();row['printing_desktop']=owned['desktop']
                    row['printing']+=printing(owned['window'],'owned_child')
                    endpoint=os.environ.get('DISKED_OWNED_PRINT_PROBE')
                    if endpoint:
                        request=Path(endpoint+'.json');response=Path(endpoint+'-response.json')
                        if request.parent.resolve()!=Path(os.environ['TEMP']).resolve():raise ValueError('Owned temp endpoint required')
                        with request.open('x',encoding='utf-8') as stream:json.dump(owned,stream)
                        Path(endpoint+'.ready').touch(exist_ok=False)
                        until=time.monotonic()+12
                        while not Path(endpoint+'-response.ready').exists():
                            if time.monotonic()>until:raise TimeoutError('Owned coordinator print control')
                            time.sleep(.05)
                        if response.stat().st_size>4096:raise ValueError('Print control response bound')
                        row['coordinator_printing']=json.loads(response.read_bytes())
                    trace=Path(os.environ['TEMP'])/('gdi-print-'+str(child.pid)+'.json')
                    row['owned_print_messages']=json.loads(trace.read_bytes()) if trace.exists() else []
                finally:
                    if child.poll() is None:child.terminate()
                    child.wait(timeout=5);child.stdout.close();child.stderr.close()
            finally:
                if reference:u.ReleaseDC(window,reference)
                if window:u.DestroyWindow(window)
    finally:
        if handle:
            k.FreeLibrary(handle)
    report['libraries'].append(row)

if '--printing-only' in sys.argv:
    print(json.dumps(report))
    sys.exit(0)
if '--console-child' in sys.argv:
    k.CreateFileW.argtypes = [T.LPCWSTR, T.DWORD, T.DWORD, T.LPVOID, T.DWORD, T.DWORD, T.HANDLE]
    k.CreateFileW.restype = T.HANDLE
    k.CloseHandle.argtypes = [T.HANDLE]
    k.GetConsoleMode.argtypes = [T.HANDLE, C.POINTER(T.DWORD)]
    handle = k.CreateFileW('CONOUT$', 0xc0000000, 3, None, 3, 0, None)
    error = C.get_last_error()
    report['console_opened'] = handle != C.c_void_p(-1).value
    report['console_error'] = 0 if report['console_opened'] else error
    if report['console_opened']:
        try:
            mode = T.DWORD()
            ok = k.GetConsoleMode(handle, C.byref(mode))
            report['console_mode'] = mode.value if ok else None
            report['console_mode_error'] = 0 if ok else C.get_last_error()
            if '--basic' not in sys.argv:
                sys.path.insert(0, str(Path(__file__).parent / 'source/tests/frontend'))
                import console_tui_fixture as fixture
                value = fixture.info(handle)
                report['console_geometry'] = dict(buffer=[value.size.X,value.size.Y],
                    viewport=[value.window.Left,value.window.Top,value.window.Right,value.window.Bottom])
                largest = fixture.api('GetLargestConsoleWindowSize',[T.HANDLE],fixture.Coord)(handle)
                report['largest_viewport'] = [largest.X,largest.Y]
                steps=[]
                for name in ('SetConsoleWindowInfo','SetConsoleScreenBufferSize'):
                    original=getattr(fixture.k,name)
                    def observe(*args,_name=name,_original=original):
                        result=_original(*args);error=C.get_last_error()
                        steps.append(dict(api=_name,success=bool(result),error=0 if result else error))
                        return result
                    setattr(fixture.k,name,observe)
                try:
                    fixture.configure(handle,240,25)
                    report['configure_passed']=True
                except OSError as error:
                    report['configure_passed']=False
                    report['configure_error']=error.winerror
                report['configure_steps']=steps
                value=fixture.info(handle)
                report['configured_geometry']=dict(buffer=[value.size.X,value.size.Y],
                    viewport=[value.window.Left,value.window.Top,value.window.Right,value.window.Bottom])
        finally:
            k.CloseHandle(handle)
else:
    child = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '--console-child',
                            *[flag for flag in ('--basic','--station-limits') if flag in sys.argv]],
                           capture_output=True, creationflags=subprocess.CREATE_NEW_CONSOLE, timeout=15)
    report['console_child'] = dict(exit_code=child.returncode,
                                   stdout=child.stdout.decode(errors='replace')[-8192:],
                                   stderr=child.stderr.decode(errors='replace')[-4096:])
print(json.dumps(report))
