"""Attach only the newly owned guest VHD, with device access separate from its backing file."""
import ctypes as C
from ctypes import wintypes as T
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import uuid

ROOT = Path(__file__).resolve().parent


class Guid(C.Structure):
    _fields_ = [('a', T.DWORD), ('b', T.WORD), ('c', T.WORD), ('d', T.BYTE * 8)]


class StorageType(C.Structure):
    _fields_ = [('device', T.DWORD), ('vendor', Guid)]


class OpenUnion(C.Union):
    _fields_ = [('depth', T.DWORD), ('space', T.BYTE * 40)]


class OpenParameters(C.Structure):
    _fields_ = [('version', T.DWORD), ('data', OpenUnion)]


class AttachUnion(C.Union):
    _fields_ = [('reserved', T.DWORD), ('range', C.c_uint64 * 2)]


class AttachParameters(C.Structure):
    _fields_ = [('version', T.DWORD), ('data', AttachUnion)]


class Luid(C.Structure):
    _fields_ = [('low', T.DWORD), ('high', T.LONG)]


class Privileges(C.Structure):
    _fields_ = [('count', T.DWORD), ('luid', Luid), ('attributes', T.DWORD)]


def main():
    if os.name != 'nt' or ROOT != Path('C:/ProgramData/DiskEd/qualification'):
        raise RuntimeError('Fixed guest qualification directory required')
    config = json.loads((ROOT / 'scratch/attach-config.json').read_bytes())
    owner = json.loads((ROOT / 'scratch/owner.json').read_bytes())
    if config['nonce'] != owner['nonce'] or len(config['profile_names']) != 3:
        raise RuntimeError('Attachment ownership mismatch')
    if config['size_mib'] not in (32, 512):
        raise RuntimeError('Only the approved proof sizes are permitted')
    capacity = config['size_mib'] * 1024 * 1024
    if len(set(config['profile_names'])) != 3 or any(not re.fullmatch(r'org\.disked\.worker\.[0-9a-f]{32}', name) for name in config['profile_names']):
        raise RuntimeError('Invalid campaign identities')
    spec = importlib.util.spec_from_file_location('worker', ROOT / 'tools/windows-worker.py')
    w = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(w)
    k, a, e, v = [C.WinDLL(name, use_last_error=True) for name in ('kernel32', 'advapi32', 'userenv', 'virtdisk')]
    P = C.c_void_p
    w.bind(k, 'GetCurrentProcess', T.HANDLE)
    w.bind(k, 'CloseHandle', T.BOOL, T.HANDLE)
    w.bind(k, 'LocalFree', P, P)
    w.bind(a, 'GetUserNameW', T.BOOL, T.LPWSTR, C.POINTER(T.DWORD))
    user = C.create_unicode_buffer(256); size = T.DWORD(256)
    w.require(a.GetUserNameW(user, C.byref(size)))
    if user.value.casefold() != 'agents' or not C.windll.shell32.IsUserAnAdmin():
        raise RuntimeError('Authorized Agents administrator required')
    image = ROOT / 'scratch/disked-proof.vhd'
    w.plain_directory(image.parent)
    if image.lstat().st_file_attributes & 0x400 or image.stat().st_size != capacity + 512:
        raise RuntimeError('Wrong fixed image')
    with image.open('rb') as source:
        source.seek(-512, 2); footer = source.read(512)
    if (footer[:8] != b'conectix' or struct.unpack_from('>I', footer, 60)[0] != 2 or
            struct.unpack_from('>Q', footer, 48)[0] != capacity or footer[68:84].hex().upper() != config['image_uuid']):
        raise RuntimeError('Image identity or size changed')
    w.bind(e, 'DeriveAppContainerSidFromAppContainerName', C.c_long, T.LPCWSTR, C.POINTER(P))
    w.bind(a, 'ConvertSidToStringSidW', T.BOOL, P, C.POINTER(T.LPWSTR))
    w.bind(a, 'FreeSid', P, P)
    profiles = []
    for name in config['profile_names']:
        sid = P(); text = T.LPWSTR()
        if e.DeriveAppContainerSidFromAppContainerName(name, C.byref(sid)) < 0:
            raise RuntimeError('Cannot derive campaign SID')
        try:
            w.require(a.ConvertSidToStringSidW(sid, C.byref(text)))
            profiles.append(dict(name=name, sid=text.value))
        finally:
            if text: k.LocalFree(C.cast(text, P))
            a.FreeSid(sid)
    sddl = ('D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GA;;;' + config['actor_sid'] + ')' +
            # Modify includes DELETE: temporary-file creation and retirement
            # need it at the attached device as well as the owned directory.
            # WRITE_DAC and WRITE_OWNER remain absent. This SD does not apply
            # to the backing file, whose separate ACL is unchanged.
            ''.join('(A;;0x1301bf;;;' + p['sid'] + ')' for p in profiles) + 'S:(ML;;NW;;;LW)')
    w.bind(a, 'ConvertStringSecurityDescriptorToSecurityDescriptorW', T.BOOL, T.LPCWSTR, T.DWORD, C.POINTER(P), P)
    descriptor = P(); w.require(a.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, C.byref(descriptor), None))
    w.bind(a, 'OpenProcessToken', T.BOOL, T.HANDLE, T.DWORD, C.POINTER(T.HANDLE))
    w.bind(a, 'LookupPrivilegeValueW', T.BOOL, T.LPCWSTR, T.LPCWSTR, C.POINTER(Luid))
    w.bind(a, 'AdjustTokenPrivileges', T.BOOL, T.HANDLE, T.BOOL, C.POINTER(Privileges), T.DWORD, C.POINTER(Privileges), C.POINTER(T.DWORD))
    w.bind(v, 'OpenVirtualDisk', T.DWORD, C.POINTER(StorageType), T.LPCWSTR, T.DWORD, T.DWORD, C.POINTER(OpenParameters), C.POINTER(T.HANDLE))
    w.bind(v, 'AttachVirtualDisk', T.DWORD, T.HANDLE, P, T.DWORD, T.DWORD, C.POINTER(AttachParameters), P)
    token, handle = T.HANDLE(), T.HANDLE()
    previous = Privileges(); changed = False
    try:
        w.require(a.OpenProcessToken(k.GetCurrentProcess(), 0x28, C.byref(token)))
        want = Privileges(); want.count = 1; want.attributes = 2
        w.require(a.LookupPrivilegeValueW(None, 'SeManageVolumePrivilege', C.byref(want.luid)))
        returned = T.DWORD(); C.set_last_error(0)
        w.require(a.AdjustTokenPrivileges(token, False, C.byref(want), C.sizeof(previous), C.byref(previous), C.byref(returned)))
        if C.get_last_error() == 1300:
            raise RuntimeError('Existing coordinator lacks volume-management privilege')
        changed = True
        storage = StorageType(2, Guid.from_buffer_copy(uuid.UUID('ec984aec-a0f9-47e9-901f-71415a66345b').bytes_le))
        opening = OpenParameters(); opening.version = 1; opening.data.depth = 1
        code = v.OpenVirtualDisk(C.byref(storage), str(image), 0xe0000, 0, C.byref(opening), C.byref(handle))
        if code: raise C.WinError(code)
        attaching = AttachParameters(); attaching.version = 1
        # Permanent lifetime + no drive letter: explicit retirement follows proof.
        code = v.AttachVirtualDisk(handle, descriptor, 6, 0, C.byref(attaching), None)
        if code: raise C.WinError(code)
        (ROOT / 'scratch/attach-result.json').write_text(json.dumps(dict(status='pass', profiles=profiles, device_sddl=sddl, backing_file_acl_modified=False))+'\n')
    finally:
        if handle: k.CloseHandle(handle)
        if changed: w.require(a.AdjustTokenPrivileges(token, False, C.byref(previous), 0, None, None))
        if token: k.CloseHandle(token)
        k.LocalFree(descriptor)


if __name__ == '__main__':
    main()
