"""Exercise the native worker-store helper using only generated owned folders.

Baseline observation and fixed qualification remain separate modes.
"""
import argparse,ctypes as C,hashlib,json,queue,subprocess,tempfile,threading
from ctypes import wintypes as W
from pathlib import Path

def sha(b):return 'sha256:'+hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--probe',required=True,type=Path);p.add_argument('--root',required=True,type=Path)
    p.add_argument('--evidence',type=Path);p.add_argument('--baseline',action='store_true');a=p.parse_args()
    root=a.root.resolve();scratch=root/'.aide-local';scratch.mkdir(exist_ok=True);probe=a.probe.resolve();records=[]
    with tempfile.TemporaryDirectory(prefix='worker-directory-',dir=scratch) as temp:
        owned=Path(temp).resolve();assert owned.is_relative_to(scratch) and scratch.is_relative_to(root)
        for role in ('directory','ancestor'):
            folder=owned/role;parent=folder/'parent';directory=parent/'state';directory.mkdir(parents=True)
            target=directory if role=='directory' else parent;renamed=folder/'moved'
            assert target.resolve().is_relative_to(owned) and renamed.resolve().is_relative_to(owned)
            original=directory.stat().st_ino;messages=queue.Queue()
            child=subprocess.Popen([str(probe),str(directory)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root)
            threading.Thread(target=lambda:messages.put(child.stdout.readline()),daemon=True).start()
            try:
                first=messages.get(timeout=12);held=json.loads(first);assert held['event']=='directory-held' and int(held['pid'])==child.pid and child.poll() is None
                moved=False;error=None
                try:target.rename(renamed);moved=True
                except PermissionError as e:error=e.winerror
                if moved:directory.mkdir(parents=True);assert directory.stat().st_ino!=original
                child.stdin.write(b'x');child.stdin.close();child.stdin=None;out,err=child.communicate(timeout=20)
                assert child.returncode==0 and not err,(child.returncode,out,err)
                result=json.loads(out);assert result['status']=='completed' and result['directory_id']==held['directory_id']
                output=directory/'fixture.records';assert output.read_bytes()==b'owned-worker-store\n'
                old=(renamed if role=='directory' else renamed/'state')/'fixture.records'
                record=dict(name=role,pid=child.pid,alive_observed=True,terminal_observed=True,exit_code=child.returncode,renamed=moved,rename_platform_code=error,
                    original_directory_id=str(original),output_directory_id=str(directory.stat().st_ino),old_directory_has_output=old.exists() if moved else None,
                    output_sha256=sha(output.read_bytes()),response_sha256=sha(first+out),response=result)
                print(json.dumps(record),flush=True)
                if a.baseline and role=='directory':assert moved and record['output_directory_id']!=record['original_directory_id'] and not old.exists()
                elif a.baseline:assert not moved and error==5 and record['output_directory_id']==record['original_directory_id']
                else:assert not moved and error in (5,32) and record['output_directory_id']==record['original_directory_id']
                records.append(record)
            finally:
                if child.poll() is None:child.kill();child.wait(timeout=10)
                child.stdout.close();child.stderr.close()
        if not a.baseline:
            advapi=C.WinDLL('advapi32',use_last_error=True);kernel=C.WinDLL('kernel32',use_last_error=True)
            advapi.GetFileSecurityW.argtypes=[W.LPCWSTR,W.DWORD,C.c_void_p,W.DWORD,C.POINTER(W.DWORD)];advapi.GetFileSecurityW.restype=W.BOOL
            advapi.SetFileSecurityW.argtypes=[W.LPCWSTR,W.DWORD,C.c_void_p];advapi.SetFileSecurityW.restype=W.BOOL
            advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes=[W.LPCWSTR,W.DWORD,C.POINTER(C.c_void_p),C.POINTER(W.DWORD)];advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype=W.BOOL
            advapi.GetSecurityDescriptorControl.argtypes=[C.c_void_p,C.POINTER(W.WORD),C.POINTER(W.DWORD)];advapi.GetSecurityDescriptorControl.restype=W.BOOL
            kernel.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,W.HANDLE];kernel.CreateFileW.restype=W.HANDLE
            kernel.CloseHandle.argtypes=[W.HANDLE];kernel.CloseHandle.restype=W.BOOL
            kernel.LocalFree.argtypes=[C.c_void_p];kernel.LocalFree.restype=C.c_void_p
            kernel.GetFileTime.argtypes=[W.HANDLE,C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME)];kernel.GetFileTime.restype=W.BOOL
            kernel.SetFileTime.argtypes=[W.HANDLE,C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME)];kernel.SetFileTime.restype=W.BOOL
            for role in ('directory','ancestor'):
                directory=owned/('generation-'+role)/'parent'/'state';directory.mkdir(parents=True)
                target=directory if role=='directory' else directory.parent;assert target.resolve().is_relative_to(owned)
                child=subprocess.Popen([str(probe),str(directory)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root)
                messages=queue.Queue();threading.Thread(target=lambda:messages.put(child.stdout.readline()),daemon=True).start()
                handle=None;created=W.FILETIME();changed=W.FILETIME()
                try:
                    held=json.loads(messages.get(timeout=12));assert held['event']=='directory-held' and int(held['pid'])==child.pid and child.poll() is None
                    # Metadata-only writes are a separate dimension from data/
                    # delete sharing. Observe a real owned generation change.
                    handle=kernel.CreateFileW(str(target),0x100,1,None,3,0x02200000,None)
                    assert handle not in (None,C.c_void_p(-1).value),C.get_last_error()
                    assert kernel.GetFileTime(handle,C.byref(created),None,None)
                    before=(created.dwHighDateTime<<32)|created.dwLowDateTime;after=before+10000000
                    changed.dwHighDateTime=after>>32;changed.dwLowDateTime=after&0xffffffff
                    assert kernel.SetFileTime(handle,C.byref(changed),None,None)
                    child.stdin.write(b'x');child.stdin.close();child.stdin=None;out,err=child.communicate(timeout=20)
                    response=json.loads(out);assert child.returncode==3 and not err and response['code']=='operation_directory_changed',response
                    assert not (directory/'fixture.records').exists()
                    records.append(dict(name='generation-'+role,pid=child.pid,alive_observed=True,terminal_observed=True,
                        old_created=str(before),new_created=str(after),exit_code=child.returncode,response=response))
                finally:
                    if child.poll() is None:child.kill();child.wait(timeout=10)
                    if handle not in (None,C.c_void_p(-1).value):
                        assert kernel.SetFileTime(handle,C.byref(created),None,None);assert kernel.CloseHandle(handle)
                    child.stdout.close();child.stderr.close()
            directory=owned/'metadata-only';directory.mkdir();needed=W.DWORD()
            advapi.GetFileSecurityW(str(directory),4,None,0,C.byref(needed));assert needed.value
            old=C.create_string_buffer(needed.value);assert advapi.GetFileSecurityW(str(directory),4,old,len(old),C.byref(needed))
            control=W.WORD();revision=W.DWORD();assert advapi.GetSecurityDescriptorControl(old,C.byref(control),C.byref(revision))
            sd=C.c_void_p();assert advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW('D:P(A;;0x1200a0;;;WD)',1,C.byref(sd),None)
            try:
                assert advapi.SetFileSecurityW(str(directory),4|0x80000000,sd)
                h=kernel.CreateFileW(str(directory),0x80,1,None,3,0x02200000,None);assert h not in (None,C.c_void_p(-1).value);assert kernel.CloseHandle(h)
                result=subprocess.run([str(probe),str(directory)],input=b'x',capture_output=True,cwd=root,timeout=20)
                response=json.loads(result.stdout);assert result.returncode==3 and not result.stderr and response['code']=='operation_directory_unavailable' and response['platform_code']=='5',response
                records.append(dict(name='no-metadata-only-fallback',metadata_only_access=True,exit_code=result.returncode,response=response))
            finally:
                assert advapi.SetFileSecurityW(str(directory),4|(0x80000000 if control.value&0x1000 else 0x20000000),old);assert kernel.LocalFree(sd) is None
            assert not (directory/'fixture.records').exists()
    result=dict(passed=True,mode='baseline-helper-defect' if a.baseline else 'fixed-helper-contract',cases=len(records),probe_sha256=sha(probe.read_bytes()),records=records,
        base_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),physical_io=False,power_loss_qualified=False,whole_worker_redirection_qualified=False)
    if a.evidence:a.evidence.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(passed=True,cases=len(records),mode=result['mode'])))

if __name__=='__main__':main()
