"""Guest coordinator control: print one verified job-owned hidden-desktop window.

The caller pins the process and verifies membership in its live job. This helper
rechecks the window/process/desktop binding. No screen DC or foreground input.
"""
import ctypes as C
from ctypes import wintypes as T
import json
import hashlib
import os
from pathlib import Path
import re
import socket
import stat
import struct
import subprocess
import sys
import uuid


def validate_request(value,nonce):
    if (type(value) is not dict or set(value)!={'nonce','id','window','pid','desktop'} or
            value['nonce']!=nonce or not isinstance(value['id'],str) or
            not re.fullmatch(r'[0-9a-f]{32}',value['id']) or
            type(value['window']) is not int or not 0<value['window']<2**64 or
            type(value['pid']) is not int or not 0<value['pid']<2**32 or
            not isinstance(value['desktop'],str) or not re.fullmatch(r'DiskEdTest-[0-9a-f]{32}',value['desktop'])):
        raise ValueError('Capture request identity or scope')


class Broker:
    """Only the exact product in the current job, on a marked private desktop."""
    def __init__(self,worker,fixtures,image,env):
        self.worker,self.fixtures,self.temp=worker,fixtures,worker.native_temp
        self.image=Path(image).resolve(strict=True);self.records=[];self.seen=set();self.nonce=uuid.uuid4().hex
        self.image_sha256=hashlib.sha256(self.image.read_bytes()).hexdigest()
        self.pin=fixtures._open(self.temp,0x81,share=1)
        env.update(DISKED_WINDOW_CAPTURE_ROOT=str(self.temp),DISKED_WINDOW_CAPTURE_NONCE=self.nonce,
                   DISKED_WINDOW_CAPTURE_COORDINATOR_SID=worker.coordinator_sid)

    def poll(self,job):
        pending=list(self.temp.glob('window-capture-request-*.ready'))
        if len(pending)>1:raise ValueError('Capture queue bound')
        for marker in pending:
            info=marker.lstat()
            ident=marker.name[len('window-capture-request-'):-len('.ready')]
            if (not re.fullmatch(r'[0-9a-f]{32}',ident) or ident in self.seen or len(self.seen)>=32 or
                    not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size!=0 or
                    getattr(info,'st_file_attributes',0)&0x400):raise ValueError('Capture ready marker')
            request=marker.with_suffix('.json');handle=self.fixtures._open(request,0x80000080,share=1)
            try:
                standard,tag=self.fixtures._form(handle)
                if (standard.directory or standard.links!=1 or not 0<standard.size<=4096 or tag.attributes&0x400 or
                        self.fixtures._final(handle)!=request or self.fixtures._identity(handle)[0]!=self.fixtures.volume):
                    raise ValueError('Capture packet handle confinement')
                import msvcrt
                fd=msvcrt.open_osfhandle(handle,os.O_RDONLY|os.O_BINARY);handle=None
                with os.fdopen(fd,'rb') as stream:body=stream.read(4097)
                if len(body)>4096:raise ValueError('Capture packet bound')
                value=json.loads(body)
            finally:
                if handle:self.worker.k.CloseHandle(handle)
            validate_request(value,self.nonce)
            if value['id']!=ident:raise ValueError('Capture packet/marker identity')
            observed,pixels=self._capture(job,value)
            observed.update(nonce=self.nonce,id=ident,image_sha256=self.image_sha256)
            response=self.temp/('window-capture-response-'+ident+'.json')
            with response.with_suffix('.bgra').open('xb') as stream:stream.write(pixels)
            with response.open('x',encoding='utf-8') as stream:json.dump(observed,stream)
            self.records.append(observed);self.seen.add(ident)
            request.unlink();marker.unlink();response.with_suffix('.ready').touch(exist_ok=False)

    def prove_refusals(self,job,job_pid):
        controls={}
        for name,pid,reason in (('outside_job',os.getpid(),'Capture target outside current job'),
                                ('different_image',job_pid,'Capture target executable differs')):
            try:self._capture(job,dict(pid=pid,window=1,desktop='DiskEdTest-'+'0'*32))
            except ValueError as error:
                if str(error)!=reason:raise
                controls[name]=True
            else:raise AssertionError('Capture scope control was accepted')
        return controls

    def _capture(self,job,value):
        w=self.worker;k=w.k;u=w.u;b=w.base
        b.bind(k,'OpenProcess',T.HANDLE,T.DWORD,T.BOOL,T.DWORD)
        b.bind(k,'IsProcessInJob',T.BOOL,T.HANDLE,T.HANDLE,C.POINTER(T.BOOL))
        b.bind(k,'QueryFullProcessImageNameW',T.BOOL,T.HANDLE,T.DWORD,T.LPWSTR,C.POINTER(T.DWORD))
        b.bind(u,'OpenDesktopW',T.HANDLE,T.LPCWSTR,T.DWORD,T.BOOL,T.DWORD)
        process=b.require(k.OpenProcess(0x1000,False,value['pid']));desktop=None;token=T.HANDLE()
        try:
            member=T.BOOL();b.require(k.IsProcessInJob(process,job.handle,C.byref(member)))
            if not member.value:raise ValueError('Capture target outside current job')
            image=C.create_unicode_buffer(1024);size=T.DWORD(len(image))
            b.require(k.QueryFullProcessImageNameW(process,0,image,C.byref(size)))
            if Path(image.value).resolve()!=self.image:raise ValueError('Capture target executable differs')
            b.require(w.a.OpenProcessToken(process,8,C.byref(token)))
            if w.identity(token)!=w.user_sid:raise ValueError('Capture target user differs')
            desktop=b.require(u.OpenDesktopW(value['desktop'],0,False,0x20081))
            expected='D:P(A;;0xf01ff;;;SY)(A;;0xf01ff;;;'+w.user_sid+')(A;;0xf01ff;;;'+w.coordinator_sid+')S:(ML;;NW;;;ME)'
            if w.user_object_security(desktop)!=expected:raise ValueError('Capture desktop security differs')
            command=[sys.executable,'-B',str(Path(__file__).resolve()),str(value['window']),str(value['pid']),value['desktop'],'--pixels']
            result=subprocess.run(command,capture_output=True,timeout=10)
            if result.returncode or len(result.stderr)>4096 or len(result.stdout)>16777216+4096:
                raise RuntimeError('Owned capture helper failed: '+result.stderr[-2048:].decode(errors='replace'))
            header,separator,pixels=result.stdout.partition(b'\n')
            if not separator or len(header)>4096:raise ValueError('Capture helper envelope')
            observed=json.loads(header)
            if (observed['window']!=value['window'] or observed['pid']!=value['pid'] or observed['desktop']!=value['desktop'] or
                    observed['method']!='owned-window-dc' or observed['bytes']!=len(pixels) or
                    len(pixels)!=observed['width']*observed['height']*4 or
                    observed['sha256']!=hashlib.sha256(pixels).hexdigest()):raise ValueError('Capture helper pixels differ')
            return observed,pixels
        finally:
            if desktop:u.CloseDesktop(desktop)
            if token:k.CloseHandle(token)
            k.CloseHandle(process)

    def finish(self,*,quiescent):
        if not quiescent:raise ValueError('Capture retirement requires job quiescence')
        try:
            for path in self.temp.glob('window-capture-*'):
                info=path.lstat()
                if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>16777216 or
                        getattr(info,'st_file_attributes',0)&0x400):raise ValueError('Capture cleanup form')
                path.unlink()
            return self.records
        finally:self.worker.k.CloseHandle(self.pin)


