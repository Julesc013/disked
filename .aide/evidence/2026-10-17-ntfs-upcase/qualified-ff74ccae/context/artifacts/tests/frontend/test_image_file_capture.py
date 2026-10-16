"""Ordinary generated-file capture controls; no mounts or physical-device opens."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import faulthandler
import json
import msvcrt
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import zlib

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'corpus'))
import partition_images as corpus

K=C.WinDLL('kernel32',use_last_error=True)
A=C.WinDLL('advapi32',use_last_error=True)
K.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,W.HANDLE];K.CreateFileW.restype=W.HANDLE
K.CloseHandle.argtypes=[W.HANDLE];K.CloseHandle.restype=W.BOOL
K.SetFilePointerEx.argtypes=[W.HANDLE,C.c_longlong,C.c_void_p,W.DWORD];K.SetFilePointerEx.restype=W.BOOL
K.SetEndOfFile.argtypes=[W.HANDLE];K.SetEndOfFile.restype=W.BOOL
K.DeviceIoControl.argtypes=[W.HANDLE,W.DWORD,C.c_void_p,W.DWORD,C.c_void_p,W.DWORD,C.POINTER(W.DWORD),C.c_void_p];K.DeviceIoControl.restype=W.BOOL
A.GetFileSecurityW.argtypes=[W.LPCWSTR,W.DWORD,C.c_void_p,W.DWORD,C.POINTER(W.DWORD)];A.GetFileSecurityW.restype=W.BOOL
A.SetFileSecurityW.argtypes=[W.LPCWSTR,W.DWORD,C.c_void_p];A.SetFileSecurityW.restype=W.BOOL
A.InitializeSecurityDescriptor.argtypes=[C.c_void_p,W.DWORD];A.InitializeSecurityDescriptor.restype=W.BOOL
A.InitializeAcl.argtypes=[C.c_void_p,W.DWORD,W.DWORD];A.InitializeAcl.restype=W.BOOL
A.SetSecurityDescriptorDacl.argtypes=[C.c_void_p,W.BOOL,C.c_void_p,W.BOOL];A.SetSecurityDescriptorDacl.restype=W.BOOL

def field(value,path):
    for part in path.split('.'):value=value[int(part)] if isinstance(value,list) else value[part]
    return value

def main():
    p=argparse.ArgumentParser();p.add_argument('--probe',required=True);p.add_argument('--fault',required=True)
    p.add_argument('--map-probe',required=True);p.add_argument('--evidence');args=p.parse_args()
    probes=[str(Path(x).resolve()) for x in [args.probe,args.fault,args.map_probe]];records=[]
    faulthandler.dump_traceback_later(60,repeat=True)
    env={k:v for k,v in os.environ.items() if not k.startswith('DISKED_IMAGE_TEST_')}
    def run(name,path,unit=512,refusal=None,fault=None,cwd=None):
        print('CASE '+ascii(name),flush=True)
        callenv=env.copy()
        if fault:callenv['DISKED_IMAGE_TEST_'+fault]='1'
        argv=[probes[1 if fault else 0],str(path),str(unit)]
        result=subprocess.run(argv,cwd=cwd,capture_output=True,env=callenv,timeout=20)
        assert result.returncode==(3 if refusal else 0),(name,result.returncode,result.stdout,result.stderr)
        value=json.loads(result.stdout)
        if refusal:assert value['refusal']==refusal,(name,value)
        else:
            assert len(result.stdout)<=320*1024+2
            receipt=value['report']['capture'];manifest=value['region_manifest']
            assert receipt['source_consistency']=='live-uncoordinated' and not receipt['atomic_snapshot'] and not receipt['whole_file_hashed']
            assert receipt['path']==str(path) and len(receipt['source_before']['file_id'])==32
            assert receipt['capture_epoch'].startswith('sha256:') and len(receipt['capture_epoch'])==71
            assert int(receipt['started_filetime'])>0 and int(receipt['finished_filetime'])>0 and int(receipt['elapsed_ms'])>=0
            assert int(receipt['requests'])<=517 and int(receipt['requested_bytes'])<=int(receipt['requested_bytes_with_reuse'])<=5*1024*1024
            assert int(receipt['unique_regions'])==len(manifest)
            assert int(receipt['captured_bytes'])==sum(int(x['bytes']) for x in manifest)
            assert int(receipt['requested_bytes'])==sum(int(x['end'])-int(x['start']) for x in manifest)
            assert int(receipt['omitted_regions'])==max(0,len(manifest)-8)
            assert receipt['regions']==manifest[:8]
            encoded=json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()
            assert receipt['region_manifest_sha256']==corpus.digest(encoded)
            assert 'selected' not in value['report'] and 'repair' not in value['report']
        records.append(dict(name=name,argv=argv,cwd=str(cwd) if cwd else str(Path.cwd()),fault=fault,
                            exit_code=result.returncode,output_sha256=corpus.digest(result.stdout)))
        return value
    scratch=Path.cwd()/'.aide-local';scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='disked-image-',dir=scratch) as tmp:
        root=Path(tmp)
        def ordinary(name,data,unit=512):
            path=root/(name+'.img');path.write_bytes(data);before=path.read_bytes()
            value=run(name,path,unit);receipt=value['report']['capture']
            assert path.read_bytes()==before,(name,'source changed')
            assert receipt['source_before']['bytes']==str(len(data)) and receipt['source_after']==receipt['source_before']
            assert receipt['observed_stable'] and receipt['metadata_equal'] and receipt['reread_equal'] and receipt['overlap_equal']
            assert receipt['partial_final_block']==bool(len(data)%unit)
            for r in value['region_manifest']:
                original=data[int(r['start']):int(r['end'])]
                assert r['bytes']==str(len(original)) and r['sha256']==corpus.digest(original)
                assert r['reread_sha256']==r['sha256'] and r['equal'] and r['read_error'] is None and r['reread_error'] is None
            blocks=(len(data)+unit-1)//unit
            process=subprocess.run([probes[2],str(blocks),str(unit)],input=data,capture_output=True,timeout=15)
            assert process.returncode==0,(name,process.stdout,process.stderr)
            parsed=json.loads(process.stdout);parsed.pop('capture');actual=value['report'].copy();actual.pop('capture')
            assert actual==parsed,(name,'region/prefix mismatch')
            return path,value
        for case in corpus.recipes():
            _,value=ordinary(case['name'],case['data'])
            if len(case['data'])>=256*512-1:
                for key,expected in case['checks'].items():assert field(value['report'],key)==expected,(case['name'],key)
        for size in [0,1,445,446,447,461,462,509,510,511,512,513,1023,1024,1030,1152,17407,17408]:
            _,value=ordinary('length-'+str(size),bytes(corpus.gpt())[:size]);receipt=value['report']['capture']
            if size==0:assert value['region_manifest']==[] and value['report']['mbr_status']==7
            if size%512:assert not receipt['regions_complete'] or size>1152
        data=bytes(corpus.gpt());wide=bytearray(256*4096);wide[:512]=data[:512]
        for my,array in [(1,2),(255,223)]:
            wide[my*4096:my*4096+512]=data[my*512:my*512+512]
            wide[array*4096:array*4096+16384]=data[array*512:array*512+16384]
        path,value=ordinary('wide-geometry',wide,4096);assert value['report']['comparison']==1
        literal,_=ordinary('--json',data);run('relative-literal-option',literal.name,cwd=root)
        duplicate=corpus.gpt();duplicate[:512]=corpus.table([corpus.mbr_entry(15,1,200)])
        _,value=ordinary('duplicate-request-reused',duplicate)
        assert value['report']['capture']['requests']=='6' and value['report']['capture']['unique_regions']=='5'
        # An eligible extended root lies inside the independently valid GPT array
        # region. These distinct requests actually overlap; an inconsistent GPT
        # header would be refused before its array and would not exercise this.
        overlap=corpus.gpt();overlap[:512]=corpus.table([corpus.mbr_entry(15,8,100)])
        overlap_path,value=ordinary('overlapping-regions',overlap);assert value['report']['capture']['overlap_equal']
        value=run('overlapping-capture-change',overlap_path,fault='OVERLAP_CHANGED')
        assert not value['report']['capture']['overlap_equal'] and not value['report']['capture']['observed_stable']
        unicode,_=ordinary('é-\U0001f4be',data);assert run('unicode-path',unicode)['report']['capture']['resolved_path']==str(unicode)
        # A large sparse ordinary file: the backup header/array are above 32-bit
        # byte offsets. Only required metadata regions may enter the capture.
        large=root/'large.img';blocks=(1<<24)+256;total=blocks*512
        with large.open('w+b') as f:
            got=W.DWORD();assert K.DeviceIoControl(msvcrt.get_osfhandle(f.fileno()),0x000900c4,None,0,None,0,C.byref(got),None),C.get_last_error()
            # The CRT truncate path can fill an extension with zeros despite
            # sparse marking. Extend the sparse fixture through Win32 directly.
            handle=msvcrt.get_osfhandle(f.fileno())
            assert K.SetFilePointerEx(handle,total,None,0) and K.SetEndOfFile(handle),C.get_last_error()
            assert K.SetFilePointerEx(handle,0,None,0),C.get_last_error()
            f.write(corpus.table([corpus.mbr_entry(0xee,1,blocks-1)]))
            rows=data[2*512:34*512]
            for my,alt,array in [(1,blocks-1,2),(blocks-1,1,blocks-33)]:
                h=bytearray(512);struct.pack_into('<8sIIIIQQQQ16sQIII',h,0,b'EFI PART',0x10000,92,0,0,my,alt,34,blocks-34,
                    corpus.DISK.bytes_le,array,128,128,zlib.crc32(rows));corpus.header_crc(h,0)
                f.seek(my*512);f.write(h);f.seek(array*512);f.write(rows)
        value=run('large-sparse-gpt',large);receipt=value['report']['capture']
        assert value['report']['comparison']==1 and receipt['source_before']['bytes']==str(total)
        assert receipt['unique_regions']=='5' and int(receipt['captured_bytes'])==3*512+2*16384
        assert any(int(x['start'])>(1<<32) for x in value['region_manifest'])
        with large.open('rb') as f:
            for r in value['region_manifest']:
                f.seek(int(r['start']));assert corpus.digest(f.read(int(r['bytes'])))==r['sha256']
        # Conventional open writers/exclusive readers conflict with read-only
        # source sharing. No real storage outside the generated fixture is used.
        for label,access,sharing in [('open-writer',0x40000000,7),('exclusive-reader',0x80000000,0)]:
            h=K.CreateFileW(str(literal),access,sharing,None,3,0,None);assert h not in [None,C.c_void_p(-1).value],C.get_last_error()
            try:value=run(label,literal,refusal='image_source_open');assert value['platform_code']=='32'
            finally:assert K.CloseHandle(h)
        alias=root/'hardlink.img';os.link(literal,alias)
        try:run('hardlink-alias',literal,refusal='image_file_aliases')
        finally:alias.unlink()
        run('directory',root,refusal='image_file_type')
        run('missing-file',root/'missing.img',refusal='image_source_open')
        # Actual owner-controlled DACL refusal; restore the exact old descriptor.
        needed=W.DWORD();A.GetFileSecurityW(str(literal),4,None,0,C.byref(needed));assert needed.value
        old=C.create_string_buffer(needed.value);assert A.GetFileSecurityW(str(literal),4,old,len(old),C.byref(needed))
        sd=C.create_string_buffer(64);acl=C.create_string_buffer(8)
        assert A.InitializeSecurityDescriptor(sd,1) and A.InitializeAcl(acl,8,2) and A.SetSecurityDescriptorDacl(sd,True,acl,False)
        assert A.SetFileSecurityW(str(literal),4,sd)
        try:value=run('access-denied',literal,refusal='image_source_open');assert value['platform_code']=='5'
        finally:assert A.SetFileSecurityW(str(literal),4,old)
        assert literal.read_bytes()==data
        # Junction construction is a local test fixture. It does not mount an
        # image and does not require symlink privilege or administrator execution.
        junction=root/'junction';cmd=os.environ['COMSPEC']
        made=subprocess.run([cmd,'/d','/c','mklink','/J',str(junction),str(root)],capture_output=True,timeout=10)
        assert made.returncode==0,(made.stdout,made.stderr)
        try:
            run('reparse-ancestor',junction/literal.name,refusal='image_reparse_source')
            run('reparse-final',junction,refusal='image_reparse_source')
        finally:junction.rmdir()
        for name,expected in [('READ_ERROR','read'),('SHORT_READ','short'),('CHANGED','change'),('VERIFY_ERROR','verify'),('METADATA_CHANGED','metadata')]:
            value=run('fault-'+expected,literal,fault=name);receipt=value['report']['capture']
            if name=='READ_ERROR':assert receipt['error_regions']=='1' and not receipt['observed_stable'] and value['report']['mbr']['issues']==256
            if name=='SHORT_READ':assert receipt['short_regions']=='1' and not receipt['observed_stable'] and value['report']['mbr']['issues']==256
            if name in ['CHANGED','VERIFY_ERROR']:assert not receipt['reread_equal'] and not receipt['observed_stable']
            if name=='METADATA_CHANGED':assert not receipt['metadata_equal'] and not receipt['observed_stable'] and receipt['reread_equal']
            assert literal.read_bytes()==data
        # Fault variables must have no effect in the ordinary library/probe.
        cleanenv=env.copy();cleanenv['DISKED_IMAGE_TEST_READ_ERROR']='1'
        result=subprocess.run([probes[0],str(literal),'512'],env=cleanenv,capture_output=True,timeout=15)
        assert result.returncode==0 and json.loads(result.stdout)['report']['capture']['observed_stable']
        records.append(dict(name='fault-unavailable-in-ordinary-probe',exit_code=0,output_sha256=corpus.digest(result.stdout)))
        for text in ['NUL','NUL .txt','CON.txt','PRN','AUX','COM1.img','LPT9.img','COM¹.img','CONIN$','CONOUT$',
                     'bad:stream','bad?name','bad*name','bad|name','bad"name','bad\x1bname','bad\x7fname','trailing.','trailing ',
                     'C:relative.img','\\rooted.img','//unavailable-share/image.img','\\\\?\\C:\\sample.img','x'*241]:
            run('path-refusal-'+repr(text),text,refusal='image_path_profile',fault='OPEN_GUARD')
        for unit in [0,1024,8192]:run('unit-refusal-'+str(unit),literal,unit,refusal='image_geometry',fault='OPEN_GUARD')
        run('open-guard-positive-control',literal,refusal='image_test_open_guard',fault='OPEN_GUARD')
    result=dict(schema='org.disked.image-file-capture-tests/1',passed=True,cases=len(records),records=records)
    faulthandler.cancel_dump_traceback_later()
    if args.evidence:Path(args.evidence).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(passed=True,cases=len(records))))

if __name__=='__main__':main()
