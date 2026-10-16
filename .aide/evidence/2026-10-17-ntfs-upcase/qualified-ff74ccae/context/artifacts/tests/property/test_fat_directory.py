"""Independent raw FAT directory/name fixtures; original representations stay exact."""
import argparse
import datetime
import hashlib
import json
import random
import struct
import subprocess
import unittest
from pathlib import Path

PROBE=None
RECEIPTS=[]
POSITIONS=(1,3,5,7,9,14,16,18,20,22,24,28,30)
DIR_TRUNC,ATTR,CASE,CLUSTER,STATE,TIME,ORDINAL,SLOT,NAME=1,2,4,8,16,32,64,128,256
LFN_TRUNC,LFN_ORD,LFN_SLOT,LFN_SUM,LFN_SHORT,PADDING,LENGTH,UTF16,CHARACTERS,NONCANON=1,2,4,8,16,32,64,128,256,512


def short(name=b'FILE    TXT',attributes=0x20,cluster=0,size=0,case=0):
    assert len(name)==11
    raw=bytearray(32);raw[:11]=name;raw[11]=attributes;raw[12]=case
    struct.pack_into('<H',raw,20,cluster>>16);struct.pack_into('<H',raw,26,cluster&0xffff)
    struct.pack_into('<I',raw,28,size);return raw


