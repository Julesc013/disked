"""Independent exFAT byte/integer/checksum oracle; supplied metadata only."""
import argparse,hashlib,json,random,struct,subprocess,unittest
from pathlib import Path
PROBE=None;RECORDS=[]
U64=(1<<64)-1;MAX=(1<<32)-11
ISS=dict(truncated=1,signature=2,name=4,zero=8,sector=16,cluster=32,revision=64,flags=128,
 percent=256,regions=512,counters=1024,table=2048,root=4096,capacity=8192,overflow=16384,
 checksum=32768,extended=65536,reserved=131072)
def checksum(raw,unit):
 value=0
 for index,byte in enumerate(raw[:unit*11]):
  if index in (106,107,112):continue
  value=((value//2)+(value%2)*(1<<31)+byte)&0xffffffff
 return value
def seal(raw):
 unit=1<<raw[108];value=checksum(raw,unit)
 raw[unit*11:unit*12]=struct.pack('<I',value)*(unit//4)
 return raw
def boot(shift=9,cluster_shift=0,clusters=4096,copies=1,trailing=0):
 unit=1<<shift;fat=((clusters+2)*4+unit-1)//unit;heap=24+fat*copies
 volume=heap+clusters*(1<<cluster_shift)+trailing
 raw=bytearray(unit*12);raw[:11]=b'\xeb\x76\x90EXFAT   '
 struct.pack_into('<QQIIIIIIHHBBBBB',raw,64,0,volume,24,fat,heap,clusters,2,0x12345678,0x100,0,shift,cluster_shift,copies,0x80,255)
 raw[510:512]=b'\x55\xaa'
 for i in range(1,9):struct.pack_into('<I',raw,(i+1)*unit-4,0xaa550000)
 return seal(raw),volume*unit
def request(raw,available,backup=0):return dict(op='boot',bytes=bytes(raw).hex(),available=str(available),backup=str(backup))
def oracle(raw,available,backup):
 if len(raw)>49152:return dict(status=7)
 if backup not in (0,1):return dict(status=1)
 if len(raw)<512:return dict(status=0,issues=1,usable_geometry=False,fields_present=False,active_fat_known=False)
 issues=0
 part,volume,fat_offset,fat_length,heap,clusters,root,serial,revision,flags=struct.unpack_from('<QQIIIIIIHH',raw,64)
 shift,cs,copies,drive,percent=raw[108:113]
 if raw[:3]!=b'\xeb\x76\x90' or raw[510:512]!=b'\x55\xaa':issues|=2
 if raw[3:11]!=b'EXFAT   ':issues|=4
 if any(raw[11:64]):issues|=8
 if any(raw[113:120]):issues|=131072
 if revision!=0x100:issues|=64
 if flags&~15 or copies==1 and flags&1:issues|=128
 if percent>100 and percent!=255:issues|=256
 if copies not in (1,2):issues|=512
 out=dict(status=0,partition_offset=str(part),volume_sectors=str(volume),fat_offset=fat_offset,fat_length=fat_length,
 heap_offset=heap,cluster_count=clusters,root_cluster=root,serial=serial,revision=revision,flags=flags,
 sector_shift=shift,cluster_shift=cs,fat_count=copies,drive_select=drive,percent_in_use=percent,
 fields_present=True,backup=bool(backup),mutable_fields_stale=bool(backup),texfat_structure=copies==2,active_fat=flags&1)
 if shift<9 or shift>12:out.update(issues=issues|16,usable_geometry=False,active_fat_known=False);return out
 unit=1<<shift
 if len(raw)>12*unit:return dict(status=7)
 out['sector_bytes']=unit;out['complete_region']=len(raw)==12*unit
 if len(raw)<12*unit:issues|=1
 else:
  calculated=checksum(raw,unit);words=struct.unpack_from('<'+'I'*(unit//4),raw,11*unit)
  mismatch=sum(w!=calculated for w in words);out.update(checksum=calculated,checksum_word=words[0],checksum_mismatches=mismatch,checksum_valid=mismatch==0)
  if mismatch:issues|=32768
  if any(struct.unpack_from('<I',raw,(i+1)*unit-4)[0]!=0xaa550000 for i in range(1,9)):issues|=65536
  if any(raw[10*unit:11*unit]):issues|=131072
 if cs>25-shift:out.update(issues=issues|32,usable_geometry=False,active_fat_known=False);return out
 size=1<<cs;volume_bytes=volume*unit
 out.update(cluster_sectors=size,cluster_bytes=unit*size,fat_bytes=str(fat_length*unit),heap_offset_bytes=str(heap*unit),heap_bytes=str(clusters*unit*size))
 if volume_bytes>U64:issues|=16384;out['volume_bytes']='0'
 else:
  out['volume_bytes']=str(volume_bytes)
  if volume_bytes>available:issues|=8192
 if volume<1048576//unit:issues|=1024
 if fat_offset<24 or fat_length==0 or fat_offset+fat_length*copies>heap or heap>=volume:issues|=512
 if not 1<=clusters<=MAX:issues|=1024
 elif fat_length*unit<(clusters+2)*4:issues|=2048
 if heap<volume and clusters!=min((volume-heap)//size,MAX):issues|=1024
 if root<2 or clusters>MAX or root>clusters+1:issues|=4096
 out.update(issues=issues,usable_geometry=issues==0,active_fat_known=issues==0 and not backup)
 return out
def run(rows):
 encoded=json.dumps(rows,separators=(',',':')).encode();result=subprocess.run([str(PROBE)],input=encoded,capture_output=True,timeout=25)
 assert result.returncode==0 and not result.stderr,(result.returncode,result.stderr)
 values=json.loads(result.stdout);assert len(values)==len(rows)
 RECORDS.append(dict(input_sha256='sha256:'+hashlib.sha256(encoded).hexdigest(),cases=len(rows),exit_code=result.returncode))
 return values
class ExfatTests(unittest.TestCase):
 def check(self,rows):
  values=run(rows)
  for inp,out in zip(rows,values):
   expected=oracle(bytes.fromhex(inp['bytes']),int(inp['available']),int(inp['backup']))
   for key,value in expected.items():self.assertEqual(value,out[key],(key,inp['bytes'][:240],out))
  return values
 def test_geometry_profiles_and_high_address_counts(self):
  rows=[]
  for shift in range(9,13):
   for cs in (0,3,25-shift):
    for copies in (1,2):
     raw,available=boot(shift,cs,copies=copies)
     for role in (0,1):rows.append(request(raw,available,role))
  for clusters in (1,127,MAX):
   raw,available=boot(clusters=clusters,cluster_shift=16)
   rows.append(request(raw,available))
  for out in self.check(rows):self.assertTrue(out['usable_geometry'])
 def test_rehashed_structural_mutations_and_u64_overflow(self):
  cases=[];raw,available=boot()
  for offset,width,value in [(0,1,0),(3,1,0),(11,1,1),(113,1,1),(104,2,0x101),(106,2,16),
    (106,2,1),(112,1,101),(110,1,0),(110,1,3),(80,4,23),(84,4,0),(84,4,1),
    (88,4,1),(88,4,0xffffffff),(92,4,0),(92,4,MAX+1),(96,4,1),(96,4,4098),
    (72,8,1),(72,8,U64)]:
   changed=bytearray(raw);changed[offset:offset+width]=value.to_bytes(width,'little');seal(changed)
   cases.append(request(changed,available))
  for out in self.check(cases):self.assertFalse(out['usable_geometry'])
 def test_invalid_shifts_truncation_and_overlong_output_conservation(self):
  raw,available=boot();rows=[request(raw[:n],available) for n in (0,1,511,512,513,5632,6143)]
  rows += [request(raw+b'x',available),request(bytes(49153),available),request(raw,available,2)]
  for shift in (0,8,13,255):
   changed=bytearray(raw);changed[108]=shift;rows.append(request(changed,available))
  for cs in (17,255):
   changed=bytearray(raw);changed[109]=cs;seal(changed);rows.append(request(changed,available))
  self.check(rows)
 def test_checksum_every_word_and_excluded_fields(self):
  rows=[]
  for shift in range(9,13):
   raw,available=boot(shift,copies=2);unit=1<<shift
   for position in range(unit//4):
    changed=bytearray(raw);changed[unit*11+position*4]^=1;rows.append(request(changed,available))
    if len(rows)==32:
     for out in self.check(rows):
      self.assertFalse(out['checksum_valid']);self.assertEqual(1,out['checksum_mismatches'])
     rows=[]
   if rows:
    self.check(rows);rows=[]
   for offset in (106,107,112):
    changed=bytearray(raw);changed[offset]^=1;rows.append(request(changed,available))
   for offset in (120,unit,unit*9+100,unit*10):
    changed=bytearray(raw);changed[offset]^=1;rows.append(request(changed,available))
   self.check(rows);rows=[]
  self.check(rows)
 def test_minimum_volume_and_maximum_byte_conversion(self):
  rows=[]
  for shift in range(9,13):
   unit=1<<shift;raw,_=boot(shift);heap=struct.unpack_from('<I',raw,88)[0]
   for volume in (1048576//unit-1,1048576//unit,U64//unit,U64//unit+1):
    changed=bytearray(raw)
    struct.pack_into('<Q',changed,72,volume)
    struct.pack_into('<I',changed,92,min(volume-heap,MAX))
    seal(changed);rows.append(request(changed,U64))
  values=self.check(rows)
  for index,out in enumerate(values):
   if index%4==0:self.assertTrue(out['issues']&ISS['counters'])
   if index%4==1:self.assertTrue(out['usable_geometry'])
   if index%4==2:self.assertFalse(out['issues']&ISS['overflow'])
   if index%4==3:self.assertTrue(out['issues']&ISS['overflow'])
 def test_seeded_valid_geometry_and_data_boundaries(self):
  rng=random.Random(5801);rows=[]
  for _ in range(80):
   shift=rng.randrange(9,13);cs=rng.randrange(0,26-shift);count=rng.randrange(2048,100000);copies=rng.randrange(1,3)
   raw,available=boot(shift,cs,count,copies,trailing=rng.randrange(1<<cs))
   raw[106]=rng.randrange(copies)|rng.choice((0,2,4,8));raw[112]=rng.choice((0,100,255))
   struct.pack_into('<Q',raw,64,rng.randrange(1<<64));seal(raw);rows.append(request(raw,available))
   rows.append(request(raw,available-1))
  values=self.check(rows)
  for i,out in enumerate(values):self.assertEqual(i%2==0,out['usable_geometry'])
 def test_extended_reserved_and_undefined_metadata(self):
  raw,available=boot();rows=[]
  for at in (1020,10*512,113):
   changed=bytearray(raw);changed[at]^=1;seal(changed);rows.append(request(changed,available))
  for at in (120,9*512+17):
   changed=bytearray(raw);changed[at]^=1;seal(changed);rows.append(request(changed,available))
  values=self.check(rows);self.assertTrue(all(not v['usable_geometry'] for v in values[:3]));self.assertTrue(all(v['usable_geometry'] for v in values[3:]))
 def test_cells_do_not_claim_bitmap_allocation(self):
  rows=[];expected=[]
  for clusters in (1,4096,MAX):
   for index in (0,1,2,clusters+1):
    for value in (0,1,2,clusters+1,0xfffffff6,0xfffffff7,0xfffffff8,0xffffffff):
     rows.append(dict(op='cell',bytes=struct.pack('<I',value).hex(),clusters=str(clusters),index=str(index)))
     expected.append(0 if index<2 else 1 if value==0 else 4 if value==0xffffffff else 3 if value==0xfffffff7 else 2 if 2<=value<=clusters+1 else 5)
  values=run(rows)
  for out,kind in zip(values,expected):self.assertEqual(0,out['status']);self.assertEqual(kind,out['kind'])
  invalid=[dict(op='cell',bytes=bytes(n).hex(),clusters='10',index='2') for n in (0,1,3,5)]
  invalid += [dict(op='cell',bytes='00000000',clusters=str(c),index=str(i)) for c,i in [(0,2),(MAX+1,2),(10,12)]]
  for out in run(invalid):self.assertNotEqual(0,out['status'])
def main():
 global PROBE
 p=argparse.ArgumentParser();p.add_argument('--probe',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args();PROBE=args.probe.resolve()
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ExfatTests))
 args.output.write_text(json.dumps(dict(passed=result.wasSuccessful(),methods=result.testsRun,cases=sum(r['cases'] for r in RECORDS),records=RECORDS),indent=2)+'\n',encoding='utf-8',newline='\n')
 return 0 if result.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
