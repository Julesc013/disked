"""Independent byte/checksum/map oracle; no host Unicode normalization."""
import argparse,hashlib,json,random,struct,subprocess,unittest
from pathlib import Path
PROBE=None;RECORDS=[];MAX=(1<<32)-11;MAP_UNITS=0;NAME_PAIRS=0
def checksum(raw):
 n=0
 for byte in raw:n=((n//2)+(n%2)*(1<<31)+byte)&0xffffffff
 return n
def mapping():return [i-32 if 97<=i<=122 else i for i in range(65536)]
def literal(table):return struct.pack('<65536H',*table)
def compress(table):
 words=[];i=0
 while i<65536:
  if table[i]==i and i<65535:
   run=1
   while i+run<65535 and run<65535 and table[i+run]==i+run:run+=1
   words.extend([65535,run]);i+=run
  else:words.append(table[i]);i+=1
 return struct.pack('<'+'H'*len(words),*words)
def decode(raw,compressed):
 table=[];issues=0;need_count=False
 for at in range(0,len(raw)-1,2):
  word=int.from_bytes(raw[at:at+2],'little')
  if issues&1:continue
  if len(table)>=65536:issues|=1;continue
  if need_count:
   need_count=False
   if not word or word>65536-len(table):issues|=1;continue
   table.extend(range(len(table),len(table)+word))
  elif compressed and word==65535 and len(table)<65535:need_count=True
  else:table.append(word)
 if len(raw)%2 or need_count:issues|=1
 if len(table)!=65536:issues|=4
 for i,n in enumerate(table[:128]):
  if n!=(i-32 if 97<=i<=122 else i):issues|=8
 return table,issues
def action(size,offset,mb=65536,capacity=65536,bb=None):return dict(size=str(size),offset=str(offset),mapping_budget=str(mb),capacity=str(capacity),byte_budget=str(size if bb is None else bb))
def request(raw,compressed=1,chunks=None,names=(),expected=None,length=None,validation=False,actions=None):
 if actions is None:
  chunks=chunks or [min(8192,len(raw)-at) for at in range(0,len(raw),8192)];actions=[];at=0
  for n in chunks:actions.append(action(n,at));at+=n
 return dict(op='stream',bytes=bytes(raw).hex(),length=str(len(raw) if length is None else length),checksum=str(checksum(raw) if expected is None else expected),compressed=str(compressed),validation=str(int(validation)),actions=actions,names=[dict(left=list(map(str,a)),right=list(map(str,b))) for a,b in names])
def namehash(table,units):
 n=0
 for unit in units:
  for byte in struct.pack('<H',table[unit]):n=((n//2)+(n%2)*32768+byte)&65535
 return n
def run(rows):
 data=json.dumps(rows,separators=(',',':')).encode();r=subprocess.run([str(PROBE)],input=data,capture_output=True,timeout=90);assert r.returncode==0 and not r.stderr,(r.returncode,r.stderr);out=json.loads(r.stdout);assert len(out)==len(rows);RECORDS.append(dict(cases=len(rows),input_sha256='sha256:'+hashlib.sha256(data).hexdigest()));return out
class Tests(unittest.TestCase):
 def check(self,rows):
  global MAP_UNITS,NAME_PAIRS
  out=run(rows)
  for row,v in zip(rows,out):
   raw=bytes.fromhex(row['bytes']);length=int(row['length']);compressed=int(row['compressed'])
   invalid=compressed not in (0,1) or not length or length%2 or (not compressed and length!=131072) or (compressed and length>262144)
   self.assertEqual(1 if invalid else 0,v['init_status'])
   if invalid:continue
   self.assertTrue(all(n==0 for n in v['statuses']),v);self.assertEqual(0,v['finish_status'])
   table,issues=decode(raw,compressed)
   MAP_UNITS+=len(table);NAME_PAIRS+=len(row['names'])
   if checksum(raw)!=int(row['checksum']):issues|=2
   self.assertEqual(issues,v['issues']);self.assertEqual(not issues,v['valid']);self.assertEqual(len(raw),v['consumed']);self.assertEqual(len(table),v['mapped']);self.assertEqual(checksum(raw),v['checksum'])
   expected_map=b'' if int(row['validation']) else struct.pack('<'+'H'*len(table),*table)
   self.assertEqual('sha256:'+hashlib.sha256(expected_map).hexdigest(),v['map_sha256'])
   for pair,observed in zip(row['names'],v['names']):
    a,b=[list(map(int,pair[k])) for k in ('left','right')]
    if not a or not b or len(a)>255 or len(b)>255:
     self.assertNotEqual(0,observed['equal_status']);continue
    self.assertEqual(namehash(table,a),observed['left_hash']);self.assertEqual(namehash(table,b),observed['right_hash']);self.assertEqual(int([table[n] for n in a]==[table[n] for n in b]),observed['equal'])
  return out
 def test_complete_literal_compressed_and_all_mappings(self):
  table=mapping();table[0x3c9]=0x3a9;table[0xe1]=0xc1
  rows=[request(literal(table),0),request(compress(table),1),request(compress(table),1,validation=True)]
  self.check(rows)
 def test_every_word_and_run_split(self):
  raw=compress(mapping());rows=[]
  for split in range(1,len(raw)):rows.append(request(raw,chunks=[split,len(raw)-split]))
  rows.append(request(raw,chunks=[1]*len(raw)))
  self.check(rows)
 def test_literal_one_byte_streaming(self):
  raw=literal(mapping());self.check([request(raw,0,chunks=[1]*len(raw))])
 def test_rehashed_malformed_and_checksum(self):
  table=mapping();raw=compress(table);rows=[]
  for words in [[65535],[65535,0],[65535,65535,65535],[65535,1,65535,65535,65535], [0]*128]:
   changed=struct.pack('<'+'H'*len(words),*words);rows.append(request(changed))
  rows.extend([request(raw[:-2]),request(raw+b'\x00\x00'),request(raw,expected=checksum(raw)^1)])
  table[97]=97;rows.append(request(literal(table),0));self.check(rows)
 def test_seeded_custom_maps_and_every_compressed_byte(self):
  rng=random.Random(6601);rows=[]
  for _ in range(12):
   table=mapping()
   for _ in range(32):table[rng.randrange(128,65535)]=rng.randrange(65535)
   raw=compress(table);cuts=[];remaining=len(raw)
   while remaining:n=min(remaining,rng.randrange(1,513));cuts.append(n);remaining-=n
   rows.append(request(raw,chunks=cuts))
  self.check(rows)
  raw=compress(mapping());rows=[]
  for at in range(len(raw)):
   changed=bytearray(raw);changed[at]^=1;rows.append(request(changed))
  self.check(rows)
 def test_name_lengths_volume_maps_and_collision(self):
  table=mapping();table[0xe1]=0xc1;table[0x3c9]=0x3a9
  pairs=[([97]*n,[65]*n) for n in range(1,256)]
  pairs += [([0xe1],[0xc1]),([0x3c9],[0x3a9]),([0xd800,0xdc00],[0xd800,0xdc00]),([0x61,0x301],[0xe1]),([], [65]),([65]*256,[65]*256)]
  # A small independently searched collision must still compare unequal.
  seen={};collision=None
  for a in range(128,512):
   for b in range(128,144):
    key=namehash(table,[a,b]);prior=seen.get(key)
    if prior and prior!=[a,b]:collision=(prior,[a,b]);break
    seen[key]=[a,b]
   if collision:break
  self.assertIsNotNone(collision);pairs.append(collision)
  rows=[request(compress(table),names=pairs),request(compress(mapping()),names=[([0xe1],[0xc1])])]
  values=self.check(rows);v=values[0]['names'][-1];self.assertEqual(v['left_hash'],v['right_hash']);self.assertEqual(0,v['equal']);self.assertEqual(0,values[1]['names'][0]['equal'])
 def test_api_budget_offset_capacity_and_pending_drain(self):
  raw=compress(mapping());actions=[action(4,1),action(4,0,bb=3),action(4,0,capacity=96),action(4,0,mb=96),action(0,4,mb=1)]
  # First three calls refuse; fourth emits96identities and holds one pending.
  actions += [action(52,4,mb=26),action(4,56,mb=1)]
  remaining=65411
  while remaining:n=min(128,remaining);actions.append(action(0,60,mb=n,capacity=n));remaining-=n
  actions.append(action(2,60,mb=1))
  row=request(raw,actions=actions);value=run([row])[0];self.assertEqual([1,7,3,0,0],value['statuses'][:5]);self.assertTrue(value['valid']);self.assertEqual(65536,value['mapped'])
 def test_descriptor_and_invalid_lengths(self):
  rows=[]
  for clusters in (1,4096,MAX):
   for shift in (9,25):
    for length in (0,1,2,512,131072,262144,262146,(1<<64)-1):
     raw=bytearray(32);raw[0]=0x82;raw[1]=1;struct.pack_into('<IIQ',raw,16,0,2,length)
     rows.append(dict(op='descriptor',bytes=raw.hex(),clusters=str(clusters),shift=str(shift)))
  values=run(rows)
  for row,v in zip(rows,values):
   raw=bytes.fromhex(row['bytes']);clusters,shift=int(row['clusters']),int(row['shift']);length=int.from_bytes(raw[24:32],'little');issues=8192
   if not length or length%2 or length>262144 or length>clusters*(1<<shift):issues|=32
   self.assertEqual(issues,v['issues']);self.assertEqual(not bool(issues&~8192),v['valid']);self.assertEqual(str(length),v['data_length'])
  self.check([request(b'',length=n,compressed=c) for n,c in [(0,1),(1,1),(262146,1),(2,0),(131072,2)]])
 def test_descriptor_types_clusters_and_capacity(self):
  rows=[];expected=[]
  for type_value in (0,1,0x80,0x81,0x82,0xc2,0xff):
   for first in (0,1,2,4097,4098):
    raw=bytearray(32);raw[0]=type_value;struct.pack_into('<IIQ',raw,16,0,first,2);rows.append(dict(op='descriptor',bytes=raw.hex(),clusters='4096',shift='9'));expected.append((2 if type_value!=0x82 else 0)|(128 if not 2<=first<=4097 else 0))
  for v,issues in zip(run(rows),expected):self.assertEqual(issues,v['issues'])
  rows=[]
  for n in (0,1,31,33):rows.append(dict(op='descriptor',bytes=bytes(n).hex(),clusters='4096',shift='9'))
  for v in run(rows):self.assertEqual(7,v['status'])
def main():
 global PROBE
 p=argparse.ArgumentParser();p.add_argument('--probe',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();PROBE=a.probe.resolve();r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests));a.output.write_text(json.dumps(dict(passed=r.wasSuccessful(),methods=r.testsRun,cases=sum(x['cases'] for x in RECORDS),mapping_units_checked=MAP_UNITS,name_pairs_checked=NAME_PAIRS,records=RECORDS),indent=2)+'\n',encoding='utf-8',newline='\n');return 0 if r.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
