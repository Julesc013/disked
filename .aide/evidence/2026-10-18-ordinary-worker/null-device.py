"""Guest-only null-sink compatibility for two exact disposable worker roles.

Reuse the separately tested bounded ACL codec/API delta implementation in an
isolated module instance. No arbitrary device, SID, mask, owner or label input.
"""
import base64
import ctypes as C
from ctypes import wintypes as T
import importlib.util
import json
import os
from pathlib import Path
import re

ROOT=Path('C:/ProgramData/DiskEd/qualification')
definition=importlib.util.spec_from_file_location('null_device_acl_api',ROOT/'crypto-device.py')
api=importlib.util.module_from_spec(definition);definition.loader.exec_module(api)
api.DEVICE='\\Device\\Null'
api.MASK=0x12019f  # FILE_GENERIC_READ | FILE_GENERIC_WRITE, no DELETE/WRITE_DAC/OWNER.


class Grant(api.Grant):
    def __init__(self,role,*,recovery=False):
        if role not in ('build','user'):raise ValueError('Exact declared null-sink role required')
        self.role=role;self.key='null_'+role
        super().__init__(recovery=recovery)
        try:
            self.before_label=self.label()
            if self.before_label!='S:AI(ML;;NW;;;LW)':raise ValueError('Unexpected null mandatory label; no label change permitted')
            self.report.update(role=role,mandatory_label=self.before_label)
        except BaseException:self.close();raise

    def read(self):
        data=super().read();result=dict(data)
        if self.role=='build':
            state=json.loads((ROOT/'scratch/state.json').read_bytes())
            attached=json.loads((ROOT/'scratch/attach-result.json').read_bytes())
            sid=state['profile_sids'][0]
            if state['nonce']!=data['nonce'] or sid!=attached['profiles'][0]['sid'] or not re.fullmatch(r'S-1-15-2-(?:[0-9]+-)*[0-9]+',sid):
                raise ValueError('Build package ownership mismatch')
            result['sid']=sid
        result.pop('crypto_device',None)
        if self.key in data:result['crypto_device']=data[self.key]
        return result

    def record(self,value):
        actual=super().read();selected=self.read()
        if selected['sid']!=self.sid_text or actual['nonce']!=self.data['nonce']:raise ValueError('Null subject ownership changed')
        actual[self.key]=value
        raw=(json.dumps(actual,indent=2)+'\n').encode()
        if len(raw)>65536:raise ValueError('Null journal bound')
        temporary=self.journal.with_name('ordinary-actor.'+actual['nonce']+'.'+self.key+'.tmp')
        with temporary.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,self.journal)

    def label(self):
        size=T.DWORD();self.n.NtQuerySecurityObject(self.device,0x10,None,0,C.byref(size))
        if not 0<size.value<=32768:raise ValueError('Null label bound')
        data=C.create_string_buffer(size.value)
        if self.n.NtQuerySecurityObject(self.device,0x10,data,size,C.byref(size))!=0:raise ValueError('Null label query')
        output=T.LPWSTR();api.require(self.a.ConvertSecurityDescriptorToStringSecurityDescriptorW(data,1,0x10,C.byref(output),None))
        try:return output.value
        finally:self.k.LocalFree(C.cast(output,api.P))

    def apply(self):
        before=self.snapshot()
        expected='(A;;0x1201bf;;;WD)(A;;FA;;;SY)(A;;FA;;;BA)(A;;0x1200a9;;;RC)'
        if before['sddl'].split('D:',1)[1]!=expected:raise ValueError('Unexpected baseline null DACL')
        self.record(dict(phase='prepared',device=api.DEVICE,subject=self.sid_text,mask=api.MASK,workers_started=False,
            before_sddl=before['sddl'],before_sha256=before['sha256'],mandatory_label=self.before_label,
            owned_ace_base64=base64.b64encode(api.owned_ace(self.sid_bytes)).decode('ascii')))
        after=self.update(before,api.add_subject(before['acl'],self.sid_bytes))
        if self.label()!=self.before_label:raise ValueError('Null mandatory label changed; preserve state')
        state=self.read()['crypto_device'];state['phase']='applied';self.record(state)
        self.report['events'].append(dict(action='applied',before_sddl=before['sddl'],after_sddl=after['sddl']))

    def retire(self,*,quiescent):
        super().retire(quiescent=quiescent)
        if self.label()!=self.before_label:raise ValueError('Null label retirement mismatch')


if __name__=='__main__':
    import sys
    if sys.argv[1:]!=['--build-apply-and-exit']:raise ValueError('Fixed prelaunch null-sink interruption only')
    instance=Grant('build');instance.apply();os._exit(19)
