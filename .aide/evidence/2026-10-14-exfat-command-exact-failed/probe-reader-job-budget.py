import ctypes as C
import argparse
import json
from pathlib import Path
root = Path.cwd()
parser = argparse.ArgumentParser()
parser.add_argument('--host', required=True)
host = parser.parse_args().host
k = C.WinDLL('kernel32', use_last_error=True)
k.OpenJobObjectW.argtypes = [C.c_uint32, C.c_int, C.c_wchar_p]
k.OpenJobObjectW.restype = C.c_void_p
k.QueryInformationJobObject.argtypes = [C.c_void_p, C.c_int, C.c_void_p, C.c_uint32, C.c_void_p]
k.CloseHandle.argtypes = [C.c_void_p]
class Accounting(C.Structure):
    _fields_ = [(name, C.c_int64) for name in ['user', 'kernel', 'period_user', 'period_kernel']] + [
        (name, C.c_uint32) for name in ['page_faults', 'processes', 'active', 'terminated']]
name = 'Local\\DiskEd.Fake.Workers.v1.' + host
handle = k.OpenJobObjectW(4, False, name)
value = dict(job_name=name, opened=bool(handle))
try:
    if handle:
        accounting = Accounting()
        assert k.QueryInformationJobObject(handle, 1, C.byref(accounting), C.sizeof(accounting), None), C.get_last_error()
        value['accounting'] = {name: getattr(accounting, name) for name, _ in Accounting._fields_}
    else: value['platform_code'] = C.get_last_error()
finally:
    if handle: k.CloseHandle(handle)
(root / '.aide-local/exfat-reader-job-budget-probe.json').write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
print(json.dumps(value, indent=2))
