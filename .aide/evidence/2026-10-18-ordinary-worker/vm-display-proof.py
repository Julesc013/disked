"""One host presentation control; DiskEd/native execution remains in the guest."""
import ctypes as C
from ctypes import wintypes as T
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
if socket.gethostname().casefold()!='blackglass-win10':raise ValueError('Expected observed coordinator DNS name')
u=C.WinDLL('user32',use_last_error=True)
k=C.WinDLL('kernel32',use_last_error=True)
u.IsWindow.argtypes=[T.HWND];u.IsIconic.argtypes=[T.HWND]
u.GetForegroundWindow.restype=T.HWND
u.GetWindowThreadProcessId.argtypes=[T.HWND,C.POINTER(T.DWORD)]
u.ShowWindowAsync.argtypes=[T.HWND,C.c_int]
k.OpenProcess.argtypes=[T.DWORD,T.BOOL,T.DWORD];k.OpenProcess.restype=T.HANDLE
k.QueryFullProcessImageNameW.argtypes=[T.HANDLE,T.DWORD,T.LPWSTR,C.POINTER(T.DWORD)]
k.CloseHandle.argtypes=[T.HANDLE]
window=166791120;expected_pid=44228
pid=T.DWORD();u.GetWindowThreadProcessId(window,C.byref(pid))
if not u.IsWindow(window) or pid.value!=expected_pid:raise ValueError('Observed VMConnect instance changed')
process=k.OpenProcess(0x1000,False,pid.value)
if not process:raise C.WinError(C.get_last_error())
try:
    image=C.create_unicode_buffer(1024);size=T.DWORD(len(image))
    if not k.QueryFullProcessImageNameW(process,0,image,C.byref(size)):raise C.WinError(C.get_last_error())
    if Path(image.value)!=Path('C:/Windows/System32/vmconnect.exe'):raise ValueError('Unexpected VM presentation executable')
    before=bool(u.IsIconic(window));foreground=u.GetForegroundWindow()
    result=dict(script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),window=window,pid=pid.value,
        image=image.value,initially_minimized=before,host_product_execution=False)
    try:
        if not before:raise ValueError('This fixed control expects the observed minimized VM window')
        if not u.ShowWindowAsync(window,4):raise C.WinError(C.get_last_error()) # SW_SHOWNOACTIVATE
        until=time.monotonic()+3
        while u.IsIconic(window) and time.monotonic()<until:time.sleep(.05)
        if u.IsIconic(window) or u.GetForegroundWindow()==window:raise RuntimeError('Restore without activation failed')
        result['restored_without_activation']=True
        outcome=subprocess.run([sys.executable,'-B',str(HERE/'campaign.py'),'--ui-proof','--interactive-ui'],timeout=600)
        result['campaign_exit_code']=outcome.returncode
    finally:
        if u.IsWindow(window) and u.GetForegroundWindow()!=window:
            if not u.ShowWindowAsync(window,7):raise C.WinError(C.get_last_error()) # SW_SHOWMINNOACTIVE
            until=time.monotonic()+3
            while not u.IsIconic(window) and time.monotonic()<until:time.sleep(.05)
        result['initial_minimized_state_restored']=bool(u.IsIconic(window))
        result['foreground_unchanged']=u.GetForegroundWindow()==foreground
        (HERE/'one-hundred-sixth-display.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    sys.exit(outcome.returncode)
finally:k.CloseHandle(process)
