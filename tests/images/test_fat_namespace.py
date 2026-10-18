"""Independent FAT alias/collision, native text API, callback and capture oracles."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from support.tempdir import fixture_parent,managed_directory
import unittest

import test_fat_capture as capture
from test_fat_capture import Volume, short, slots, code_units


def oem(base=b'FILE', extension=b'TXT'):
    assert 0 < len(base) <= 8 and len(extension) <= 3
    return base.ljust(8, b' ') + extension.ljust(3, b' ')


def entry(identity=1, stored=None, name=None, parent=0, **fields):
    value=dict(id=str(identity), parent=str(parent), short=(stored or oem()).hex(), **fields)
    if name is not None:
        value['long']=list(map(str, code_units(name) if isinstance(name,str) else name))
    return value


def query(name, directory=0):
    return dict(directory=str(directory), units=list(map(str,code_units(name) if isinstance(name,str) else name)))


def request(entries=(), queries=(), page=437, directories=None, **fields):
    return dict(op='namespace', namespace_code_page=str(page), entries=list(entries),
                directories=directories or [dict(id='0', complete=True)], namespace_queries=list(queries), **fields)


def direct(rows):
    outputs=capture.run(rows)
    return [r['namespace'] for r in outputs]


def names_in_capture(volume, queries=(), page=437, **fields):
    r=volume.request()
    r.update(namespace_code_page=str(page), namespace_queries=list(queries), **fields)
    return r


def decode_api(raw, page):
    """Independent Windows API caller over exact fixed fields, not production code."""
    api=ctypes.WinDLL('kernel32', use_last_error=True).MultiByteToWideChar
    api.argtypes=[wintypes.UINT,wintypes.DWORD,ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_int]
    api.restype=ctypes.c_int
    raw=bytes([0xe5 if raw[0]==5 else raw[0]])+raw[1:]
    result=[]
    for part in (raw[:8].rstrip(b' '),raw[8:].rstrip(b' ')):
        if not part:
            result.append([]); continue
        source=ctypes.create_string_buffer(part)
        target=(ctypes.c_uint16*16)()
        count=api(page,8,source,len(part),target,16)
        result.append(list(target[:count]) if count else None)
    if not result[0] or result[1] is None:return None
    return result[0]+([46]+result[1] if result[1] else [])


def equality_api(a,b):
    api=ctypes.WinDLL('kernel32', use_last_error=True).CompareStringOrdinal
    api.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_int,wintypes.BOOL]
    api.restype=ctypes.c_int
    left=(ctypes.c_uint16*len(a))(*a);right=(ctypes.c_uint16*len(b))(*b)
    value=api(left,len(a),right,len(b),True)
    assert value in (1,2,3)
    return value==2


class NamespaceTests(unittest.TestCase):
    def test_short_long_same_entry_and_case_aliases(self):
        fixture=request([entry(name='file.txt')],[query('FILE.TXT'),query('file.txt'),query('MISSING')])
        report=direct([fixture])[0]
        self.assertEqual([r['status'] for r in report['queries']],['unique','unique','not_found'])
        self.assertEqual(report['aliases'],'2');self.assertEqual(report['total_findings'],'0')
        self.assertEqual(report['queries'][0]['matches'],['1'])
        self.assertEqual(report['entries'][0]['stored_oem'],oem().hex())
        self.assertEqual(report['entries'][0]['original_long_units'],list(map(str,code_units('file.txt'))))
        self.assertFalse(report['storage_consumer_qualified']);self.assertFalse(report['authorizes_effects'])

    def test_cross_entry_collision_forms_and_exact_oem(self):
        rows=[request([entry(1,name='other.txt'),entry(2,oem(b'OTHER'),name='file.txt')],
                      [query('file.txt'),query('other.txt')]),
              request([entry(1),entry(2)],[query('file.txt')]),
              request([entry(1,name='same long'),entry(2,oem(b'SECOND'),name='SAME LONG')],[query('same long')])]
        cross,duplicate,long=direct(rows)
        self.assertTrue(all(q['status']=='ambiguous' for q in cross['queries']))
        forms={(f.get('first_form'),f.get('second_form')) for f in cross['findings']}
        self.assertIn(('short','long'),forms);self.assertIn(('long','short'),forms)
        self.assertIn('stored_oem_duplicate',[f['code'] for f in duplicate['findings']])
        self.assertEqual(long['queries'][0]['status'],'ambiguous')
        self.assertIn(('long','long'),{(f.get('first_form'),f.get('second_form')) for f in long['findings']})

    def test_directory_scope_and_excluded_or_unknown_records(self):
        dirs=[dict(id='0',complete=True),dict(id='3',complete=True)]
        rows=[request([entry(1),entry(2,parent=3)],[query('file.txt'),query('file.txt',3)],directories=dirs),
              request([entry(1,kind='excluded')],[query('file.txt')]),
              request([entry(1),entry(2,oem(b'OTHER'),kind='unknown')],[query('file.txt'),query('absent')]),
              request([entry(1)],[query('file.txt',4)])]
        scoped,excluded,unknown,missing=direct(rows)
        self.assertEqual([q['entry_id'] for q in scoped['queries']],['1','2'])
        self.assertEqual(scoped['findings'],[])
        self.assertEqual(excluded['queries'][0]['status'],'not_found')
        self.assertTrue(all(q['status']=='incomplete' for q in unknown['queries']))
        self.assertEqual(missing['queries'][0]['status'],'directory_not_observed')

    def test_windows_code_pages_and_dbcs_trail_byte(self):
        cases=[];stored_values=[]
        for page in (437,850,932):
            for stored in (oem(b'ASCII'),oem(b'\x82FILE'),oem(b'\x05FILE'),oem(b'\x81\x5cNAME')):
                decoded=decode_api(stored,page)
                # Fixed-format eligibility is checked separately; this case compares codec bytes/units.
                cases.append(request([entry(stored=stored)],page=page));stored_values.append((page,stored,decoded))
        for value,(page,stored,decoded) in zip(direct(cases),stored_values):
            form=value['entries'][0]['forms'][0]
            self.assertEqual(value['consumer_binding']['code_page'],str(page))
            self.assertEqual(value['entries'][0]['stored_oem'],stored.hex())
            if decoded is None:self.assertEqual(form['state'],'rejected')
            elif not any(n<=32 or n in (46,43,44,59,61,91,93) for n in decoded if n!=46):
                self.assertEqual(list(map(int,form['derived_units'])),decoded)
        self.assertEqual(decode_api(oem(b'\x82FILE'),437)[0],0xe9)
        self.assertEqual(decode_api(oem(b'\x81\x5cNAME'),932)[0],0x2015)
        dbcs=direct([request([entry(stored=oem(b'\x81\x5cNAME'))],[query('\u2015NAME.TXT')],page=932)])[0]
        self.assertEqual(dbcs['queries'][0]['status'],'unique')

    def test_reserved_and_invalid_components_remain_data(self):
        reserved=['.','..','CON','con.txt','PRN.data','AUX','NUL.bin','COM1','com9.ext','LPT1',
                  'COM\u00b9','LPT\u00b2.txt','COM\u00b3','CONIN$','CONOUT$', ' lead','trail ', 'trail.',
                  'a/b','a\\b','a:b','a?b','a*b','a<b','a>b','a|b','a"b','a\x00b','a\x1bb']
        values=direct([request([entry(name=name)],[query(name)]) for name in reserved])
        for name,value in zip(reserved,values):
            self.assertEqual(value['queries'][0]['status'],'query_rejected',name)
            self.assertEqual(value['entries'][0]['forms'][1]['state'],'rejected',name)
        allowed=['COM0','COM10','LPT0','CONSOLE','conx.txt','inside space','name+plus;ok=[]','\U0001f4be']
        for value in direct([request([entry(name=name)],[query(name)]) for name in allowed]):
            self.assertEqual(value['queries'][0]['status'],'unique')
        invalid=[[0xd800],[0xdc00],[0xd800,65],[65,0xdc00]]
        for value in direct([request([entry(name=n)],[query(n)]) for n in invalid]):
            self.assertEqual(value['queries'][0]['status'],'query_rejected')

    def test_fixed_short_fields_invalid_bytes_and_long_flags(self):
        raw=[oem(b'A B'),oem(b'A.B'),oem(b'A+B'),oem(b'A,B'),oem(b'A;B'),oem(b'A=B'),oem(b'A[B'),oem(b'A]B'),oem(b'\x81')]
        for value in direct([request([entry(stored=r)],page=932) for r in raw]):
            self.assertEqual(value['entries'][0]['forms'][0]['state'],'rejected')
        rows=[request([entry(name='A long',**{flag:False})],[query('A long'),query('FILE.TXT')])
              for flag in ('associated','unicode_valid','canonical')]
        for value in direct(rows):
            self.assertEqual([q['status'] for q in value['queries']],['not_found','unique'])
            self.assertEqual(value['entries'][0]['original_long_units'],list(map(str,code_units('A long'))))

    def test_ordinal_unicode_and_no_normalization(self):
        pairs=[('Alpha','ALPHA'),('\u00e9','\u00c9'),('\u00e9','e\u0301'),('\u00df','SS'),
               ('\u03c3','\u03a3'),('\u0131','I'),('a\U0001f4be','A\U0001f4be')]
        for (a,b),value in zip(pairs,direct([request([entry(name=a)],[query(b)]) for a,b in pairs])):
            expected='unique' if equality_api(code_units(a),code_units(b)) else 'not_found'
            self.assertEqual(value['queries'][0]['status'],expected,(a,b))
            self.assertEqual(value['consumer_binding']['normalization'],'none')
        self.assertFalse(equality_api(code_units('\u00e9'),code_units('e\u0301')))

    def test_independent_ascii_alias_oracle(self):
        # Expected candidate sets computed from original explicit ASCII aliases, independently of the native result.
        rows=[];oracles=[]
        for seed in range(16):
            entries=[];aliases={}
            for identity in range(1,13):
                base=f'N{(identity+seed)%7}'.encode();long=f'long {(identity*3+seed)%9}'
                entries.append(entry(identity,oem(base),long))
                for name in (base.decode()+'.TXT',long):aliases.setdefault(name.upper(),set()).add(str(identity))
            queries=[query(f'N{n}.txt') for n in range(7)]+[query(f'LONG {n}') for n in range(9)]
            rows.append(request(entries,queries));oracles.append(aliases)
        for value,oracle in zip(direct(rows),oracles):
            for q in value['queries']:
                key=''.join(chr(int(n)) for n in q['query_units']).upper();matches=oracle.get(key,set())
                self.assertEqual(set(q['matches']),matches)
                self.assertEqual(q['status'],'ambiguous' if len(matches)>1 else 'unique' if matches else 'not_found')

    def test_callback_faults_and_preflight_validation(self):
        faults=['equal_unknown','equal_throw','equal_invalid','nonreflexive','asymmetric',
                'decode_unknown','decode_throw','decode_invalid','component_unknown','component_throw','component_invalid']
        for value in direct([request([entry(1),entry(2,oem(b'OTHER'))],[query('file.txt'),query('absent')],consumer_fault=f) for f in faults]):
            self.assertTrue(all(q['status']=='incomplete' for q in value['queries']))
            self.assertTrue(all(not d['model_complete'] for d in value['directories']))
        rows=[request([entry()],consumer_fault=f) for f in ('missing_callback','invalid_identity','invalid_binding')]
        rows += [request([entry(1),entry(1)]),request([entry(parent=3)]),request([entry()],page=1252),
                 request([entry()],queries=[query('x',128)]),request([entry()],queries=[query([])]),
                 request([entry()],queries=[query('x'*256)]),request([entry()],queries=[query('x')]*17)]
        for row in capture.run(rows):self.assertIn('error',row)

    def test_coverage_applicability_and_each_budget(self):
        incomplete=request([entry()],[query('file.txt'),query('absent')],directories=[dict(id='0',complete=False)])
        not_applicable=request([entry()],[query('file.txt')],applicable=False)
        ambiguous=request([entry(1),entry(2)],[query('file.txt')],directories=[dict(id='0',complete=False)])
        for v in direct([incomplete,not_applicable]):self.assertTrue(all(q['status']=='incomplete' for q in v['queries']))
        self.assertEqual(direct([ambiguous])[0]['queries'][0]['status'],'ambiguous')
        limited=request([entry(1),entry(2)],[query('file.txt')],namespace_limits={'comparisons':'1'})
        value=direct([limited])[0];self.assertIn('namespace_comparison_budget',value['diagnostics'])
        self.assertEqual(value['queries'][0]['status'],'incomplete')
        limited=request([entry(n) for n in range(1,5)],[query('file.txt')],namespace_limits={'findings':'1'})
        value=direct([limited])[0];self.assertEqual(len(value['findings']),1)
        self.assertGreater(int(value['omitted_findings']),0);self.assertEqual(value['queries'][0]['status'],'ambiguous')
        limited=request([entry(n,oem(f'F{n}'.encode()),'X'*255) for n in range(1,128)],[query('FILE.TXT')],namespace_limits={'output_bytes':'16384'})
        value=direct([limited])[0];self.assertIn('namespace_output_budget',value['diagnostics'])
        self.assertLessEqual(len(json.dumps(value,separators=(',',':')).encode()),16384)
        self.assertTrue(all(q['status']!='unique' for q in value['queries']))
        for key,number in [('comparisons',0),('comparisons',65537),('findings',0),('findings',129),('output_bytes',16383),('output_bytes',524289)]:
            self.assertIn('error',capture.run([request(namespace_limits={key:str(number)})])[0])

    def test_capture_integration_partial_and_no_additional_reads(self):
        for bits in (12,16,32):
            volume=Volume(bits,offset=17);item=short();long,_=slots(code_units('A long name'),item)
            volume.directory([long,bytes(item)])
            plain,calls=capture.report(volume.request())
            value,name_calls=capture.report(names_in_capture(volume,[query('A long name'),query('FILE.TXT')]))
            self.assertEqual(name_calls,calls)
            model=value.pop('namespace');self.assertEqual(value,plain)
            self.assertEqual([q['status'] for q in model['queries']],['unique','unique'])
            partial,_=capture.report(names_in_capture(volume,[query('FILE.TXT')],limits={'records':'1'}))
            self.assertEqual(partial['namespace']['queries'][0]['status'],'incomplete')
            refused=capture.run([names_in_capture(volume,limits={'output_bytes':'786431'})])[0]
            self.assertIn('error',refused);self.assertEqual(refused['calls'],[])
        volume=Volume();volume.directory([bytes(short()),bytes(short(name=b'SECOND  TXT'))])
        request_row=names_in_capture(volume,[query('FILE.TXT')],limits={'nodes':'2'})
        value,_=capture.report(request_row);self.assertEqual(value['namespace']['queries'][0]['status'],'incomplete')

    def test_late_auxiliary_overlap_withdraws_lookup(self):
        from test_fat_auxiliary import MetadataVolume
        volume=MetadataVolume();volume.directory([bytes(short())])
        r=names_in_capture(volume,[query('FILE.TXT'),query('absent')],auxiliary_checks=True)
        good,calls=capture.report(r)
        self.assertEqual([q['status'] for q in good['namespace']['queries']],['unique','not_found'])
        # The optional 8-byte header read overlaps the earlier separate 4-byte FAT32 cells.
        table=volume.offset+volume.g['reserved']*volume.unit
        index=next(i for i,c in enumerate(calls,1) if int(c['offset'])==table and int(c['bytes'])==8)
        r['fault']=dict(call=str(index),kind='change');bad,_=capture.report(r)
        self.assertTrue(bad['selected_tree_complete']);self.assertFalse(bad['reads']['overlap_equal'])
        model=bad['namespace'];self.assertFalse(model['capture_applicable'])
        self.assertEqual([q['status'] for q in model['queries']],['incomplete','incomplete'])
        self.assertEqual(model['queries'][0]['matches'],['1']);self.assertNotIn('entry_id',model['queries'][0])

    def test_maximum_shapes_and_comparison_ceiling(self):
        directories=[dict(id=str(n),complete=True) for n in range(128)]
        value=direct([request(directories=directories,queries=[query('absent',127)])])[0]
        self.assertEqual(len(value['directories']),128);self.assertEqual(value['queries'][0]['status'],'not_found')
        entries=[entry(n,oem(f'F{n}'.encode()),f'Long {n}') for n in range(1,128)]
        value=direct([request(entries,[query('absent')]*16)])[0]
        self.assertEqual(value['comparison_calls'],'65536')
        self.assertIn('namespace_comparison_budget',value['diagnostics'])
        self.assertTrue(all(q['status']=='incomplete' for q in value['queries']))
        invalid=[request(entries+[entry(128)]),request(directories=directories+[dict(id='128',complete=True)]),
                 request(directories=[dict(id='0',complete=True)]*2)]
        for row in capture.run(invalid):self.assertIn('error',row)

    def test_ordinary_files_recapture_and_source_preservation(self):
        root=fixture_parent()
        with managed_directory(prefix='fatnames-') as folder:
            for bits in (12,16,32):
                volume=Volume(bits,offset=512);item=short();long,_=slots(code_units('Name.txt'),item)
                volume.directory([long,bytes(item)])
                path=Path(folder)/f'{bits}.img';volume.write(path);before=hashlib.sha256(path.read_bytes()).hexdigest()
                r=dict(op='file',path=str(path),offset='512',length=str(volume.length),copy='0',namespace_code_page='437',
                       namespace_queries=[query('Name.txt')])
                result=capture.run([r])[0]['result'];self.assertTrue(result['capture']['observed_stable'])
                self.assertEqual(result['observation']['namespace']['queries'][0]['status'],'unique')
                for flag in ('DISKED_FAT_TEST_VERIFY_CHANGED','DISKED_FAT_TEST_VERIFY_ERROR','DISKED_FAT_TEST_METADATA_CHANGED'):
                    env=os.environ.copy();env[flag]='1'
                    bad=capture.run([r],probe=capture.FAULT_PROBE,environment=env)[0]['result']
                    good=capture.run([r],environment=env)[0]['result']
                    self.assertFalse(bad['capture']['observed_stable']);self.assertTrue(good['capture']['observed_stable'])
                    model=bad['observation']['namespace'];self.assertFalse(model['capture_applicable'])
                    self.assertEqual(model['queries'][0]['status'],'incomplete');self.assertEqual(model['queries'][0]['matches'],['1'])
                    self.assertNotIn('entry_id',model['queries'][0]);self.assertEqual(good['observation']['namespace']['queries'][0]['status'],'unique')
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe',type=Path,required=True);parser.add_argument('--fault-probe',type=Path,required=True)
    parser.add_argument('--output',type=Path);args=parser.parse_args()
    capture.PROBE=args.probe.resolve();capture.FAULT_PROBE=args.fault_probe.resolve()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NamespaceTests))
    cases=sum(r['cases'] for r in capture.RECEIPTS)
    if args.output:args.output.write_text(json.dumps(dict(tests_run=result.testsRun,passed=result.wasSuccessful(),cases=cases,
        batches=capture.RECEIPTS),indent=2)+'\n',encoding='utf-8',newline='\n')
    print('FAT namespace cases executed: '+str(cases),flush=True)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__=='__main__':main()
