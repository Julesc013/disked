"""Paired old/default versus actual fixture desktop; owned children only."""
import ctypes as C
import atexit
from ctypes import wintypes as T
import importlib.util
import json
from pathlib import Path
import sys
import uuid

ROOT=Path('C:/ProgramData/DiskEd/qualification')
spec=importlib.util.spec_from_file_location('actual_gui_fixture',ROOT/'tests/frontend/gui_fixture.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
exe=Path(sys.argv[1]).resolve();work=Path.cwd()
if exe.parent!=work or exe.name!='memory-budget.exe' or len(sys.argv)!=3:raise ValueError('Owned component arguments only')
sid=sys.argv[2];rows=[]
atexit.register(lambda:print(json.dumps(dict(scope=__doc__,cases=rows))))

def acl_entries(a,descriptor,sacl):
    """Compare exact ACE bytes, independently of SDDL's rights spelling."""
    getter=fixture.bind(a,'GetSecurityDescriptorSacl' if sacl else 'GetSecurityDescriptorDacl',T.BOOL,
        [T.LPVOID,C.POINTER(T.BOOL),C.POINTER(T.LPVOID),C.POINTER(T.BOOL)])
    present,defaulted=T.BOOL(),T.BOOL();acl=T.LPVOID()
    if not getter(descriptor,C.byref(present),C.byref(acl),C.byref(defaulted)) or not present.value or not acl:raise ValueError('Absent desktop ACL')
    size=C.c_ushort.from_address(acl.value+2).value;count=C.c_ushort.from_address(acl.value+4).value
    if not 8<=size<=4096 or not 0<count<=8:raise ValueError('Desktop ACL bound')
    get=fixture.bind(a,'GetAce',T.BOOL,[T.LPVOID,T.DWORD,C.POINTER(T.LPVOID)]);values=[]
    for index in range(count):
        ace=T.LPVOID()
        if not get(acl,index,C.byref(ace)):raise C.WinError(C.get_last_error())
        if not acl.value+8<=ace.value<=acl.value+size-4:raise ValueError('Desktop ACE header range')
        length=C.c_ushort.from_address(ace.value+2).value
        if length<16 or length%4 or ace.value+length>acl.value+size:raise ValueError('Desktop ACE range')
        values.append(C.string_at(ace,length).hex())
    return values
for explicit in (False,True):
    desktop=process=previous=None;row=dict(explicit_subject_acl=explicit)
    try:
        if explicit:desktop,name=fixture.owned_desktop()
        else:
            # The exact original factory call, retained as a regression control.
            leaf='DiskEdTest-'+uuid.uuid4().hex;desktop=fixture.U.CreateDesktopW(leaf,None,None,0,0x1ff,None)
            if not desktop:raise C.WinError(C.get_last_error())
            station=C.create_unicode_buffer(1024);needed=T.DWORD()
            if not fixture.U.GetUserObjectInformationW(fixture.U.GetProcessWindowStation(),2,station,C.sizeof(station),C.byref(needed)):raise C.WinError(C.get_last_error())
            name=station.value+'\\'+leaf
        row['desktop']=name
        if explicit:
            query=fixture.bind(fixture.U,'GetUserObjectSecurity',T.BOOL,[T.HANDLE,C.POINTER(T.DWORD),T.LPVOID,T.DWORD,C.POINTER(T.DWORD)])
            a=C.WinDLL('advapi32',use_last_error=True)
            convert=fixture.bind(a,'ConvertSecurityDescriptorToStringSecurityDescriptorW',T.BOOL,[T.LPVOID,T.DWORD,T.DWORD,C.POINTER(T.LPWSTR),T.LPVOID])
            kind=T.DWORD(0x14);size=T.DWORD();query(desktop,C.byref(kind),None,0,C.byref(size))
            if not 0<size.value<=4096:raise ValueError('Owned desktop descriptor bound')
            data=C.create_string_buffer(size.value)
            if not query(desktop,C.byref(kind),data,size,C.byref(size)):raise C.WinError(C.get_last_error())
            text=T.LPWSTR()
            if not convert(data,1,kind.value,C.byref(text),None):raise C.WinError(C.get_last_error())
            try:row['security']=text.value
            finally:fixture.K.LocalFree(C.cast(text,T.LPVOID))
            expected=T.LPVOID()
            parse=fixture.bind(a,'ConvertStringSecurityDescriptorToSecurityDescriptorW',T.BOOL,[T.LPCWSTR,T.DWORD,C.POINTER(T.LPVOID),T.LPVOID])
            if not parse('D:P(A;;0xf01ff;;;SY)(A;;0xf01ff;;;'+sid+')S:(ML;;NW;;;ME)',1,C.byref(expected),None):raise C.WinError(C.get_last_error())
            try:
                row['dacl_aces']=acl_entries(a,data,False);row['expected_dacl_aces']=acl_entries(a,expected,False)
                row['label_aces']=acl_entries(a,data,True);row['expected_label_aces']=acl_entries(a,expected,True)
                control=T.WORD();revision=T.DWORD()
                query_control=fixture.bind(a,'GetSecurityDescriptorControl',T.BOOL,[T.LPVOID,C.POINTER(T.WORD),C.POINTER(T.DWORD)])
                if not query_control(data,C.byref(control),C.byref(revision)):raise C.WinError(C.get_last_error())
                row['descriptor_control']=hex(control.value);row['protected_dacl']=bool(control.value&0x1000)
            finally:fixture.K.LocalFree(expected)
        previous=fixture.U.GetThreadDesktop(fixture.K.GetCurrentThreadId())
        if not fixture.U.SetThreadDesktop(desktop):raise C.WinError(C.get_last_error())
        process=fixture.DesktopProcess([str(exe)],str(work),name)
        out,error=process.communicate(timeout=15);row.update(exit_code=process.returncode,stderr=error.decode(),native=json.loads(out))
    finally:
        if process and process.poll() is None:process.kill();process.communicate(timeout=5)
        if previous and not fixture.U.SetThreadDesktop(previous):raise C.WinError(C.get_last_error())
        if desktop:
            if not fixture.U.CloseDesktop(desktop):raise C.WinError(C.get_last_error())
            row['desktop_handle_closed']=True
        rows.append(row)
assert rows[1]['protected_dacl'] and rows[1]['dacl_aces']==rows[1]['expected_dacl_aces'] and rows[1]['label_aces']==rows[1]['expected_label_aces'],rows[1]
assert rows[0]['exit_code']==3 and not rows[0]['native']['user32_loaded'] and rows[0]['native']['ready']
assert rows[1]['exit_code']==0 and rows[1]['native']['user32_loaded'] and rows[1]['native']['ready']
assert all(row['desktop_handle_closed'] and not row['stderr'] for row in rows)
