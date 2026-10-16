"""Independent supplied-byte/name oracles for the capture-local namespace."""
import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path
import struct
import subprocess
import unittest
from exfat_directory_vectors import file_set, seal, extension
from test_exfat_upcase import mapping, literal, compress, checksum, namehash

P=argparse.ArgumentParser();P.add_argument('--probe',type=Path,required=True);P.add_argument('--output',type=Path,required=True)
ARGS,REST=P.parse_known_args();RECORDS=[];CASE_COUNT=0
TABLE=mapping();TABLE[0xe9]=0xc9

def entry(name, table=TABLE, **kw):
    raw=file_set(name,**kw);struct.pack_into('<H',raw,36,namehash(table,name));return bytes(seal(raw))

def directory(data,id=0,complete=True,root=True,offset=1000):
    assert len(data)%32==0
    return dict(id=str(id),root=root,complete=complete,records=[dict(offset=str(offset+i),bytes=data[i:i+32].hex()) for i in range(0,len(data),32)])

def request(data=b'',names=(),*,table=TABLE,format='auto',complete=True,end=True,**changes):
    encoded=compress(table) if format!='literal' else literal(table)
    row=dict(table=encoded.hex(),checksum=str(checksum(encoded)),format=format,
             directories=[directory(data+(bytes(32) if end else b''),complete=complete)],
             queries=[dict(directory='0',units=list(map(str,n))) for n in names]);row.update(changes);return row

def run(rows):
    global CASE_COUNT
    before=copy.deepcopy(rows);data=''.join(json.dumps(r,separators=(',',':'))+'\n' for r in rows).encode()
    p=subprocess.run([str(ARGS.probe.resolve())],input=data,capture_output=True,timeout=100)
    assert p.returncode==0 and not p.stderr,(p.returncode,p.stderr.decode())
    values=[json.loads(line) for line in p.stdout.splitlines()];assert len(values)==len(rows);assert rows==before
    CASE_COUNT+=len(rows);RECORDS.append(dict(cases=len(rows),input_sha256=hashlib.sha256(data).hexdigest(),output_sha256=hashlib.sha256(p.stdout).hexdigest()))
    return values