def capture(window, pid, desktop, *, pixels=False):
    if (socket.gethostname().casefold() != 'blackglass-hyperv' or
            not re.fullmatch(r'(?:Proof|DiskEdTest)-[0-9a-f]{32}', desktop) or
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
    bind(u,'GetWindowDC',T.HDC,T.HWND)
    bind(u,'ReleaseDC',C.c_int,T.HWND,T.HDC)
    bind(u,'RedrawWindow',T.BOOL,T.HWND,T.LPVOID,T.HANDLE,T.UINT)
    bind(g,'CreateCompatibleDC',T.HDC,T.HDC)
    bind(g,'CreateDIBSection',T.HBITMAP,T.HDC,T.LPVOID,T.UINT,C.POINTER(T.LPVOID),T.HANDLE,T.DWORD)
    bind(g,'SelectObject',T.HANDLE,T.HDC,T.HANDLE)
    bind(g,'DeleteObject',T.BOOL,T.HANDLE)
    bind(g,'DeleteDC',T.BOOL,T.HDC)
    bind(g,'GdiFlush',T.BOOL)
    bind(g,'BitBlt',T.BOOL,T.HDC,C.c_int,C.c_int,C.c_int,C.c_int,T.HDC,C.c_int,C.c_int,T.DWORD)
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
        printed=False if pixels else u.PrintWindow(window,dc,0)
        g.GdiFlush();body=C.string_at(bits,width*height*4)
        rgb={value[0]&0xffffff for value in struct.iter_unpack('<I',body)}
        C.memset(bits,0,width*height*4)
        source=u.GetWindowDC(window)
        try:
            C.set_last_error(0)
            copied=bool(source and g.BitBlt(dc,0,0,width,height,source,0,0,0x40cc0020))
            error=0 if copied else C.get_last_error()
            g.GdiFlush();window_body=C.string_at(bits,width*height*4)
            window_rgb={value[0]&0xffffff for value in struct.iter_unpack('<I',window_body)}
            window_dc=dict(acquired=bool(source),copied=copied,error=error,rgb_colors=len(window_rgb),
                           varied=len(window_rgb)>1,first_bgr=window_body[:3].hex())
        finally:
            if source:u.ReleaseDC(window,source)
        if pixels:
            if not window_dc['copied']:raise RuntimeError('Owned window DC copy failed')
            # Detect replacement/resize across the actual copy.
            after=T.RECT();after_pid=T.DWORD()
            if (not u.GetWindowRect(window,C.byref(after)) or
                    not u.GetWindowThreadProcessId(window,C.byref(after_pid)) or after_pid.value!=pid or
                    tuple(getattr(after,k) for k in ('left','top','right','bottom'))!=
                    tuple(getattr(bounds,k) for k in ('left','top','right','bottom'))):
                raise ValueError('Owned window identity or bounds changed during copy')
            return dict(window=window,pid=pid,desktop=desktop,width=width,height=height,
                        method='owned-window-dc',bytes=len(window_body),sha256=hashlib.sha256(window_body).hexdigest()),window_body
        return dict(window=window,pid=pid,desktop=desktop,width=width,height=height,
                    printed=bool(printed),rgb_colors=len(rgb),varied=len(rgb)>1,first_bgr=body[:3].hex(),window_dc=window_dc)
    finally:
        if old not in (None,C.c_void_p(-1).value):g.SelectObject(dc,old)
        if bitmap:g.DeleteObject(bitmap)
        if dc:g.DeleteDC(dc)
        if not u.SetThreadDesktop(previous):raise C.WinError(C.get_last_error())
        u.CloseDesktop(target)


if __name__=='__main__':
    pixels=len(sys.argv)==5 and sys.argv[4]=='--pixels'
    if len(sys.argv)!=4 and not pixels:raise ValueError('Exact window/process/desktop arguments required')
    observed=capture(int(sys.argv[1]),int(sys.argv[2]),sys.argv[3],pixels=pixels)
    if pixels:
        header,body=observed
        sys.stdout.buffer.write(json.dumps(header).encode()+b'\n'+body)
    else:print(json.dumps(observed))