def checksum(name):
    # Mathematical rotate modulo8, independently of C's split bit operations.
    n=0
    for byte in name:n=((n//2)+(n%2)*128+byte)%256
    return n


def slots(units,record=None):
    record=short() if record is None else record
    values=list(units);count=(len(values)+12)//13
    assert count>0
    if len(values)%13:values+=[0]+[0xffff]*(count*13-len(values)-1)
    rows=[]
    for ordinal in range(count,0,-1):
        row=bytearray(32);row[0]=ordinal|(0x40 if ordinal==count else 0);row[11]=0x0f;row[13]=checksum(record[:11])
        for position,value in zip(POSITIONS,values[(ordinal-1)*13:ordinal*13]):struct.pack_into('<H',row,position,value)
        rows.append(row)
    return b''.join(rows),values


def code_units(text):return list(struct.unpack('<'+'H'*(len(text.encode('utf-16-le'))//2),text.encode('utf-16-le')))
def entry(raw,bits=32):return dict(op='entry',record=bytes(raw).hex(),bits=str(bits))
def long_name(raw,record=None,bits=32):return dict(op='lfn',slots=bytes(raw).hex(),record=bytes(short() if record is None else record).hex(),bits=str(bits))
def display(values,capacity=2048):return dict(op='display',units=list(map(str,values)),capacity=str(capacity))
def escaped(values):return ''.join('\\\\' if n==92 else chr(n) if 32<=n<=126 else f'\\u{n:04X}' for n in values)


def run(requests):
    data=b''.join(json.dumps(row,sort_keys=True,separators=(',',':')).encode()+b'\n' for row in requests)
    process=subprocess.run([str(PROBE)],input=data,capture_output=True,timeout=60)
    assert process.returncode==0 and not process.stderr,process.stderr.decode(errors='replace')
    result=[json.loads(line) for line in process.stdout.splitlines()];assert len(result)==len(requests)
    RECEIPTS.append(dict(cases=len(requests),input_sha256=hashlib.sha256(data).hexdigest(),output_sha256=hashlib.sha256(process.stdout).hexdigest()))
    return result


class DirectoryTests(unittest.TestCase):
    def test_entry_kinds_and_original_bytes(self):
        rows=[]
        for bits in (12,16,32):
            for attributes,kind in ((0,3),(0x20,3),(0x10,4),(8,5),(0x18,7)):
                raw=short(attributes=attributes);rows.append((entry(raw,bits),kind,raw))
            for marker,kind in ((0,1),(0xe5,2)):
                raw=bytearray([0xff]*32);raw[0]=marker;rows.append((entry(raw,bits),kind,raw))
        for result,(_,kind,raw) in zip(run([r[0] for r in rows]),rows):
            self.assertEqual(result['status'],0);self.assertEqual(result['kind'],kind);self.assertEqual(result['raw'],raw.hex())
            if kind in (1,2):self.assertEqual((result['issues'],result['cluster'],result['file_bytes']),(0,0,0))

    def test_unknown_attributes_case_and_short_name_encoding(self):
        rows=[]
        for bits in (12,16,32):
            for name in (b'\x05FILE   TXT',b'\x81\\FILE TXT ',b'MiXeD   TxT',b'ABC\x1bDEF TXT'):
                self.assertEqual(len(name),11);rows.append((entry(short(name=name,case=0x18),bits),name))
        for result,(_,name) in zip(run([r[0] for r in rows]),rows):
            self.assertEqual(result['name_field'],name.hex());self.assertEqual(result['case_flags'],0x18)
            self.assertEqual(result['lead_escape'],name[0]==5);self.assertEqual(result['issues'],0)
        for value,issue in ((short(attributes=0xa0),ATTR),(short(case=1),CASE),(short(name=b' FILE   TXT'),NAME)):
            self.assertEqual(run([entry(value)])[0]['issues'],issue)

    def test_exact_cluster_words_and_size_semantics(self):
        cases=[]
        for bits in (12,16,32):
            for cluster in (0,1,2,0xfff,0x1000,0xffff,0x10002,0x0ffffff6,0xf0000002):
                raw=short(cluster=cluster,size=1)
                cases.append((entry(raw,bits),bits,cluster))
        for result,(_,bits,cluster) in zip(run([r[0] for r in cases]),cases):
            self.assertEqual(result['raw_cluster'],cluster)
            self.assertEqual(result['cluster'],cluster&0x0fffffff if bits==32 else cluster&0xffff)
            self.assertEqual(result['file_bytes'],1)
            invalid=(bits==32 and cluster>=0x10000000) or (bits!=32 and cluster>0xffff) or (bits==12 and (cluster&0xffff)>0xfff)
            self.assertEqual(bool(result['issues']&CLUSTER),bool(invalid))
        for raw in (short(cluster=2),short(cluster=0,size=1),short(cluster=1,size=1),
                    short(attributes=8,cluster=2),short(attributes=8,size=1),short(attributes=0x10,size=1)):
            self.assertTrue(run([entry(raw)])[0]['issues']&STATE)
        for raw,dot in ((short(name=b'.          ',attributes=0x10,cluster=2),1),
                        (short(name=b'..         ',attributes=0x10),2)):
            result=run([entry(raw)])[0];self.assertEqual((result['dot'],result['issues']),(dot,0))

    def test_gregorian_date_oracle_and_raw_preservation(self):
        requests,expected=[],[]
        for year in (1980,1984,1999,2000,2004,2096,2100,2104,2107):
            for month in range(16):
                for day in range(32):
                    value=((year-1980)<<9)|(month<<5)|day;raw=short();struct.pack_into('<HH',raw,16,value,value);struct.pack_into('<H',raw,24,value)
                    try:datetime.date(year,month,day);valid=True
                    except ValueError:valid=(value==0)
                    requests.append(entry(raw));expected.append((value,valid))
        for offset in range(0,len(requests),512):
            for result,(raw,valid) in zip(run(requests[offset:offset+512]),expected[offset:offset+512]):
                self.assertEqual((result['creation_date'],result['access_date'],result['write_date']),(raw,raw,raw))
                self.assertEqual(result['issues'],0 if valid else TIME)

    def test_time_fields_and_all_creation_fraction_values(self):
        requests,expected=[],[]
        for hour in range(32):
            for minute in (0,1,30,59,60,63):
                for second in (0,1,29,30,31):
                    value=(hour<<11)|(minute<<5)|second;raw=short();struct.pack_into('<H',raw,14,value);struct.pack_into('<H',raw,22,value)
                    requests.append(entry(raw));expected.append((value,hour<=23 and minute<=59 and second<=29))
        for result,(value,valid) in zip(run(requests),expected):
            self.assertEqual((result['creation_time'],result['write_time']),(value,value))
            self.assertEqual(result['issues'],0 if valid else TIME)
        requests=[]
        for value in range(256):raw=short();raw[13]=value;requests.append(entry(raw))
        for value,result in enumerate(run(requests)):
            self.assertEqual(result['fraction'],value);self.assertEqual(result['issues'],0 if value<200 else TIME)

    def test_record_and_checksum_truncation_and_budget(self):
        for bits in (12,16,32):
            for result in run([entry(short()[:n],bits) for n in range(32)]):
                self.assertEqual((result['status'],result['issues'],result['kind']),(0,DIR_TRUNC,0))
            self.assertEqual(run([entry(short()+b'x',bits)])[0],{'status':7})
        self.assertEqual(run([entry(short(),8)])[0],{'status':1})
        for length in range(13):
            result=run([dict(op='checksum',name=(b'A'*length).hex())])[0]
            if length==11:self.assertEqual(result['checksum'],checksum(b'A'*11))
            else:self.assertEqual(result,{'status':7})

    def test_independent_checksum_and_stored_lead_byte(self):
        rng=random.Random(0x026C);names=[bytes(rng.randrange(256) for _ in range(11)) for _ in range(256)]
        names += [b'\x05FILE   TXT',b'\xe5FILE   TXT',b'FILE    TXT']
        for result,name in zip(run([dict(op='checksum',name=n.hex()) for n in names]),names):
            self.assertEqual(result['checksum'],checksum(name))
        self.assertNotEqual(checksum(names[-3]),checksum(names[-2]))

    def test_all_long_name_lengths_and_exact_unit_boundaries(self):
        requests,expected=[],[]
        for length in range(1,256):
            values=[ord('A')+(i%26) for i in range(length)];raw,payload=slots(values)
            requests.append(long_name(raw));expected.append((values,payload,raw))
        for result,(values,payload,raw) in zip(run(requests),expected):
            self.assertEqual((result['status'],result['issues'],result['associated'],result['unicode_valid'],result['canonical']),(0,0,True,True,True))
            self.assertEqual(result['units'],payload);self.assertEqual(result['name_length'],len(values));self.assertEqual(result['raw_slots'],raw.hex())
            self.assertEqual(result['terminated'],len(values)%13!=0);self.assertEqual(result['display']['text'],escaped(values))

    def test_checksum_collision_is_correlation_not_authentication(self):
        first=second=None;seen={}
        for n in range(10000):
            candidate=f'N{n:07d}TXT'.encode()
            value=checksum(candidate)
            if value in seen:first=short(name=seen[value]);second=short(name=candidate);break
            seen[value]=candidate
        self.assertIsNotNone(second)
        raw,_=slots(code_units('Correlated.txt'),first)
        rows=run([long_name(raw,first),long_name(raw,second)])
        self.assertTrue(all(r['associated'] for r in rows))
        self.assertNotEqual(rows[0]['raw_short'],rows[1]['raw_short'])

    def test_single_slot_fields_and_malformed_shapes(self):
        raw,_=slots(code_units('Alpha.txt'));self.assertEqual(len(raw),32)
        result=run([entry(raw)])[0];self.assertEqual((result['kind'],result['issues']),(6,0));self.assertEqual(result['ordinal'],0x41)
        self.assertEqual(result['units'],[int.from_bytes(raw[p:p+2],'little') for p in POSITIONS])
        for offset,value,issue in ((0,0x20,ORDINAL),(0,0,0),(0,0x55,ORDINAL),(11,0x8f,ATTR),(12,1,SLOT),(26,1,SLOT)):
            changed=bytearray(raw);changed[offset]=value;result=run([entry(changed)])[0]
            if offset==0 and value==0:self.assertEqual(result['kind'],1)
            else:self.assertTrue(result['issues']&issue)

    def test_order_missing_duplicate_reserved_and_second_last_markers(self):
        raw,_=slots(code_units('ABCDEFGHIJKLMNOPQRSTUVWXYZ.txt'))
        groups=[]
        groups.append(raw[32:]+raw[:32]);groups.append(raw[:32]+raw[64:]);groups.append(raw[:32]+raw[:32]+raw[64:])
        for offset,value in ((0,3),(0,0x40),(0,0x63),(32,0x42),(64,2),(64,0x81)):
            changed=bytearray(raw);changed[offset]=value;groups.append(bytes(changed))
        for result in run([long_name(group) for group in groups]):
            self.assertFalse(result['associated']);self.assertTrue(result['issues']&LFN_ORD);self.assertEqual(result['unit_count'],0)

    def test_checksums_and_active_following_short_record(self):
        raw,_=slots(code_units('Long name.txt'))
        bad=bytearray(raw);bad[13]^=1
        self.assertEqual(run([long_name(bad)])[0]['issues'],LFN_SUM)
        for following in (short(name=b'OTHER   TXT'),short(attributes=8),short(attributes=0x18),
                          short(name=b'.          ',attributes=0x10),short(attributes=0xa0),short(name=b' FILE   TXT')):
            result=run([long_name(raw,following)])[0];self.assertFalse(result['associated'])
        for marker in (0,0xe5):
            following=short();following[0]=marker;result=run([long_name(raw,following)])[0]
            self.assertFalse(result['associated']);self.assertTrue(result['issues']&LFN_SHORT)
        following=short(cluster=0,size=123);raw,_=slots(code_units('Long name.txt'),following)
        self.assertTrue(run([long_name(raw,following)])[0]['associated'])

    def test_deleted_unknown_type_and_nonzero_reserved_cluster(self):
        raw,_=slots(code_units('A name.txt'))
        for offset,value in ((0,0xe5),(11,0x8f),(11,0x20),(12,1),(26,1)):
            changed=bytearray(raw);changed[offset]=value;result=run([long_name(changed)])[0]
            self.assertFalse(result['associated']);self.assertTrue(result['issues']&(LFN_SLOT|LFN_ORD))

    def test_payload_termination_padding_empty_overlong_redundant(self):
        raw,_=slots(code_units('ABC'))
        changed=bytearray(raw);struct.pack_into('<H',changed,POSITIONS[4],ord('X'))
        self.assertTrue(run([long_name(changed)])[0]['issues']&PADDING)
        changed=bytearray(raw);struct.pack_into('<H',changed,POSITIONS[1],0xffff)
        self.assertTrue(run([long_name(changed)])[0]['issues']&PADDING)
        changed=bytearray(raw);struct.pack_into('<H',changed,POSITIONS[0],0)
        self.assertFalse(run([long_name(changed)])[0]['associated'])
        oversized,_=slots([65]*260);result=run([long_name(oversized)])[0]
        self.assertFalse(result['associated']);self.assertTrue(result['issues']&LENGTH)
        redundant,_=slots([65]*14);changed=bytearray(redundant)
        # Logical slot2 is physically first: terminator at its first unit makes
        # a13-unit name incorrectly consume a second slot.
        for i,p in enumerate(POSITIONS):struct.pack_into('<H',changed,p,0 if i==0 else 0xffff)
        result=run([long_name(changed)])[0];self.assertFalse(result['associated']);self.assertTrue(result['issues']&LENGTH)

    def test_missing_short_and_partial_or_oversized_sets(self):
        raw,_=slots(code_units('A name.txt'))
        for result in run([long_name(raw,short()[:n]) for n in range(32)]):
            self.assertEqual(result['issues'],LFN_TRUNC);self.assertFalse(result['associated'])
        for length in (1,2,31,33,63,639):
            result=run([long_name(bytes(length))])[0];self.assertEqual(result['issues'],LFN_TRUNC)
        self.assertEqual(run([long_name(bytes(641))])[0],{'status':3})
        self.assertEqual(run([long_name(raw,short()+b'x')])[0],{'status':7})
        result=run([long_name(b'')])[0];self.assertEqual((result['issues'],result['associated'],result['unit_count']),(0,False,0))

    def test_utf16_surrogates_across_slot_boundary_and_invalid_originals(self):
        cases=[([65]*12+[0xd83d,0xde80]+[66]*4,True),([0xd800],False),([0xdc00],False),
               ([65]*12+[0xd800,66],False),([0xd800,0xd800,0xdc00],False),([0xd800,0xdc00],True)]
        for values,valid in cases:
            raw,payload=slots(values);result=run([long_name(raw)])[0]
            self.assertTrue(result['associated']);self.assertEqual(result['unicode_valid'],valid)
            self.assertEqual(result['units'],payload);self.assertEqual(result['display']['text'],escaped(values))
            self.assertEqual(bool(result['issues']&UTF16),not valid)

    def test_original_normalization_case_and_noncanonical_names_remain_distinct(self):
        texts=['Café.txt','Cafe\u0301.txt','MiXeD.txt','mixed.txt',' name.txt','name.txt ','name.txt.','file\u202e.txt']
        requests=[]
        for text in texts:raw,_=slots(code_units(text));requests.append(long_name(raw))
        rows=run(requests)
        for text,row in zip(texts,rows):
            self.assertTrue(row['associated']);self.assertEqual(row['units'][:row['name_length']],code_units(text))
            self.assertEqual(row['display']['text'],escaped(code_units(text)))
        self.assertNotEqual(rows[0]['units'],rows[1]['units']);self.assertNotEqual(rows[2]['units'],rows[3]['units'])
        for row in rows[4:7]:self.assertTrue(row['issues']&NONCANON);self.assertFalse(row['canonical'])
        self.assertTrue(rows[-1]['canonical']);self.assertTrue(rows[-1]['requires_escaping'])

    def test_illegal_characters_preserve_byte_correlation(self):
        for unit in list(range(1,32))+list(map(ord,'"*/:<>?\\|')):
            values=[65,unit,66];raw,payload=slots(values);result=run([long_name(raw)])[0]
            self.assertTrue(result['associated']);self.assertTrue(result['issues']&CHARACTERS)
            self.assertFalse(result['canonical']);self.assertEqual(result['units'],payload)
            self.assertEqual(result['display']['text'],escaped(values))

    def test_display_reversibility_budget_and_unchanged_capacity_errors(self):
        values=[0,10,27,31,32,34,65,92,126,127,128,0x202e,0xd800,0xdc00,0xffff]
        expected=escaped(values)
        self.assertEqual(run([display(values,len(expected)+1)])[0],dict(status=0,text=expected))
        for capacity in (0,1,len(values),len(expected)):
            self.assertEqual(run([display(values,capacity)])[0],{'status':3})
        self.assertEqual(run([display([0xffff]*261)])[0],{'status':3})
        self.assertEqual(run([display([],1)])[0],dict(status=0,text=''))
        rng=random.Random(0xD15A);requests=[]
        for _ in range(128):requests.append(display([rng.randrange(65536) for _ in range(rng.randrange(1,261))]))
        for request,result in zip(requests,run(requests)):
            self.assertEqual(result['text'],escaped(list(map(int,request['units']))))


def main():
    global PROBE
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--probe',type=Path,required=True);parser.add_argument('--output',type=Path)
    args=parser.parse_args();PROBE=args.probe.resolve()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DirectoryTests))
    if args.output:args.output.write_text(json.dumps(dict(tests_run=result.testsRun,passed=result.wasSuccessful(),
        cases=sum(r['cases'] for r in RECEIPTS),batches=RECEIPTS),indent=2)+'\n',encoding='utf-8')
    print('FAT directory/name supplied-byte cases executed: '+str(sum(r['cases'] for r in RECEIPTS)),flush=True)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__=='__main__':main()
