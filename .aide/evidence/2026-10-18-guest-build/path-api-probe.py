"""Read-only path/volume API observations on one owned generated fixture."""
import ctypes
from ctypes import wintypes as T
import json
from pathlib import Path
import sys

sys.path.insert(0,sys.argv[1])
from support.tempdir import temporary_directory

kernel = ctypes.WinDLL('kernel32',use_last_error=True)
kernel.CreateFileW.argtypes = [T.LPCWSTR,T.DWORD,T.DWORD,ctypes.c_void_p,T.DWORD,T.DWORD,T.HANDLE]
kernel.CreateFileW.restype = T.HANDLE
kernel.CloseHandle.argtypes = [T.HANDLE]
kernel.GetFinalPathNameByHandleW.argtypes = [T.HANDLE,T.LPWSTR,T.DWORD,T.DWORD]
kernel.GetFinalPathNameByHandleW.restype = T.DWORD
kernel.GetFileInformationByHandleEx.argtypes = [T.HANDLE,ctypes.c_int,ctypes.c_void_p,T.DWORD]
kernel.QueryDosDeviceW.argtypes = [T.LPCWSTR,T.LPWSTR,T.DWORD]
kernel.QueryDosDeviceW.restype = T.DWORD
result = dict(scope='Owned generated fixture and its ancestors; no product execution',paths=[])
with temporary_directory(prefix='disked-path-api-') as directory:
    target=Path(directory)/'generated.img'
    target.write_bytes(b'owned path probe')
    device=ctypes.create_unicode_buffer(1024)
    ctypes.set_last_error(0)
    count=kernel.QueryDosDeviceW(target.drive,device,len(device))
    result['dos_device']=dict(drive=target.drive,count=count,error=ctypes.get_last_error(),name=device.value if count else None)
    handles=[]
    try:
        for path in [*reversed(target.parents),target]:
            row=dict(path=str(path),final_names=[])
            ctypes.set_last_error(0)
            handle=kernel.CreateFileW(str(path),0x80000000,1,None,3,0x02200000,None)
            row['open_error']=ctypes.get_last_error()
            if handle==ctypes.c_void_p(-1).value:
                result['paths'].append(row)
                break
            handles.append(handle)
            for flags in (0,1,2,4,8,9,10,12):
                buffer=ctypes.create_unicode_buffer(1024)
                ctypes.set_last_error(0)
                count=kernel.GetFinalPathNameByHandleW(handle,buffer,len(buffer),flags)
                row['final_names'].append(dict(flags=flags,count=count,error=ctypes.get_last_error(),
                    name=buffer.value if 0<count<len(buffer) else None))
            for kind,size in ((18,24),(2,2048)):
                buffer=ctypes.create_string_buffer(size)
                ctypes.set_last_error(0)
                ok=kernel.GetFileInformationByHandleEx(handle,kind,buffer,size)
                observation=dict(ok=bool(ok),error=ctypes.get_last_error())
                if ok and kind==18:
                    observation.update(volume_serial=str(int.from_bytes(buffer.raw[:8],'little')),file_id=buffer.raw[8:24].hex())
                if ok and kind==2:
                    length=int.from_bytes(buffer.raw[:4],'little')
                    assert length<=size-4 and length%2==0
                    observation['name']=buffer.raw[4:4+length].decode('utf-16-le')
                row[str(kind)]=observation
            result['paths'].append(row)
    finally:
        for handle in reversed(handles):kernel.CloseHandle(handle)
print(json.dumps(result))
