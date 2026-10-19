"""Bounded read-only analysis of the guest's exact failed DLL entry routine.

Binary-analysis evidence, not a clean-room claim or a product dependency.
The managed host workspace holds the disposable DLL copy; no DLL is executed.
"""
import base64
import hashlib
import json
import lzma
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
work=Path(os.environ['DISKED_WORK_ROOT'])
script=r'''
$ErrorActionPreference='Stop'
$session=& .\tools\connect-vm.ps1 -OpenSession
try {
    $before=Invoke-Command -Session $session -ScriptBlock {
        if([Security.Principal.WindowsIdentity]::GetCurrent().Name-ne'BLACKGLASS-HYPE\Agents'-or[IntPtr]::Size-ne8){throw 'Wrong guest identity/architecture.'}
        $path='C:\Windows\System32\KernelBase.dll'
        $file=Get-Item -LiteralPath $path
        if($file.Length-gt4MB){throw 'DLL exceeds analysis input bound.'}
        $module=[Diagnostics.Process]::GetCurrentProcess().Modules|Where-Object ModuleName -ieq 'kernelbase.dll'
        if(@($module).Count-ne1){throw 'KernelBase identity unresolved.'}
        @{sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLower();bytes=$file.Length;version=$file.VersionInfo.FileVersion;loaded_base=('0x{0:x}'-f$module.BaseAddress.ToInt64());guest=$env:COMPUTERNAME;path=$path}
    }
    Copy-Item -FromSession $session -LiteralPath 'C:\Windows\System32\KernelBase.dll' -Destination (Join-Path $env:DISKED_WORK_ROOT 'KernelBase.dll')
    $after=Invoke-Command -Session $session -ScriptBlock {(Get-FileHash -LiteralPath 'C:\Windows\System32\KernelBase.dll' -Algorithm SHA256).Hash.ToLower()}
    if($after-ne$before.sha256){throw 'Guest DLL changed during observation.'}
    $before|ConvertTo-Json -Compress
} finally {Remove-PSSession -Session $session}
'''
call=subprocess.run(['pwsh','-NoProfile','-Command',script],cwd=ROOT,capture_output=True,timeout=60)
if call.returncode:raise RuntimeError(call.stderr[-4096:].decode(errors='replace'))
meta=json.loads(call.stdout);image=work/'KernelBase.dll';raw=image.read_bytes()
assert len(raw)==meta['bytes']<=4194304 and hashlib.sha256(raw).hexdigest()==meta['sha256']
record=json.loads((HERE/'twenty-first-error-reporting.json').read_bytes())
v=record['guest']['proof']['debug']['variants'][1]
trace=lzma.decompress(base64.b64decode(v['trace']['xz_base64']))
assert hashlib.sha256(trace).hexdigest()==v['trace']['sha256']
match=re.search(rb'Init routine ([0-9A-Fa-f]+) for DLL "C:\\Windows\\System32\\KERNELBASE.dll" failed during DLL_PROCESS_ATTACH',trace)
assert match
entry=int(match[1],16)-int(meta['loaded_base'],16)
u16=lambda at:struct.unpack_from('<H',raw,at)[0]
u32=lambda at:struct.unpack_from('<I',raw,at)[0]
u64=lambda at:struct.unpack_from('<Q',raw,at)[0]
pe=u32(60);assert raw[pe:pe+4]==b'PE\0\0' and u16(pe+4)==0x8664
optional=pe+24;assert u16(optional)==0x20b
base=u64(optional+24);section_start=optional+u16(pe+20)
sections=[]
for i in range(u16(pe+6)):
    at=section_start+40*i
    sections.append((u32(at+12),u32(at+16),u32(at+20)))
def offset(rva,size):
    for start,length,position in sections:
        if start<=rva and rva+size<=start+length:return position+rva-start
    raise ValueError('RVA outside supplied section bytes')
pdata_rva,pdata_size=struct.unpack_from('<II',raw,optional+112+24)
assert pdata_size%12==0
pdata=offset(pdata_rva,pdata_size);bounds=[]
for at in range(pdata,pdata+pdata_size,12):
    start,end,_=struct.unpack_from('<III',raw,at)
    if start<=entry<end:bounds.append((start,end))
