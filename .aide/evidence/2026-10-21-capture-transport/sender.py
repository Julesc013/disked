"""Guest-only owned WM_COPYDATA/anonymous-section control sender."""
import ctypes as C
from ctypes import wintypes as T
import hashlib
import json
from pathlib import Path
import time
import traceback


def run(g,executor,executable,request,stop,result,*,hang=False):
    worker=executor.worker;u=worker.u;k=worker.k;bind=g.W.bind;keep=[];process=None;old_station=old_desktop=prior_dpi=None
    try:
        until=time.monotonic()+2.5;ready=None
        while not stop.is_set() and time.monotonic()<until:
            if executor.child is not None:
                with worker.raw_paths['stdout'].open('rb') as stream:body=stream.read(16385)
                if b'\n' in body:
                    line=body.split(b'\n',1)[0];assert len(line)<=8192;ready=json.loads(line);break
            time.sleep(.005)
        assert ready is not None and ready['schema']=='org.disked.capture-receiver-ready/1' and ready['pid']==str(executor.child.pid) and ready['nonce']==request['nonce']
        child=executor.child;current=bind(k,'GetCurrentProcess',T.HANDLE)();duplicate=bind(k,'DuplicateHandle',T.BOOL,T.HANDLE,T.HANDLE,T.HANDLE,C.POINTER(T.HANDLE),T.DWORD,T.BOOL,T.DWORD)
        owned=T.HANDLE();g.W.require(duplicate(current,child.handle,current,C.byref(owned),0,False,2));process=owned.value
        query=bind(k,'QueryFullProcessImageNameW',T.BOOL,T.HANDLE,T.DWORD,T.LPWSTR,C.POINTER(T.DWORD));image=C.create_unicode_buffer(32768);size=T.DWORD(len(image));g.W.require(query(process,0,image,C.byref(size)));assert Path(image.value).resolve()==executable.resolve()
        member=T.BOOL();member_api=bind(k,'IsProcessInJob',T.BOOL,T.HANDLE,T.HANDLE,C.POINTER(T.BOOL));g.W.require(member_api(process,executor.active_job.handle,C.byref(member)));assert member.value
        token=T.HANDLE();g.W.require(worker.a.OpenProcessToken(process,8,C.byref(token)))
        try:
            assert worker.identity(token)==worker.user_sid and worker.identity(token,kind=25)=='S-1-16-8192'
            assert bind(worker.a,'IsTokenRestricted',T.BOOL,T.HANDLE)(token)
            for kind in (20,29):
                value=T.DWORD();needed=T.DWORD();g.W.require(worker.a.GetTokenInformation(token,kind,C.byref(value),C.sizeof(value),C.byref(needed)));assert value.value==0
        finally:k.CloseHandle(token)
        acl=g.load('capture_acl_comparison',g.ROOT/'owned-window.py')
        expected='D:P(A;;0xf01ff;;;SY)(A;;0xf01ff;;;'+worker.coordinator_sid+')(A;;0xf01ff;;;'+worker.user_sid+')S:(ML;;NW;;;ME)'
        assert acl.desktop_acls(worker.user_object_security(worker.desktop))==acl.desktop_acls(expected)
        old_station=u.GetProcessWindowStation();old_desktop=bind(u,'GetThreadDesktop',T.HANDLE,T.DWORD)(k.GetCurrentThreadId())
        if worker.station:g.W.require(u.SetProcessWindowStation(worker.station))
        g.W.require(bind(u,'SetThreadDesktop',T.BOOL,T.HANDLE)(worker.desktop))
        dpi=bind(u,'SetThreadDpiAwarenessContext',T.HANDLE,T.HANDLE);prior_dpi=dpi(C.c_void_p(-4))
        window=int(ready['window']);owner=T.DWORD();thread=bind(u,'GetWindowThreadProcessId',T.DWORD,T.HWND,C.POINTER(T.DWORD))(window,C.byref(owner));assert owner.value==child.pid and thread==int(ready['thread'])
        rect=T.RECT();g.W.require(bind(u,'GetWindowRect',T.BOOL,T.HWND,C.POINTER(T.RECT))(window,C.byref(rect)));bounds=[rect.left,rect.top,rect.right,rect.bottom];assert bounds==list(map(int,ready['window_rect']))
        protocol=g.load('capture_wire',g.ROOT/'tests/support/capture_transport.py')
        expected_doc=json.loads((g.ROOT/'expected.json').read_bytes())['capture_transport']
        assert [v['name'] for v in ready['guards']]==expected_doc['guard_cases']
        assert all(v==dict(name=v['name'],refused=True,output_unchanged=True,render_called=False,borrowed_handles_open=True) for v in ready['guards'])
        mapping=bind(k,'CreateFileMappingW',T.HANDLE,T.HANDLE,C.c_void_p,T.DWORD,T.DWORD,T.DWORD,T.LPCWSTR)
        map_view=bind(k,'MapViewOfFile',C.c_void_p,T.HANDLE,T.DWORD,T.DWORD,T.DWORD,C.c_size_t)
        send=bind(u,'SendMessageTimeoutW',C.c_ssize_t,T.HWND,T.UINT,C.c_size_t,C.c_ssize_t,T.UINT,T.UINT,C.POINTER(C.c_size_t))
        class Copy(C.Structure):_fields_=[('tag',C.c_size_t),('bytes',T.DWORD),('data',C.c_void_p)]
        result.update(ready=ready,actual_process_id=child.pid,actual_thread_id=thread,desktop_acl_validated=True,actual_user_sid=worker.user_sid,
            image_path_matched=True,job_membership_verified=True,requests=[],frames=[])
        for phase in range(1 if hang else 2):
            section=mapping(C.c_void_p(-1),None,4,0,96256,None);g.W.require(section);view=map_view(section,2,0,0,96256)
            if not view:k.CloseHandle(section);raise C.WinError(C.get_last_error())
            keep.append((section,view));target=T.HANDLE();g.W.require(duplicate(current,section,process,C.byref(target),2,False,0))
            # Fixed identities exist before the receiver paints. No colour/seed
            # enters this packet; it contains only scope and output capability.
            import os
            packet=protocol.encode_request(nonce=int(request['nonce']),sequence=phase+1,width=240,height=96,window=window,process=child.pid,thread=thread,
                job_handle=int(request['job_handle']),section_handle=target.value,volume=int(request['volume']),file_id=bytes.fromhex(request['file_id']),
                case_id=os.urandom(16),window_rect=bounds,desktop=worker.desktop_name)
            buffer=C.create_string_buffer(packet);message=Copy(protocol.TAG,len(packet),C.addressof(buffer));answer=C.c_size_t();C.set_last_error(0)
            accepted=send(window,0x4a,0,C.addressof(message),2,500,C.byref(answer));error=C.get_last_error()
            row=dict(sequence=phase+1,request_hex=packet.hex(),request_sha256=hashlib.sha256(packet).hexdigest(),send_completed=bool(accepted),reply_result=answer.value,winerror=error,section_access=2,inheritable=False)
            result['requests'].append(row)
            if hang:
                assert not accepted and answer.value==0 and C.string_at(view,96256)==bytes(96256);result['sender_timeout_without_publication']=True;break
            assert accepted and answer.value==1
            frame=C.string_at(view,96256);metadata,pixels=protocol.decode_reply(frame,packet)
            assert metadata['descendants']==2;result['frames'].append((metadata,frame,pixels))
        result['status']='pass'
    except BaseException:result.update(status='fail',error=traceback.format_exc()[-8192:])
    finally:
        # Even a completed sender timeout does not retire the paint operation.
        # The coordinator signals only after the owned job is proven quiescent.
        retired=stop.wait(5)
        if not retired:
            result.update(status='fail',quiescence_unverified=True,retained_sections=len(keep));return
        for section,view in keep:
            bind(k,'UnmapViewOfFile',T.BOOL,C.c_void_p)(view);k.CloseHandle(section)
        if process:k.CloseHandle(process)
        if prior_dpi:dpi(prior_dpi)
        if old_station:u.SetProcessWindowStation(old_station)
        if old_desktop:bind(u,'SetThreadDesktop',T.BOOL,T.HANDLE)(old_desktop)
        result['local_views_and_handles_retired_after_quiescence']=True