def utf(text):return list(struct.unpack('<'+'H'*(len(text.encode('utf-16-le'))//2),text.encode('utf-16-le')))

class Namespace(unittest.TestCase):
    def assess(self,row):
        v=run([row])[0];self.assertNotIn('error',v,v);r=v['result']
        self.assertFalse(r['authorizes_effects']);self.assertFalse(r['physical_admission'])
        if not r.get('budget_exhausted'):self.assertEqual(bytes.fromhex(row['table']).hex(),v['map_original_hex'])
        return r

    def test_every_name_length_and_original_units(self):
        rows=[request(entry([0xe9]+[97]*(n-1)),[[0xc9]+[65]*(n-1)]) for n in range(1,256)]
        for n,v in enumerate(run(rows),1):
            r=v['result'];self.assertEqual('unique',r['queries'][0]['status']);e=r['entries'][0]
            self.assertEqual(list(map(str,[0xe9]+[97]*(n-1))),e['original_units'])
            self.assertEqual(str(namehash(TABLE,[0xe9]+[97]*(n-1))),e['calculated_name_hash'])
            self.assertEqual(rows[n-1]['directories'][0]['records'][0]['offset'],e['source_record_offset'])
            self.assertEqual(entry([0xe9]+[97]*(n-1)).hex(),e['raw_set_hex'])

    def test_volume_rules_without_host_normalization(self):
        names=[utf('é'),utf('e\u0301'),utf('😀'),utf('Alpha')]
        r=self.assess(request(b''.join(entry(n) for n in names),[utf('É'),utf('E\u0301'),utf('😀'),utf('ALPHA')]))
        self.assertEqual(['unique']*4,[q['status'] for q in r['queries']]);self.assertEqual(4,len({q['entry_id'] for q in r['queries']}))

    def test_hash_collision_requires_full_comparison(self):
        seen={};pair=None
        for letters in itertools.product(range(65,91),repeat=3):
            h=namehash(TABLE,letters)
            if h in seen and seen[h]!=letters:pair=(seen[h],letters);break
            seen[h]=letters
        self.assertIsNotNone(pair)
        a,b=pair;self.assertEqual(namehash(TABLE,a),namehash(TABLE,b))
        r=self.assess(request(entry(a)+entry(b),[a,b]));self.assertEqual(['unique','unique'],[q['status'] for q in r['queries']])
        self.assertFalse(any(f['code']=='exfat_name_collision' for f in r['findings']))

    def test_case_collision_and_finding_omissions(self):
        data=entry(utf('alpha'))+entry(utf('ALPHA'))+entry(utf('AlPhA'))
        r=self.assess(request(data,[utf('alpha')],limits={'findings':'1'}))
        self.assertEqual('ambiguous',r['queries'][0]['status']);self.assertNotIn('entry_id',r['queries'][0])
        self.assertEqual('3',r['findings_total']);self.assertEqual('2',r['findings_omitted']);self.assertEqual(3,len(r['queries'][0]['observed_matches']))

    def test_partial_capture_never_establishes_absence_or_unique(self):
        name=utf('known')
        for kw in [dict(complete=False,end=False),dict(capture_applicable=False)]:
            r=self.assess(request(entry(name),[name,utf('missing')],**kw))
            self.assertEqual(['incomplete']*2,[q['status'] for q in r['queries']]);self.assertEqual(['1'],r['queries'][0]['observed_matches'])
        r=self.assess(request(entry(name),[utf('missing')],complete=False,end=True))
        self.assertEqual('not_found',r['queries'][0]['status'])

    def test_invalid_sets_and_orphans_preserve_raw_names(self):
        name=utf('known');variants=[]
        raw=bytearray(entry(name));raw[2]^=1;variants.append(bytes(raw))
        raw=bytearray(entry(name));raw[36]^=1;variants.append(bytes(seal(raw)))
        variants.extend([entry([0xd800]),entry([0]),entry([46]),entry(name,extra=[extension(0xc2)]),entry(name)[:-32]])
        for raw in variants:
            r=self.assess(request(raw,[name],end=False));self.assertEqual('incomplete',r['queries'][0]['status'])
            self.assertEqual(raw.hex(),r['entries'][0]['raw_set_hex'])
        for kind in [0xc0,0xc1,0xc2,0xe2,0x80,0x86]:
            raw=bytes([kind])+bytes(31);r=self.assess(request(raw,[name]));self.assertEqual('incomplete',r['queries'][0]['status'])

    def test_stream_and_timestamp_validity_are_separate(self):
        name=utf('known');raw=bytearray(entry(name));raw[8:12]=bytes(4);raw=bytes(seal(raw))
        r=self.assess(request(raw,[name]));self.assertFalse(r['entries'][0]['metadata_valid']);self.assertTrue(r['entries'][0]['name_usable']);self.assertEqual('unique',r['queries'][0]['status'])
        r=self.assess(request(entry(name,cluster=5000),[name]));self.assertFalse(r['entries'][0]['stream_valid']);self.assertEqual('unique',r['queries'][0]['status'])

    def test_map_ambiguity_invalid_and_explicit_selection(self):
        m=mapping();m[128:130]=[65535,2];raw=literal(m)
        row=request(entry([128],m),[[128]]);row.update(table=raw.hex(),checksum=str(checksum(raw)))
        r=self.assess(row);self.assertFalse(r['map_valid']);self.assertEqual('ambiguous',r['map']['selection']);self.assertEqual('incomplete',r['queries'][0]['status'])
        row['format']='literal';r=self.assess(row);self.assertEqual('unique',r['queries'][0]['status'])
        row['checksum']=str(checksum(raw)^1);r=self.assess(row);self.assertFalse(r['map_valid']);self.assertEqual('incomplete',r['queries'][0]['status'])
        m=mapping();raw=literal(m);row=request(entry([65],m),[[65]]);row.update(table=raw.hex(),checksum=str(checksum(raw)))
        r=self.assess(row);self.assertEqual('equivalent',r['map']['selection'])

    def test_map_and_namespace_resource_bounds(self):
        m=mapping();raw=literal(m)
        row=request(entry([65],m),[[65]]);row.update(table=raw.hex(),checksum=str(checksum(raw)),map_budget='393216')
        r=self.assess(row);self.assertFalse(r['map_valid']);self.assertEqual('exfat_retained_budget',r['map_diagnostic']);self.assertTrue(r['map']['candidates'][0]['evaluated']);self.assertFalse(r['map']['candidates'][1]['evaluated'])
        r=self.assess(request(entry([65])+entry([97]),[[65]],limits={'comparisons':'1'}));self.assertEqual('incomplete',r['queries'][0]['status']);self.assertTrue(r['budget_exhausted'])
        for limit in [{'records':'1'},{'output_bytes':'16384'}]:
            r=self.assess(request(b''.join(entry([65+i]) for i in range(20)),[[65]],limits=limit));self.assertTrue(r['budget_exhausted'])
            self.assertFalse(any(q.get('status') in ('unique','not_found') for q in r.get('queries',[])))

    def test_end_marker_root_records_and_independent_directories(self):
        a=entry(utf('alpha'));trailing=entry(utf('hidden'))
        r=self.assess(request(a+bytes(32)+trailing,[utf('hidden')]));self.assertEqual('not_found',r['queries'][0]['status']);self.assertEqual(1,len(r['entries']));self.assertEqual((len(a)+32+len(trailing))//32+1,len(r['directories'][0]['records']))
        for kind in [0x81,0x82,0x83]:
            row=request(bytes([kind])+bytes(31),[[65]]);r=self.assess(row);self.assertEqual('not_found',r['queries'][0]['status'])
            row['directories'][0]['root']=False;r=self.assess(row);self.assertEqual('incomplete',r['queries'][0]['status'])
        row=request(a,[utf('alpha')]);row['directories'].append(directory(a+bytes(32),id=1,root=False,offset=10000));row['queries'].append(dict(directory='1',units=list(map(str,utf('ALPHA')))))
        r=self.assess(row);self.assertEqual(['unique','unique'],[q['status'] for q in r['queries']]);self.assertNotEqual(r['queries'][0]['entry_id'],r['queries'][1]['entry_id'])

    def test_invalid_api_and_query_names(self):
        good=request(entry([65]),[[65]]);rows=[]
        for change in [dict(limits={'comparisons':'0'}),dict(limits={'records':'4097'}),dict(map_budget='0')]:
            v=copy.deepcopy(good);v.update(change);rows.append(v)
        v=copy.deepcopy(good);v['directories']*=2;rows.append(v)
        v=copy.deepcopy(good);v['directories'][0]['records'][1]['offset']=v['directories'][0]['records'][0]['offset'];rows.append(v)
        v=copy.deepcopy(good);v['directories'][0]['records'][0]['offset']=str((1<<64)-1);rows.append(v)
        v=copy.deepcopy(good);v['queries'][0]['units']=[];rows.append(v)
        self.assertTrue(all('error' in v for v in run(rows)))
        r=self.assess(request(entry([65]),[[0],[46],[46,46],[0xd800],[47]]));self.assertEqual(['query_rejected']*5,[q['status'] for q in r['queries']])

    def test_map_retention_and_directory_query_coverage(self):
        row=request(entry([65]),[[65]],map_budget='1')
        v=run([row])[0];self.assertFalse(v['original_retained']);r=v['result']
        self.assertFalse(r['map']['original_retained']);self.assertEqual('incomplete',r['queries'][0]['status'])
        self.assertEqual('sha256:'+hashlib.sha256(bytes.fromhex(row['table'])).hexdigest(),r['map']['original_sha256'])
        row=request(entry([65]),[[65]]);row['directories'].append(directory(entry([66])+bytes(32),id=1,root=False,offset=10000))
        row['queries'].append(dict(directory='1',units=['66']));row['limits']={'directories':'1'}
        r=self.assess(row);self.assertEqual(('2','1'),(r['directories_total'],r['directories_covered']))
        self.assertEqual('directory_not_observed',r['queries'][1]['status'])
        row=request(entry([65]),[[65],[66]],limits={'queries':'1'})
        r=self.assess(row);self.assertEqual(('2','1'),(r['queries_total'],r['queries_covered']))
        self.assertEqual('unique',r['queries'][0]['status'])

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Namespace))
    ARGS.output.write_text(json.dumps(dict(passed=result.wasSuccessful(),methods=result.testsRun,cases=CASE_COUNT,records=RECORDS),indent=2)+'\n',encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