assert len(bounds)==1
start,end=bounds[0];assert 0<end-start<=16384
objdump=shutil.which('objdump');assert objdump
command=[objdump,'-d','-Mintel','--start-address='+hex(base+start),'--stop-address='+hex(base+end),str(image)]
disassembly=subprocess.run(command,capture_output=True,timeout=30)
assert disassembly.returncode==0 and len(disassembly.stdout)<=524288
output=disassembly.stdout
compressed=lzma.compress(output,filters=[dict(id=lzma.FILTER_LZMA2,preset=9|lzma.PRESET_EXTREME,dict_size=2097152)])
assert len(compressed)<=131072 and lzma.decompress(compressed)==output
result=dict(scope='Read-only Windows binary analysis; no product or clean-room claim',input=meta,init_rva=hex(entry),runtime_function_rva=[hex(start),hex(end)],tool_path=objdump,tool_sha256=hashlib.sha256(Path(objdump).read_bytes()).hexdigest(),tool_version=subprocess.check_output([objdump,'--version']).decode(errors='replace').splitlines()[0],disassembly=dict(bytes=len(output),sha256=hashlib.sha256(output).hexdigest(),xz_sha256=hashlib.sha256(compressed).hexdigest(),xz_base64=base64.b64encode(compressed).decode('ascii')))
# These direct/tail callees come from the observed entry routine, and are
# deliberately bound to this one exact Windows DLL rather than a public ABI.
assert meta['sha256']=='c5e318c29e2bb032b21d981d3c130f0645c37b4330f5ef9659456452b2d0f00c'
result['followups']=[]
for selected in (0x49670,0x496e4,0x7c90,0x4a6ec):
    found=[]
    for at in range(pdata,pdata+pdata_size,12):
        left,right,_=struct.unpack_from('<III',raw,at)
        if left<=selected<right:found.append((left,right))
    assert len(found)==1
    left,right=found[0];assert 0<right-left<=16384
    follow=subprocess.run([objdump,'-d','-Mintel','--start-address='+hex(base+left),'--stop-address='+hex(base+right),str(image)],capture_output=True,timeout=30)
    assert follow.returncode==0 and len(follow.stdout)<=524288
    packed=lzma.compress(follow.stdout,filters=[dict(id=lzma.FILTER_LZMA2,preset=9|lzma.PRESET_EXTREME,dict_size=2097152)])
    assert len(packed)<=131072 and lzma.decompress(packed)==follow.stdout
    result['followups'].append(dict(selected_rva=hex(selected),runtime_function_rva=[hex(left),hex(right)],bytes=len(follow.stdout),sha256=hashlib.sha256(follow.stdout).hexdigest(),xz_base64=base64.b64encode(packed).decode('ascii')))
def string(rva):
    at=offset(rva,1);end=raw.index(b'\0',at,at+256);return raw[at:end].decode('ascii')
imports={};descriptor=offset(u32(optional+112+8),20)
for index in range(128):
    original,_,_,module,thunk=struct.unpack_from('<IIIII',raw,descriptor+20*index)
    if not any((original,module,thunk)):break
    dll=string(module)
    for j in range(4096):
        value=u64(offset((original or thunk)+8*j,8))
        if not value:break
        imports[base+thunk+8*j]=dll+'!'+('ordinal'+str(value&65535) if value>>63 else string(value+2))
    else:raise ValueError('Import thunk bound')
else:raise ValueError('Import descriptor bound')
for item in [result['disassembly']]+result['followups']:
    text=lzma.decompress(base64.b64decode(item['xz_base64']))
    referenced={int(value,16) for value in re.findall(rb'# 0x([a-f0-9]+)',text)}
    item['referenced_imports']={hex(address):imports[address] for address in referenced if address in imports}
(HERE/'kernelbase-stage600-static.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(input=meta,init_rva=hex(entry),runtime_function_rva=result['runtime_function_rva'],output_bytes=len(output),compressed_bytes=len(compressed))))
