"""Trusted product coordinator: owned client repaint, no display-DC fallback."""
import ctypes as C
from ctypes import wintypes as T
import hashlib
import importlib.util
import json
import os
from pathlib import Path

METHOD='owned-ui-thread-cooperative-client-tree-transport/1'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


class Coordinator:
    def __new__(cls,worker,fixtures,image,env,*,expected_sha256,source_root,new_job,retire_job):
        legacy=load('product_capture_scope',Path(__file__).with_name('owned-window.py'))
        protocol=load('product_capture_protocol',Path(source_root)/'tests/support/capture_transport.py')
        class Bound(legacy.Broker):
            method=METHOD
            def __init__(self):
                self.memberships={};self.sections=[];self.retirements=[];self.remote_transfers=[]
                self.protocol=protocol
                super().__init__(worker,fixtures,image,env,expected_sha256=expected_sha256)
                self.capture_nonce=int(self.nonce[:16],16)
                while not self.capture_nonce&0xffffffff or not self.capture_nonce>>32:self.capture_nonce=int.from_bytes(os.urandom(8),'little')
                env.update(DISKED_GUI_CAPTURE_TEST='owned-client-tree/1',DISKED_GUI_CAPTURE_NONCE=f'{self.capture_nonce:016x}',DISKED_WINDOW_CAPTURE_METHOD=METHOD)
            def poll(self,job):
                if len(self.seen)>=6 and list(self.temp.glob('window-capture-request-*.ready')):raise ValueError('Six-case capture request bound')
                super().poll(job)
            def _read_pixels(self,value,job=None):
                w=self.worker;k=w.k;u=w.u;b=w.base;bind=b.bind
                pid=value['pid'];window=value['window']
                if pid not in self.memberships:
                    process=b.require(bind(k,'OpenProcess',T.HANDLE,T.DWORD,T.BOOL,T.DWORD)(0x101141,False,pid))
                    token=T.HANDLE()
                    if not w.a.OpenProcessToken(process,8,C.byref(token)):
                        error=C.WinError(C.get_last_error());k.CloseHandle(process);raise error
                    try:
                        if w.identity(token)!=w.user_sid or w.identity(token,kind=25)!='S-1-16-8192' or not bind(w.a,'IsTokenRestricted',T.BOOL,T.HANDLE)(token):raise ValueError('Capture ordinary token differs')
                        for kind in (20,29):
                            flag=T.DWORD();needed=T.DWORD();b.require(w.a.GetTokenInformation(token,kind,C.byref(flag),C.sizeof(flag),C.byref(needed)))
                            if flag.value:raise ValueError('Capture ordinary token differs')
                    except BaseException:k.CloseHandle(process);raise
                    finally:k.CloseHandle(token)
                    member=T.BOOL()
                    if not k.IsProcessInJob(process,job.handle,C.byref(member)):
                        error=C.WinError(C.get_last_error());k.CloseHandle(process);raise error
                    if not member.value:k.CloseHandle(process);raise ValueError('Capture target outside current job')
                    try:inner=new_job()
                    except BaseException:k.CloseHandle(process);raise
                    entry=dict(process=process,job=inner,sequence=0,query=None);self.memberships[pid]=entry
                    b.require(inner.api.AssignProcessToJobObject(inner.handle,process))
                    current=bind(k,'GetCurrentProcess',T.HANDLE)();target=T.HANDLE()
                    duplicate=bind(k,'DuplicateHandle',T.BOOL,T.HANDLE,T.HANDLE,T.HANDLE,C.POINTER(T.HANDLE),T.DWORD,T.BOOL,T.DWORD)
                    b.require(duplicate(current,inner.handle,process,C.byref(target),4,False,0));entry['query']=target.value
                entry=self.memberships[pid];entry['sequence']+=1
                if entry['sequence']>8:raise ValueError('Per-process receiver request bound')
                current=bind(k,'GetCurrentProcess',T.HANDLE)();duplicate=bind(k,'DuplicateHandle',T.BOOL,T.HANDLE,T.HANDLE,T.HANDLE,C.POINTER(T.HANDLE),T.DWORD,T.BOOL,T.DWORD)
                desktop=b.require(bind(u,'OpenDesktopW',T.HANDLE,T.LPCWSTR,T.DWORD,T.BOOL,T.DWORD)(value['desktop'],0,False,0x20081))
                prior_desktop=bind(u,'GetThreadDesktop',T.HANDLE,T.DWORD)(bind(k,'GetCurrentThreadId',T.DWORD)())
                prior_dpi=None;set_desktop=bind(u,'SetThreadDesktop',T.BOOL,T.HANDLE)
                try:
                    b.require(set_desktop(desktop))
                    dpi=bind(u,'SetThreadDpiAwarenessContext',T.HANDLE,T.HANDLE);prior_dpi=dpi(C.c_void_p(-2))
                    owner=T.DWORD();thread=bind(u,'GetWindowThreadProcessId',T.DWORD,T.HWND,C.POINTER(T.DWORD))(window,C.byref(owner))
                    if owner.value!=pid or not thread:raise ValueError('Capture window ownership changed')
                    frame=T.RECT();client=T.RECT();get_frame=bind(u,'GetWindowRect',T.BOOL,T.HWND,C.POINTER(T.RECT));get_client=bind(u,'GetClientRect',T.BOOL,T.HWND,C.POINTER(T.RECT))
                    b.require(get_frame(window,C.byref(frame)));b.require(get_client(window,C.byref(client)))
                    bounds=[frame.left,frame.top,frame.right,frame.bottom];width,height=client.right,client.bottom
                    if client.left or client.top or not 0<width<=4096 or not 0<height<=2160 or width*height*4>16777216:raise ValueError('Capture client dimensions')
                    total=4096+width*height*4
                    section=b.require(bind(k,'CreateFileMappingW',T.HANDLE,T.HANDLE,C.c_void_p,T.DWORD,T.DWORD,T.DWORD,T.LPCWSTR)(C.c_void_p(-1),None,4,0,total,None))
                    view=bind(k,'MapViewOfFile',C.c_void_p,T.HANDLE,T.DWORD,T.DWORD,T.DWORD,C.c_size_t)(section,2,0,0,total)
                    if not view:k.CloseHandle(section);raise C.WinError(C.get_last_error())
                    self.sections.append((section,view));target=T.HANDLE();b.require(duplicate(current,section,entry['process'],C.byref(target),2,False,0))
                    packet=protocol.encode_request(nonce=self.capture_nonce,sequence=entry['sequence'],width=width,height=height,window=window,process=pid,thread=thread,
                        job_handle=entry['query'],section_handle=target.value,volume=int(self.image_identity[0]),file_id=bytes.fromhex(self.image_identity[1]),case_id=bytes.fromhex(value['id']),
                        window_rect=bounds,desktop=w.desktop_name.split('\\')[0]+'\\'+value['desktop'])
                    class Copy(C.Structure):_fields_=[('tag',C.c_size_t),('bytes',T.DWORD),('data',C.c_void_p)]
                    raw=C.create_string_buffer(packet);message=Copy(protocol.TAG,len(packet),C.addressof(raw));answer=C.c_size_t()
                    accepted=bind(u,'SendMessageTimeoutW',C.c_ssize_t,T.HWND,T.UINT,C.c_size_t,C.c_ssize_t,T.UINT,T.UINT,C.POINTER(C.c_size_t))(window,0x4a,0,C.addressof(message),2,500,C.byref(answer))
                    if not accepted or answer.value!=1:raise RuntimeError('Cooperative receiver did not acknowledge;retire original job before cleanup')
                    body=C.string_at(view,total);observed,pixels=protocol.decode_reply(body,packet)
                    after=T.RECT();b.require(get_frame(window,C.byref(after)))
                    if [after.left,after.top,after.right,after.bottom]!=bounds:raise ValueError('Capture frame changed after reply')
                    observed.update(window=window,pid=pid,desktop=value['desktop'],method=METHOD,client_box=[0,0,width,height],frame_bounds=bounds,
                        coordinator_integrity_sid=w.coordinator_integrity_sid,
                        request_sha256=hashlib.sha256(packet).hexdigest(),request_hex=packet.hex(),reply_header_hex=body[:124].hex(),membership_job_query_access=4,
                        output_section_access=2,supervisor_handle_exposed=False,receiver_sequence=entry['sequence'],capture_id=value['id'])
                    self.remote_transfers.append(dict(pid=pid,sequence=entry['sequence'],query_access=4,section_access=2,supervisor_exposed=False))
                    header=json.dumps(observed,separators=(',',':')).encode()
                    if len(header)>4096:raise ValueError('Capture envelope bound')
                    return header+b'\n'+pixels
                finally:
                    if prior_dpi:dpi(prior_dpi)
                    b.require(set_desktop(prior_desktop));u.CloseDesktop(desktop)
            def finish(self,*,quiescent):
                if not quiescent:raise ValueError('Cooperative capture requires supervisor quiescence')
                for entry in self.memberships.values():
                    self.retirements.append(retire_job(entry['job']));worker.k.CloseHandle(entry['process'])
                for section,view in self.sections:
                    worker.base.bind(worker.k,'UnmapViewOfFile',T.BOOL,C.c_void_p)(view);worker.k.CloseHandle(section)
                for row in self.records:row.update(membership_jobs_retired=True,output_sections_retired=True)
                return super().finish(quiescent=True)
        return Bound()
