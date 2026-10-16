"""Independent synthetic GPT/encoding oracle; no device or mounted-image access."""
import argparse
import copy
import hashlib
import json
import random
import struct
import subprocess
import unittest
import uuid
import zlib
from pathlib import Path

TRUNCATED,SIGNATURE,REVISION,HEADER_SIZE,HEADER_CRC,RESERVED=1,2,4,8,16,32
LOCATION,USABLE,ARRAY_SHAPE,ARRAY_RANGE,ARRAY_CRC,ENTRY_RANGE=64,128,256,512,1024,2048
OVERLAP,DUPLICATE,ZERO_GUID,NAME_UTF16,NAME_TERM,UNUSED=4096,8192,16384,32768,65536,131072
DISK=uuid.UUID('12345678-9abc-4def-8123-456789abcdef')
TYPE=uuid.UUID('ebd0a0a2-b9e5-4433-87c0-68b6b72699c7')


def entry(first,last,identity=1,name='Disk',attributes=0,size=128):
    out=bytearray(size);out[:16]=TYPE.bytes_le;out[16:32]=uuid.UUID(int=identity).bytes_le
    struct.pack_into('<QQQ',out,32,first,last,attributes)
    encoded=name.encode('utf-16-le');assert len(encoded)<=72
    out[56:56+len(encoded)]=encoded
    return out


def header(unit,my,alternate,first,last,array_lba,count,size,array_crc,disk=DISK):
    out=bytearray(unit)
    struct.pack_into('<8sIIIIQQQQ16sQIII',out,0,b'EFI PART',0x10000,92,0,0,my,alternate,first,last,disk.bytes_le,array_lba,count,size,array_crc)
    fix_header(out);return out


def fix_header(data):
    struct.pack_into('<I',data,16,0)
    size=struct.unpack_from('<I',data,12)[0]
    struct.pack_into('<I',data,16,zlib.crc32(data[:size]))


def fixture(blocks=100,unit=512,count=4,size=128,entries=None):
    span=(count*size+unit-1)//unit;reserve=max(span,(16384+unit-1)//unit)
    first=2+reserve;last=blocks-2-reserve
    assert first<=last
    raw=bytearray(span*unit)
    if entries is None:entries=[entry(first,min(first+4,last),size=size)]
    for i,row in enumerate(entries):assert len(row)==size;raw[i*size:(i+1)*size]=row
    crc=zlib.crc32(raw[:count*size])
    return dict(blocks=str(blocks),unit=str(unit),max_entries='1024',max_entry_size='4096',max_bytes='1048576',
                primary=header(unit,1,blocks-1,first,last,2,count,size,crc).hex(),
                backup=header(unit,blocks-1,1,first,last,blocks-1-span,count,size,crc).hex(),
                primary_array=raw.hex(),backup_array=raw.hex())


def change_header(value,offset,fmt,number,side='primary',repair_crc=True):
    data=bytearray.fromhex(value[side]);struct.pack_into(fmt,data,offset,number)
    if repair_crc:fix_header(data)
    value[side]=data.hex()


def change_array(value,mutate,side='primary',repair_crc=True):
    data=bytearray.fromhex(value[side+'_array']);mutate(data);value[side+'_array']=data.hex()
    if repair_crc:
        h=bytes.fromhex(value[side]);count,size=struct.unpack_from('<II',h,80)
        change_header(value,88,'<I',zlib.crc32(data[:count*size]),side)


