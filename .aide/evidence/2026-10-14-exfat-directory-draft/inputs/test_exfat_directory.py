"""Independent exFAT entry-set oracle over generated supplied bytes."""
import argparse,hashlib,json,random,struct,subprocess,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'tests/property'))
from exfat_directory_vectors import file_set,extension,seal,set_checksum,timestamp,valid_timestamp
PROBE=None;RECEIPTS=[];MAX=(1<<32)-11
TRUNC,TYPE,ORDER,SUM,UNSUPPORTED,LENGTH,FLAGS,CLUSTER,CAPACITY,TIME,UTF16,CHARS,DOT,RESERVED,PADDING=[1<<i for i in range(15)]
def request(raw,clusters=4096,shift=9,budget=8192):return dict(op='set',bytes=bytes(raw).hex(),clusters=str(clusters),shift=str(shift),budget=str(budget))
def time_oracle(raw,fraction,offset):
 valid=valid_timestamp(raw) and fraction<=199 and (offset>=128 or offset==0)
 signed=offset&127;signed=signed if signed<64 else signed-128
 return dict(raw=raw,fraction=fraction,offset=offset,valid=valid,offset_known=offset>=128,offset_minutes=signed*15 if offset>=128 else 0,year=1980+(raw>>25),month=(raw>>21)&15,day=(raw>>16)&31,hour=(raw>>11)&31,minute=(raw>>5)&63,second=(raw&31)*2)
def illegal(n):return n<32 or n in (34,42,47,58,60,62,63,92,124)
def oracle(raw,clusters,shift,budget):
 if not 1<=clusters<=MAX or not 9<=shift<=25:return dict(status=1)
 if len(raw)>8192 or len(raw)>budget:return dict(status=7)
 if len(raw)<32:return dict(status=0,issues=TRUNC,primary_present=False,present_bytes=len(raw),associated=False,metadata_valid=False)
 declared=(raw[1]+1)*32;present=min(len(raw),declared);complete=present==declared
 issues=0 if complete else TRUNC
 out=dict(status=0,primary_present=True,secondary_count=raw[1],declared_bytes=declared,present_bytes=present,complete=complete)
 if raw[0]!=0x85:out.update(issues=issues|TYPE,associated=False,metadata_valid=False);return out
 attrs,stored=struct.unpack_from('<H',raw,4)[0],struct.unpack_from('<H',raw,2)[0]
 if attrs&~0x37 or any(raw[6:8]) or any(raw[25:32]):issues|=RESERVED
 times=[time_oracle(struct.unpack_from('<I',raw,at)[0],fraction,offset) for at,fraction,offset in [(8,raw[20],raw[22]),(12,raw[21],raw[23]),(16,0,raw[24])]]
 if not all(t['valid'] for t in times):issues|=TIME
 out.update(attributes=attrs,stored_checksum=stored,created=times[0],modified=times[1],accessed=times[2])
 if complete:
  calc=set_checksum(raw[:declared]);valid=calc==stored;out.update(calculated_checksum=calc,checksum_valid=valid)
  if not valid:issues|=SUM
 if present<64 or raw[32]!=0xc0:out.update(issues=issues|ORDER,stream_present=False,associated=False,metadata_valid=False);return out
 flags,length=raw[33],raw[35];hash_value=struct.unpack_from('<H',raw,36)[0]
 valid_length=struct.unpack_from('<Q',raw,40)[0];cluster=struct.unpack_from('<I',raw,52)[0];data=struct.unpack_from('<Q',raw,56)[0]
 out.update(stream_present=True,stream_flags=flags,name_length=length,name_hash=hash_value,valid_data_length=str(valid_length),first_cluster=cluster,data_length=str(data))
 if flags&~3 or raw[34] or any(raw[38:40]) or any(raw[48:52]):issues|=RESERVED
 if not flags&1:issues|=FLAGS
 if not length:issues|=LENGTH
 names=(length+14)//15;expected=names+1;units=[]
 if raw[1]<expected:issues|=ORDER
 for index in range(names):
  at=(index+2)*32
  if at+32>present:issues|=TRUNC;break
  if raw[at]!=0xc1:issues|=ORDER;break
  if raw[at+1]:issues|=RESERVED
  for n in struct.unpack_from('<15H',raw,at+2):
   if len(units)<length:
    units.append(n)
    if illegal(n):issues|=CHARS
   elif n:issues|=PADDING
 benign=unknown=0
 for index in range(expected+1,raw[1]+1):
  at=index*32
  if at+32>present:break
  type_value=raw[at]
  if type_value&0xc0!=0xc0 or type_value in (0xc0,0xc1):issues|=ORDER
  elif not type_value&32:unknown+=1;issues|=UNSUPPORTED
  else:benign+=1
 try:struct.pack('<'+'H'*len(units),*units).decode('utf-16-le');encoding=len(units)==length
 except UnicodeDecodeError:encoding=False
 if not encoding:issues|=UTF16
 if units in ([46],[46,46]) and len(units)==length:issues|=DOT
 chars=bool(length) and len(units)==length and not issues&(CHARS|DOT)
 size=1<<shift
 if data>clusters*size or valid_length>data:issues|=CAPACITY
 if not cluster and data or cluster and not 2<=cluster<=clusters+1:issues|=CLUSTER
 if flags&2:
  if not cluster or not data:issues|=FLAGS
  elif 2<=cluster<=clusters+1 and data>(clusters+2-cluster)*size:issues|=CAPACITY
 if attrs&16 and (valid_length!=data or data>268435456 or data%size):issues|=LENGTH
 associated=complete and out.get('checksum_valid',False) and not issues&(TYPE|ORDER|UNSUPPORTED|TRUNC)
 stream=associated and not issues&(FLAGS|CLUSTER|CAPACITY|LENGTH)
 out.update(issues=issues,units=units,name_units_present=len(units),benign_extensions=benign,unsupported_extensions=unknown,encoding_valid=encoding,name_characters_valid=chars,associated=bool(associated),stream_valid=bool(stream),metadata_valid=bool(stream and encoding and chars and not issues&TIME))
 return out
