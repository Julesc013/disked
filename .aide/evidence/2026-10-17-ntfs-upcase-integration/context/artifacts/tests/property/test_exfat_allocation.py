"""Independent supplied bitmap descriptor and bit/count oracle."""
import argparse,hashlib,json,random,struct,subprocess,unittest
from pathlib import Path
PROBE=None;RECORDS=[];MAX=(1<<32)-11;U64=(1<<64)-1
def descriptor(clusters=4096,shift=9,fats=1,identifier=0,first=2,length=None,reserved=False):
 raw=bytearray(32);raw[0]=0x81;raw[1]=identifier;struct.pack_into('<I',raw,20,first);struct.pack_into('<Q',raw,24,(clusters+7)//8 if length is None else length)
 if reserved:raw[3]=0x7a;raw[1]|=0x80
 return dict(op='descriptor',bytes=raw.hex(),clusters=str(clusters),shift=str(shift),fats=str(fats))
def interval(raw,clusters,first,count,offset=0,length=None,budget=None):return dict(op='interval',bytes=bytes(raw).hex(),clusters=str(clusters),first=str(first),count=str(count),offset=str(offset),length=str((clusters+7)//8 if length is None else length),budget=str(count if budget is None else budget))
def oracle(row):
 raw=bytes.fromhex(row['bytes']);clusters=int(row['clusters'])
 if row['op']=='descriptor':
  shift,fats=int(row['shift']),int(row['fats'])
  if not 1<=clusters<=MAX or not 9<=shift<=25 or fats not in (1,2):return dict(status=1)
  if len(raw)!=32:return dict(status=7)
  first=struct.unpack_from('<I',raw,20)[0];length=struct.unpack_from('<Q',raw,24)[0];minimum=(clusters+7)//8;heap=clusters*(1<<shift);issues=0
  if raw[0]!=0x81:issues|=2
  if (raw[1]&1)>=fats:issues|=64
  if raw[1]&~1 or any(raw[2:20]):issues|=8192
  if not 2<=first<=clusters+1:issues|=128
  if length<minimum or length>heap:issues|=32
  return dict(status=0,issues=issues,identifier=raw[1]&1,first_cluster=first,data_length=str(length),minimum_bytes=str(minimum),heap_bytes=str(heap),valid=not bool(issues&~8192))
 first,count,offset,length,budget=[int(row[k]) for k in ('first','count','offset','length','budget')]
 if not 1<=clusters<=MAX or not 2<=first<=clusters+1 or not 1<=count<=clusters+2-first:return dict(status=1)
 if len(raw)>8192 or count>budget:return dict(status=7)
 if length<(clusters+7)//8:return dict(status=1)
 if offset+len(raw)>U64:return dict(status=2)
 if offset+len(raw)>length:return dict(status=7)
 start=first-2;last=start+count-1
 if start//8<offset or last//8>=offset+len(raw):return dict(status=7)
 unavailable=sum((raw[bit//8-offset]>>(bit%8))&1 for bit in range(start,last+1))
 return dict(status=0,first_cluster=first,cluster_count=count,available=count-unavailable,unavailable=unavailable,first_byte=str(start//8),last_byte=str(last//8))
def run(rows):
 data=json.dumps(rows,separators=(',',':')).encode();r=subprocess.run([str(PROBE)],input=data,capture_output=True,timeout=20);assert r.returncode==0 and not r.stderr,(r.returncode,r.stderr);values=json.loads(r.stdout);assert len(values)==len(rows);RECORDS.append(dict(cases=len(rows),input_sha256='sha256:'+hashlib.sha256(data).hexdigest()));return values
class Tests(unittest.TestCase):
 def check(self,rows):
  values=run(rows)
  for row,out in zip(rows,values):
   for key,value in oracle(row).items():self.assertEqual(value,out[key],(key,row,out))
  return values
 def test_descriptor_geometry_and_raw_advisory(self):
  rows=[]
  for clusters in (1,7,8,9,4096,MAX):
   for shift in (9,12,25):
    for fats in (1,2):
     for identifier in (0,1):
      for length in ((clusters+7)//8-1,(clusters+7)//8,clusters*(1<<shift),clusters*(1<<shift)+1):rows.append(descriptor(clusters,shift,fats,identifier,length=length,reserved=True))
  rows += [descriptor(first=n) for n in (0,1,2,4097,4098)]
  for type_value in (0,0x01,0x80,0x82,0xc1,0xff):
   row=descriptor();raw=bytearray.fromhex(row['bytes']);raw[0]=type_value;row['bytes']=raw.hex();rows.append(row)
  self.check(rows)
 def test_every_bit_position_and_reserved_final_bits(self):
  rows=[]
  for byte in range(256):
   for bit in range(8):rows.append(interval(bytes([byte]),8,bit+2,1))
  for clusters in range(1,17):rows.append(interval(b'\xff'*((clusters+7)//8),clusters,2,clusters))
  self.check(rows)
 def test_high_cluster_windows_and_seeded_intervals(self):
  rows=[];rng=random.Random(6501)
  for _ in range(160):
   clusters=rng.choice([4096,MAX]);first=rng.randrange(2,clusters+2);count=rng.randrange(1,min(4096,clusters+2-first)+1);offset=(first-2)//8;n=((first-2+count-1)//8)-offset+1;raw=bytes(rng.randrange(256) for _ in range(n));rows.append(interval(raw,clusters,first,count,offset))
  rows += [interval(bytes([255]),MAX,MAX+1,1,(MAX-1)//8),interval(bytes(8192),65536,2,65536),interval(bytes([255])*8192,65536,2,65536)]
  self.check(rows)
 def test_invalid_calls_budget_truncation_overflow(self):
  rows=[interval(bytes(n),64,2,64) for n in range(9)]
  rows += [interval(bytes(8193),65536,2,1),interval(bytes(8),64,2,64,budget=63),interval(bytes(8),64,1,1),interval(bytes(8),64,2,0),interval(bytes(8),64,65,2),interval(bytes(8),64,2,64,offset=1),interval(bytes(8),64,2,64,length=7),interval(bytes(1),64,2,1,offset=U64,length=U64),interval(bytes(1),64,2,1,offset=U64-1,length=U64)]
  self.check(rows)
  descriptors=[descriptor(clusters=0),descriptor(clusters=MAX+1),descriptor(shift=8),descriptor(shift=26),descriptor(fats=0),descriptor(fats=3)]
  for n in (0,1,31,33):row=descriptor();row['bytes']=bytes(n).hex();descriptors.append(row)
  self.check(descriptors)
def main():
 global PROBE
 p=argparse.ArgumentParser();p.add_argument('--probe',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args();PROBE=args.probe.resolve();r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests));args.output.write_text(json.dumps(dict(passed=r.wasSuccessful(),methods=r.testsRun,cases=sum(v['cases'] for v in RECORDS),records=RECORDS),indent=2)+'\n',encoding='utf-8',newline='\n');return 0 if r.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