def equal_crc_patch(data,offset,target):
    """Solve a four-byte CRC patch over GF(2), solely to challenge CRC-only comparison."""
    data[offset:offset+4]=b'\0'*4;base=zlib.crc32(data);basis={}
    for bit in range(32):
        candidate=bytearray(data);candidate[offset+bit//8]^=1<<(bit%8)
        v=zlib.crc32(candidate)^base;mask=1<<bit
        while v:
            pivot=v.bit_length()-1
            if pivot not in basis:basis[pivot]=(v,mask);break
            v^=basis[pivot][0];mask^=basis[pivot][1]
    delta=target^base;mask=0
    while delta:
        pivot=delta.bit_length()-1;delta^=basis[pivot][0];mask^=basis[pivot][1]
    data[offset:offset+4]=mask.to_bytes(4,'little');assert zlib.crc32(data)==target


def corpus():
    cases=[]
    def add(name,value,**expected):cases.append(dict(name=name,input=copy.deepcopy(value),expected=expected))
    add('valid-pair',fixture(),comparison=1,header_issues=0,array_issues=0)
    add('empty-pair',fixture(entries=[]),comparison=1,array_issues=0)
    for unit in (520,4096,1048576):add('unit-'+str(unit),fixture(unit=unit),comparison=1,array_issues=0)
    for count,size in ((1,128),(3,128),(128,128),(1024,128),(4,256),(256,4096)):
        add('array-shape-'+str(count)+'-'+str(size),fixture(blocks=10000,count=count,size=size),comparison=1,array_issues=0)
    f=fixture();change_array(f,lambda a:struct.pack_into('<Q',a,48,1<<63),'backup')
    add('valid-disagree-attributes',f,comparison=2,array_issues=0,backup_array_issues=0)
    f=fixture();change_header(f,56,'<I',0x99887766,'backup')
    add('valid-disagree-disk-guid',f,comparison=2,header_issues=0,backup_header_issues=0)
    f=fixture();change_header(f,40,'<Q',35,'backup');change_array(f,lambda a:struct.pack_into('<Q',a,32,35),'backup')
    add('valid-disagree-usable',f,comparison=2)
    f=fixture();change_header(f,12,'<I',128,'backup')
    add('valid-disagree-header-size',f,comparison=2)
    f=fixture();other=fixture(count=2,size=256)
    f['backup']=other['backup'];f['backup_array']=other['backup_array']
    assert f['primary_array']==f['backup_array']
    add('same-bytes-different-entry-shape',f,comparison=2,array_issues=0,backup_array_issues=0)
    f=fixture();original=bytes.fromhex(f['primary_array']);other=bytearray(original);other[16]^=8
    equal_crc_patch(other,124,zlib.crc32(original));assert other!=original
    f['backup_array']=other.hex()
    add('same-crc-different-valid-bytes',f,comparison=2,array_issues=0,backup_array_issues=0)
    f=fixture();f['separate_space']=True;add('equal-name-separate-space',f,comparison=0)
    f=fixture();change_header(f,16,'<I',0,repair_crc=False)
    add('primary-crc-fails-backup-independent',f,comparison=0,header_issues=HEADER_CRC,backup_header_issues=0,backup_array_issues=0)
    f=fixture();change_header(f,16,'<I',0,'backup',False)
    add('backup-crc-fails-primary-independent',f,comparison=0,header_issues=0,array_issues=0,backup_header_issues=HEADER_CRC)
    for offset,fmt,n,flag in [(8,'<I',0x20000,REVISION),(12,'<I',91,HEADER_SIZE),(12,'<I',513,HEADER_SIZE),
                             (20,'<I',1,RESERVED),(24,'<Q',2,LOCATION),(32,'<Q',1,LOCATION),
                             (40,'<Q',33,USABLE),(48,'<Q',67,USABLE),(80,'<I',0,ARRAY_SHAPE),
                             (84,'<I',96,ARRAY_SHAPE),(72,'<Q',1,ARRAY_RANGE),
                             (72,'<Q',99,ARRAY_RANGE),(88,'<I',0,0)]:
        f=fixture();change_header(f,offset,fmt,n)
        if offset==88:add('array-crc-mismatch',f,header_issues=0,array_issues=ARRAY_CRC,comparison=0)
        else:add('header-field-'+str(offset)+'-'+str(n),f,header_has=flag,comparison=0)
    f=fixture();change_header(f,56,'<16s',b'\0'*16);add('zero-disk-guid',f,header_issues=ZERO_GUID,comparison=0)
    f=fixture();data=bytearray.fromhex(f['primary']);data[0]=0;f['primary']=data.hex()
    add('signature-not-interpreted',f,header_issues=SIGNATURE,comparison=0)
    for n in (0,1,91,92,509,511):
        f=fixture();f['primary']=f['primary'][:n*2];add('short-header-'+str(n),f,header_issues=TRUNCATED,comparison=0)
    f=fixture();f['primary']+='00';add('oversized-header',f,primary_status=7)
    for offset in (92,200,511):
        f=fixture();data=bytearray.fromhex(f['primary']);data[offset]=1;f['primary']=data.hex()
        add('reserved-header-'+str(offset),f,header_issues=RESERVED,comparison=0)
    for n in (0,1,127,128,511):
        f=fixture();f['primary_array']=f['primary_array'][:n*2]
        add('short-array-'+str(n),f,array_issues=TRUNCATED,complete=False,comparison=0)
    f=fixture();f['primary_array']+='00';add('oversized-array',f,array_status=7,comparison=0)
    f=fixture(count=3);change_array(f,lambda a:a.__setitem__(400,1),repair_crc=False)
    add('padding-outside-crc',f,array_issues=RESERVED,comparison=0)
    for label,mutator,flag in [
        ('inclusive-below',lambda a:struct.pack_into('<Q',a,32,33),ENTRY_RANGE),
        ('inclusive-above',lambda a:struct.pack_into('<Q',a,40,67),ENTRY_RANGE),
        ('reversed',lambda a:struct.pack_into('<QQ',a,32,40,39),ENTRY_RANGE),
        ('u64-end-overflow',lambda a:struct.pack_into('<QQ',a,32,34,(1<<64)-1),ENTRY_RANGE),
        ('zero-unique',lambda a:a.__setitem__(slice(16,32),b'\0'*16),ZERO_GUID),
        ('reserved-attribute',lambda a:struct.pack_into('<Q',a,48,8),RESERVED),
        ('isolated-high-surrogate',lambda a:a.__setitem__(slice(56,60),b'\0\xd8\0\0'),NAME_UTF16),
        ('isolated-low-surrogate',lambda a:a.__setitem__(slice(56,60),b'\0\xdc\0\0'),NAME_UTF16),
        ('missing-terminator',lambda a:a.__setitem__(slice(56,128),'A'.encode('utf-16-le')*36),NAME_TERM),
        ('inactive-residual',lambda a:a.__setitem__(slice(0,16),b'\0'*16),UNUSED)]:
        f=fixture();change_array(f,mutator);add(label,f,array_issues=flag,comparison=0)
    f=fixture(size=256);change_array(f,lambda a:a.__setitem__(200,1));add('extended-entry-reserved',f,array_issues=RESERVED,comparison=0)
    f=fixture(entries=[entry(34,38,1),entry(39,44,2)]);add('adjacent',f,array_issues=0,comparison=1)
    f=fixture(entries=[entry(34,39,1),entry(39,44,2)]);add('overlap',f,array_issues=OVERLAP,comparison=0)
    f=fixture(entries=[entry(34,38,1),entry(39,44,1)]);add('duplicate-guid',f,array_issues=DUPLICATE,comparison=0)
    for field,value in [('max_entries','3'),('max_entry_size','128'),('max_bytes','511')]:
        f=fixture(size=256) if field=='max_entry_size' else fixture();f[field]=value
        add('budget-'+field,f,request_status=3,comparison=0)
    for field,value in [('max_entries','0'),('max_entries','1025'),('max_entry_size','129'),('max_bytes','0'),('max_bytes','1048577')]:
        f=fixture();f[field]=value;add('invalid-budget-'+field+'-'+value,f,request_status=1,comparison=0)
    # Symbolic huge geometry tests the u64 product/range before any array read.
    n=(1<<64)-1;count=0xffffffff;size=0x80000000;span=(count*size+511)//512
    f=fixture();f.update(blocks=str(n),primary=header(512,1,n-1,2+span,n-2-span,2,count,size,0).hex(),
        backup=header(512,n-1,1,2+span,n-2-span,n-1-span,count,size,0).hex(),primary_array='',backup_array='')
    add('large-product-budget-before-read',f,header_issues=0,backup_header_issues=0,request_status=3,comparison=0)
    change_header(f,72,'<Q',n-5)
    add('array-end-overflow',copy.deepcopy(f),header_has=ARRAY_RANGE,comparison=0)
    rng=random.Random(220022)
    for i in range(120):
        unit=rng.choice([512,520,4096]);count=rng.randint(1,16);size=rng.choice([128,256,512])
        reserve=max((count*size+unit-1)//unit,(16384+unit-1)//unit);first=2+reserve
        rows=[entry(first+3*j,first+3*j+rng.randrange(3),j+1,name='D'+chr(0x400+j),size=size,attributes=(j<<48)) for j in range(count)]
        add('generated-'+str(i),fixture(blocks=500,unit=unit,count=count,size=size,entries=rows),comparison=1,array_issues=0)
    add('maximum-active-entry-workspace',fixture(blocks=10000,count=1024,entries=[entry(258+3*j,258+3*j,j+1) for j in range(1024)]),comparison=1,array_issues=0)
    for i in range(500):
        f=fixture();key=rng.choice(['primary','backup','primary_array','backup_array']);data=bytearray.fromhex(f[key])
        for _ in range(rng.randint(1,8)):data[rng.randrange(len(data))]=rng.randrange(256)
        if i%9==0:data=data[:rng.randrange(len(data))]
        f[key]=data.hex();add('mutation-'+str(i),f)
    for payload in [b'',b'123456789',bytes(range(256)),b'\xff'*16384]+[rng.randbytes(rng.randrange(0,4096)) for _ in range(200)]:
        expect=dict(crc=zlib.crc32(payload));
        if len(payload)==16:expect['guid']=str(uuid.UUID(bytes_le=payload))
        add('crc-'+str(len(cases)),dict(encoding=payload.hex()),encoding=expect)
    for i in range(100):
        data=rng.randbytes(16);add('guid-'+str(i),dict(encoding=data.hex()),encoding=dict(crc=zlib.crc32(data),guid=str(uuid.UUID(bytes_le=data))))
    for label in ['', 'Disk', '\u03b1\u6f22', '\U0001f4be', 'A\x1b\n', 'Z'*35, '\u0800'*35, '\U0001f4be'*17, 'Q'*36]:
        data=label.encode('utf-16-le').ljust(72,b'\0');expected=dict(crc=zlib.crc32(data),status=0,name=label,terminated=len(data.rstrip(b'\0'))<72 if label else True)
        expected['terminated']=len(label.encode('utf-16-le'))<72
        add('name-'+str(len(cases)),dict(encoding=data.hex()),encoding=expected)
        need=len(label.encode('utf-8'))+1
        if need>1:add('name-small-buffer-'+str(len(cases)),dict(encoding=data.hex(),capacity=str(need-1)),encoding=dict(crc=zlib.crc32(data),status=3))
    for data in [b'\0\xd8'+b'\0'*70,b'\0\xdc'+b'\0'*70,b'A\0'*35+b'\0\xd8']:
        add('invalid-name-'+str(len(cases)),dict(encoding=data.hex()),encoding=dict(crc=zlib.crc32(data),status=1))
    add('empty-name-zero-capacity',dict(encoding=(b'\0'*72).hex(),capacity='0'),encoding=dict(crc=zlib.crc32(b'\0'*72),status=3))
    return cases


class Gpt(unittest.TestCase):
    def test_synthetic_and_encoding_cases(self):
        global RECORDS
        cases=corpus();records=[]
        for start in range(0,len(cases),8):
            batch=cases[start:start+8];wire=''.join(json.dumps(c['input'],separators=(',',':'))+'\n' for c in batch)
            result=subprocess.run([ARGS.probe],input=wire,text=True,encoding='utf-8',capture_output=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr);outs=[json.loads(x) for x in result.stdout.splitlines()]
            self.assertEqual(len(outs),len(batch))
            for case,out in zip(batch,outs):
                with self.subTest(case=case['name']):
                    expected=case['expected'];inp=case['input']
                    if 'encoding' in inp:
                        for key,value in expected['encoding'].items():self.assertEqual(out[key],value,key)
                    else:
                        copies=out['copies'];primary=copies[0];backup=copies[1]
                        self.assertEqual(primary['status'],expected.get('primary_status',0))
                        if 'comparison' in expected:self.assertEqual(out['comparison'],expected['comparison'])
                        for prefix,value in [('',primary),('backup_',backup)]:
                            if value['status']:continue
                            h=value['header'];self.assertEqual(h['raw'],inp['backup' if prefix else 'primary'])
                            if prefix+'header_issues' in expected:self.assertEqual(h['issues'],expected[prefix+'header_issues'])
                            if prefix+'header_has' in expected:self.assertEqual(h['issues']&expected[prefix+'header_has'],expected[prefix+'header_has'])
                            if prefix+'request_status' in expected:self.assertEqual(value['request_status'],expected[prefix+'request_status'])
                            if 'array_status' in value and prefix+'array_status' in expected:self.assertEqual(value['array_status'],expected[prefix+'array_status'])
                            if value.get('array_status',1)==0:
                                c=value['candidate'];self.assertEqual(c['raw'],inp[('backup' if prefix else 'primary')+'_array'])
                                if prefix+'array_issues' in expected:self.assertEqual(c['issues'],expected[prefix+'array_issues'])
                                if prefix+'complete' in expected:self.assertEqual(c['complete'],expected[prefix+'complete'])
                                for n,e in enumerate(c['entries']):
                                    self.assertEqual(e['raw'],c['raw'][2*n*h['entry_size']:2*(n+1)*h['entry_size']])
                                    if e['range_valid']:self.assertTrue(int(h['first'])<=int(e['first'])<int(e['end'])<=int(h['last'])+1)
                                    if e['active']:
                                        raw=bytes.fromhex(e['raw']);self.assertEqual(e['type_guid'],str(uuid.UUID(bytes_le=raw[:16])))
                                        self.assertEqual(e['unique_guid'],str(uuid.UUID(bytes_le=raw[16:32])))
                                        units=struct.unpack('<36H',raw[56:128]);end=units.index(0) if 0 in units else 36
                                        try:name=raw[56:56+end*2].decode('utf-16-le')
                                        except UnicodeDecodeError:self.assertEqual(e['name_status'],1)
                                        else:self.assertEqual(e['name'],name)
                    records.append(dict(name=case['name'],input_sha256=hashlib.sha256(json.dumps(inp,sort_keys=True).encode()).hexdigest(),output_sha256=hashlib.sha256(json.dumps(out,sort_keys=True).encode()).hexdigest(),expected=expected))
        RECORDS=records;print('Checked',len(cases),'synthetic GPT/encoding cases.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--probe',required=True);p.add_argument('--evidence');ARGS=p.parse_args();RECORDS=[]
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Gpt))
    if ARGS.evidence:Path(ARGS.evidence).write_text(json.dumps(dict(cases=len(RECORDS),passed=result.wasSuccessful(),observations=RECORDS),indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