def run(rows):
 data=json.dumps(rows,separators=(',',':')).encode();result=subprocess.run([str(PROBE)],input=data,capture_output=True,timeout=30)
 assert result.returncode==0 and not result.stderr,(result.returncode,result.stderr)
 values=json.loads(result.stdout);assert len(values)==len(rows)
 RECEIPTS.append(dict(input_sha256='sha256:'+hashlib.sha256(data).hexdigest(),cases=len(rows),exit_code=0));return values
class DirectoryTests(unittest.TestCase):
 def check(self,rows):
  values=run(rows)
  for row,out in zip(rows,values):
   expected=oracle(bytes.fromhex(row['bytes']),int(row['clusters']),int(row['shift']),int(row['budget']))
   for key,value in expected.items():self.assertEqual(value,out[key],(key,row['bytes'][:100],out))
   if expected['status']==0:self.assertEqual(row['bytes'][:out['present_bytes']*2],out['raw'])
  return values
 def test_every_name_length_and_secondary_count(self):
  rows=[request(file_set([65]*n)) for n in range(1,256)]
  for count in range(256):
   if count>=2:raw=file_set([65],extra=[extension()]*(count-2))
   else:raw=file_set([65]);raw[1]=count;raw=raw[:32*(count+1)];seal(raw)
   rows.append(request(raw))
  values=self.check(rows)
  for v in values[:255]:self.assertTrue(v['metadata_valid'])
 def test_structure_rehashed_unknown_and_extra_bytes(self):
  base=file_set([65]*16);rows=[]
  for at,value in [(0,0x86),(32,0xc1),(64,0xc0),(96,0),(96,0x41),(96,0x85)]:
   raw=bytearray(base);raw[at]=value;seal(raw);rows.append(request(raw))
  for type_value in (0xc2,0xe2,0xe0,0xe1,0x80,0,0x82,0xc0,0xc1):rows.append(request(file_set([65],extra=[extension(type_value)])))
  rows += [request(base+b'x'*32),request(file_set([65],padding=0x1234))]
  values=self.check(rows);self.assertTrue(values[-2]['metadata_valid']);self.assertTrue(values[-1]['associated']);self.assertTrue(values[-1]['issues']&PADDING)
 def test_truncation_budget_and_invalid_api_model(self):
  raw=file_set([65]*255);rows=[request(raw[:n]) for n in range(len(raw))]
  rows += [request(raw,budget=len(raw)-1),request(bytes(8193)),request(raw,clusters=0),request(raw,clusters=MAX+1),request(raw,shift=8),request(raw,shift=26)]
  for at in range(0,len(rows),96):self.check(rows[at:at+96])
 def test_stream_integer_and_contiguous_bounds(self):
  rows=[]
  for shift in (9,12,25):
   for clusters in (1,4096,MAX):
    for data,valid,cluster,flags,attrs in [(0,0,0,1,32),(1,0,2,1,32),(1,1,2,3,32),((1<<64)-1,0,2,1,32),(512,513,2,1,32),(512,512,1,1,32),(512,512,clusters+2,1,32),(512,512,clusters+1,3,32),(513,513,clusters+1,3,32),(512,512,0,1,32),(0,0,2,3,32),(512,512,2,0,32),(512,512,2,1,16),(513,513,2,1,16),(268435456,268435456,2,1,16),(268435457,268435457,2,1,16)]:
     rows.append(request(file_set([65],cluster=cluster,length=data,valid_length=valid,flags=flags,attributes=attrs),clusters,shift))
  self.check(rows)
 def test_rehashed_seeded_geometry_and_names(self):
  rng=random.Random(6402);rows=[]
  for _ in range(160):
   shift=rng.randrange(9,26);clusters=rng.choice([1,4096,MAX]);cluster=rng.randrange(2,clusters+2)
   size=1<<shift;data=rng.randrange(1,min(1<<40,(clusters+2-cluster)*size)+1)
   rows.append(request(file_set([rng.choice([65,97,0x20ac]) for _ in range(rng.randrange(1,256))],cluster=cluster,length=data,valid_length=rng.randrange(data+1),flags=3),clusters,shift))
  for out in self.check(rows):self.assertTrue(out['metadata_valid'])
 def test_lossless_utf16_characters_and_reserved(self):
  names=[[0xd83d,0xde00],[0xd800],[0xdc00],[46],[46,46],[65]*14+[0xd83d,0xde00],[0x202e,65],[0x61,0x301],[0xe1]]
  names += [[n] for n in list(range(32))+[34,42,47,58,60,62,63,92,124]]
  rows=[request(file_set(n)) for n in names]
  for at in (6,25,33,34,38,48,65):
   raw=file_set([65]);raw[at]|=128;seal(raw);rows.append(request(raw))
  values=self.check(rows)
  for row,out in zip(names,values):self.assertEqual(row,out['units'])
 def test_time_calendar_fraction_and_every_offset(self):
  rows=[]
  for offset in range(256):
   raw=file_set([65]);raw[22:25]=bytes([offset]*3);seal(raw);rows.append(request(raw))
  for field,values in [(20,[0,199,200,255]),(21,[0,199,200,255])]:
   for value in values:raw=file_set([65]);raw[field]=value;seal(raw);rows.append(request(raw))
  times=[0,timestamp(1980,1,1,0,0,0),timestamp(2107,12,31),timestamp(2000,2,29),timestamp(2100,2,29),timestamp(2024,2,30),timestamp(2024,0,1),timestamp(2024,13,1),timestamp(hour=24),timestamp(minute=60),timestamp(double_seconds=30)]
  for at in (8,12,16):
   for value in times:raw=file_set([65]);struct.pack_into('<I',raw,at,value);seal(raw);rows.append(request(raw))
  self.check(rows)
 def test_checksum_mutations_and_seeded_valid_sets(self):
  raw=file_set([65]*31,extra=[extension()]);rows=[]
  for at in range(len(raw)):
   changed=bytearray(raw);changed[at]^=1;rows.append(request(changed))
  rng=random.Random(6401)
  for _ in range(64):
   n=rng.randrange(1,256);units=[rng.choice([65,97,0x3a9,0xe1]) for _ in range(n)]
   rows.append(request(file_set(units,extra=[extension()] * rng.randrange(4))))
  self.check(rows)
 def test_all_slot_type_bytes_and_bounds(self):
  rows=[dict(op='slot',bytes=(bytes([n])+bytes(31)).hex()) for n in range(256)]
  for n,out in enumerate(run(rows)):
   expected=0 if n==0 else 1 if n<128 else 2 if n==128 else {129:3,130:4,131:5,133:6,192:7,193:8}.get(n,10 if n&64 else 9)
   self.assertEqual(0,out['status']);self.assertEqual(expected,out['kind']);self.assertEqual(n,out['type'])
  for out in run([dict(op='slot',bytes=bytes(n).hex()) for n in (0,1,31,33)]):self.assertEqual(7,out['status'])
def main():
 global PROBE
 p=argparse.ArgumentParser();p.add_argument('--probe',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args();PROBE=args.probe.resolve()
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DirectoryTests))
 args.output.write_text(json.dumps(dict(passed=result.wasSuccessful(),methods=result.testsRun,cases=sum(r['cases'] for r in RECEIPTS),records=RECEIPTS),indent=2)+'\n',encoding='utf-8',newline='\n')
 return 0 if result.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
