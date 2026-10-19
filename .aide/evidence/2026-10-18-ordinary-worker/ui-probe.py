"""Observe owned private-desktop and console startup; no product qualification."""
import ctypes as C
from ctypes import wintypes as T
import json
from pathlib import Path
import subprocess
import sys

k = C.WinDLL('kernel32', use_last_error=True)
k.LoadLibraryExW.argtypes = [T.LPCWSTR, T.HANDLE, T.DWORD]
k.LoadLibraryExW.restype = T.HMODULE
k.FreeLibrary.argtypes = [T.HMODULE]
report = dict(scope=__doc__, libraries=[])
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
    finally:
        if handle:
            k.FreeLibrary(handle)
    report['libraries'].append(row)

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
