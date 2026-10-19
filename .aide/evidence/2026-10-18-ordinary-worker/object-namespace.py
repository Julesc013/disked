"""Exact disposable-subject creation rights in one guest session directory.

Private qualification setup, not product code. Never alters a broad SID, label,
owner, parent directory or existing object's security. Reuses the bounded,
separately tested crypto ACL codec/API in an isolated module instance.
"""
import base64
import ctypes as C
from ctypes import wintypes as T
import importlib.util
import json
import os
from pathlib import Path

ROOT=Path('C:/ProgramData/DiskEd/qualification')
definition=importlib.util.spec_from_file_location('namespace_acl_api',Path(__file__).with_name('crypto-device.py'))
api=importlib.util.module_from_spec(definition);definition.loader.exec_module(api)
api.DEVICE='\\Sessions\\3\\BaseNamedObjects\\Restricted'
# Run77 observes Win32 requesting0xf on this directory. Query/traverse already
# exist; add only the two creation bits. No standard security/delete rights.
api.MASK=0xc
strict_aces=api.aces
api.aces=lambda raw:strict_aces(raw,allow_inherited=True)


class Grant(api.Grant):
    def __init__(self,*,recovery=False):
        if os.name!='nt':raise ValueError('Windows guest only')
        k=C.WinDLL('kernel32',use_last_error=True);session=T.DWORD()
        api.require(api.bind(k,'ProcessIdToSessionId',T.BOOL,T.DWORD,C.POINTER(T.DWORD))(os.getpid(),C.byref(session)))
        if session.value!=3:raise ValueError('Exact guest session3 coordinator required')
        super().__init__(recovery=recovery)
        try:
            self.before_label=self.label()
            if self.before_label!='S:AI(ML;;NW;;;LW)':raise ValueError('Unexpected namespace label; no label change')
            self.report.update(object_type='Directory',session_id=3,mandatory_label=self.before_label)
        except BaseException:self.close();raise

    def open_object(self,attrs,iosb):
        return api.bind(self.n,'NtOpenDirectoryObject',T.LONG,C.POINTER(T.HANDLE),T.DWORD,C.POINTER(api.Attributes))(
            C.byref(self.device),0x60003,C.byref(attrs))

    def read(self):
        actual=super().read();result=dict(actual);result.pop('crypto_device',None)
        if 'object_namespace' in actual:result['crypto_device']=actual['object_namespace']
        return result

    def record(self,value):
        actual=super().read()
        if actual['sid']!=self.sid_text or actual['nonce']!=self.data['nonce']:raise ValueError('Namespace journal ownership changed')
        actual['object_namespace']=value;raw=(json.dumps(actual,indent=2)+'\n').encode()
        if len(raw)>65536:raise ValueError('Namespace journal bound')
        temporary=self.journal.with_name('ordinary-actor.'+actual['nonce']+'.namespace.tmp')
        with temporary.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,self.journal)

    def label(self):
        size=T.DWORD();self.n.NtQuerySecurityObject(self.device,0x10,None,0,C.byref(size))
        if not 0<size.value<=32768:raise ValueError('Namespace label bound')
        data=C.create_string_buffer(size.value)
        if self.n.NtQuerySecurityObject(self.device,0x10,data,size,C.byref(size))!=0:raise ValueError('Namespace label query')
        output=T.LPWSTR();api.require(self.a.ConvertSecurityDescriptorToStringSecurityDescriptorW(data,1,0x10,C.byref(output),None))
        try:return output.value
        finally:self.k.LocalFree(C.cast(output,api.P))

    def apply(self):
        before=self.snapshot()
        expected='(A;;CCDC;;;WD)(A;;CCDCRC;;;RC)(A;;CCDCLCSWSDRCWDWO;;;S-1-5-90-0-3)(A;;CCDCLCSWSDRCWDWO;;;SY)'
        if before['sddl'].split('D:',1)[1]!=expected:raise ValueError('Unexpected exact session namespace baseline')
        self.record(dict(phase='prepared',device=api.DEVICE,subject=self.sid_text,mask=api.MASK,workers_started=False,
            before_sddl=before['sddl'],before_sha256=before['sha256'],mandatory_label=self.before_label,
            owned_ace_base64=base64.b64encode(api.owned_ace(self.sid_bytes)).decode('ascii')))
        after=self.update(before,api.add_subject(before['acl'],self.sid_bytes))
        if self.label()!=self.before_label:raise ValueError('Namespace label changed; preserve state')
        state=self.read()['crypto_device'];state['phase']='applied';self.record(state)
        self.report['events'].append(dict(action='applied',before_sddl=before['sddl'],after_sddl=after['sddl']))

    def retire(self,*,quiescent):
        super().retire(quiescent=quiescent)
        if self.label()!=self.before_label:raise ValueError('Namespace retirement label differs')


if __name__=='__main__':
    import sys
    if sys.argv[1:]!=['--apply-and-exit']:raise ValueError('Fixed prelaunch interruption only')
    instance=Grant()
    try:instance.apply()
    except BaseException:instance.retire(quiescent=True);instance.close();raise
    os._exit(19)
