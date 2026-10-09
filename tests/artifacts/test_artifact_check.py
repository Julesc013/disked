"""Owned staging/ZIP fixtures for independent artifact completeness checks."""
import argparse
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile
import zlib

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('disked_artifact_check',ROOT/'tools/release/artifact_check.py');check=importlib.util.module_from_spec(spec);sys.modules[spec.name]=check;spec.loader.exec_module(check)

class Artifacts(unittest.TestCase):
    def setUp(self):
        base=ROOT/'.aide-local/artifact-tests';base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=base);self.work=Path(self.temp.name).resolve();assert self.work.is_relative_to(base.resolve())
        self.stage=self.work/'stage';self.stage.mkdir();(self.stage/'disked.exe').write_bytes(b'owned fixture executable bytes, never executed');(self.stage/'docs').mkdir();(self.stage/'docs/readme.txt').write_bytes(b'fixture documentation')
        self.expected=check.inventory(self.stage,['disked.exe']);self.archive=self.work/'product.zip'
    def tearDown(self):
        assert self.work.is_relative_to((ROOT/'.aide-local/artifact-tests').resolve());self.temp.cleanup()
    def zip(self,entries=None,compression=zipfile.ZIP_STORED):
        if entries is None:entries=[(x['path'],(self.stage/x['path']).read_bytes()) for x in self.expected['files']]
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',UserWarning)
            with zipfile.ZipFile(self.archive,'w',compression=compression) as z:
                for name,data in entries:z.writestr(name,data)
        return self.archive
    def denied(self,entries,code=None):
        self.zip(entries)
        with self.assertRaises(check.Rejected) as error:check.verify_zip(self.expected,self.archive)
        if code:self.assertEqual(str(error.exception),code)
    def test_matching_stored(self):
        out=check.verify_zip(self.expected,self.zip());self.assertTrue(out['completeness']);self.assertEqual(out['files'],'2');self.assertEqual(out['runtime'],'not_run');self.assertEqual(out['publication'],'not_run');self.assertEqual(out['authenticity'],'not_run');self.assertEqual(out['extraction'],'not_run')
    def test_matching_deflated(self):self.assertEqual(check.verify_zip(self.expected,self.zip(compression=zipfile.ZIP_DEFLATED))['status'],'pass')
    def test_many_output_chunks(self):
        (self.stage/'disked.exe').write_bytes(b'A'*(check.CHUNK*20+19));self.expected=check.inventory(self.stage,['disked.exe'])
        self.assertEqual(check.verify_zip(self.expected,self.zip(compression=zipfile.ZIP_DEFLATED))['status'],'pass')
    def test_empty_optional_file(self):
        (self.stage/'docs/empty').write_bytes(b'');self.expected=check.inventory(self.stage,['disked.exe'])
        for compression in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):
            with self.subTest(compression=compression):self.assertEqual(check.verify_zip(self.expected,self.zip(compression=compression))['status'],'pass')
    def test_optional_expected_directory(self):
        entries=[('docs/',b'')]+[(x['path'],(self.stage/x['path']).read_bytes()) for x in self.expected['files']];self.assertEqual(check.verify_zip(self.expected,self.zip(entries))['status'],'pass')
    def test_valid_but_empty(self):self.denied([],'archive_missing')
    def test_missing_required(self):self.denied([('docs/readme.txt',b'fixture documentation')],'archive_missing')
    def test_extra(self):self.denied([('unreviewed.exe',b'not executed')],'archive_extra')
    def test_duplicate(self):self.denied([('disked.exe',b'x'),('disked.exe',b'x')])
    def test_case_collision(self):
        entries=[('disked.exe',(self.stage/'disked.exe').read_bytes()),('DISKED.EXE',b'other')];self.denied(entries)
    def test_changed_same_size(self):self.denied([('disked.exe',b'x'*(self.stage/'disked.exe').stat().st_size)],'archive_content')
    def test_changed_size(self):self.denied([('disked.exe',b'x')],'archive_size')
    def test_extra_directory(self):self.denied([('unreviewed/',b'')],'archive_extra_directory')
    def test_directory_with_data(self):self.denied([('docs/',b'payload')],'archive_extra_directory')
    def test_unsafe_names(self):
        for name in ('../disked.exe','/disked.exe','C:/disked.exe','C:disked.exe','docs\\readme.txt','docs//readme.txt','./disked.exe','docs/../disked.exe','disked.exe:stream','NUL.txt','con','COM1.exe','LPT².txt','name.','name ','a\x1b[31m','a\x00tail','e\u0301.txt','name\u202etxt'):
            with self.subTest(name=repr(name)):self.denied([(name,b'x')])
    def test_archive_link_and_special_types(self):
        for mode in (stat.S_IFLNK,stat.S_IFIFO,stat.S_IFCHR,stat.S_IFBLK,stat.S_IFDIR):
            info=zipfile.ZipInfo('disked.exe');info.create_system=3;info.external_attr=(mode|0o644)<<16
            with self.subTest(mode=mode):self.denied([(info,b'x')],'archive_file_type')
    def test_dos_reparse_flag(self):
        info=zipfile.ZipInfo('disked.exe');info.external_attr=0x400;self.denied([(info,b'x')],'archive_file_type')
    def test_unknown_extra_field(self):
        info=zipfile.ZipInfo('disked.exe');info.extra=struct.pack('<HH',0xffff,0);self.denied([(info,b'x')],'archive_extra_field')
    def test_unsupported_compression(self):
        self.zip(compression=zipfile.ZIP_BZIP2)
        with self.assertRaises(check.Rejected) as error:check.verify_zip(self.expected,self.archive)
        self.assertEqual(str(error.exception),'archive_encoding')
    def test_zip64_local_headers(self):
        with zipfile.ZipFile(self.archive,'w') as z:
            for row in self.expected['files']:
                with z.open(row['path'],'w',force_zip64=True) as file:file.write((self.stage/row['path']).read_bytes())
        self.assertEqual(check.verify_zip(self.expected,self.archive)['status'],'pass')
    def test_zip64_end_record(self):
        self.zip();data=self.archive.read_bytes();offset=data.rfind(b'PK\x05\x06');end=data[offset:];fields=struct.unpack('<4s4H2IH',end)
        record=struct.pack('<4sQ2H2I4Q',b'PK\x06\x06',44,45,45,0,0,fields[4],fields[4],fields[5],fields[6]);locator=struct.pack('<4sIQI',b'PK\x06\x07',0,offset,1)
        end=struct.pack('<4s4H2IH',b'PK\x05\x06',0,0,65535,65535,0xffffffff,0xffffffff,0);self.archive.write_bytes(data[:offset]+record+locator+end)
        self.assertEqual(check.verify_zip(self.expected,self.archive)['status'],'pass')
    def test_deflate_failure(self):
        self.zip(compression=zipfile.ZIP_DEFLATED);data=bytearray(self.archive.read_bytes());offset=30+struct.unpack_from('<H',data,26)[0];data[offset]=0xff;self.archive.write_bytes(data)
        with self.assertRaises(check.Rejected):check.verify_zip(self.expected,self.archive)
    def test_hidden_uncompressed_tail(self):
        entries=[('disked.exe',(self.stage/'disked.exe').read_bytes()+b'undeclared generated tail'),('docs/readme.txt',(self.stage/'docs/readme.txt').read_bytes())]
        self.zip(entries,zipfile.ZIP_DEFLATED);data=bytearray(self.archive.read_bytes());crc=zlib.crc32((self.stage/'disked.exe').read_bytes());size=(self.stage/'disked.exe').stat().st_size
        struct.pack_into('<I',data,14,crc);struct.pack_into('<I',data,22,size);central=data.index(b'PK\x01\x02');struct.pack_into('<I',data,central+16,crc);struct.pack_into('<I',data,central+24,size);self.archive.write_bytes(data)
        with self.assertRaises(check.Rejected) as error:check.verify_zip(self.expected,self.archive)
        self.assertEqual(str(error.exception),'archive_size')
    def test_data_descriptors(self):
        class Stream(io.BytesIO):
            def seek(self,*args):raise io.UnsupportedOperation()
        stream=Stream()
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for row in self.expected['files']:z.writestr(row['path'],(self.stage/row['path']).read_bytes())
        self.archive.write_bytes(stream.getvalue());self.assertEqual(check.verify_zip(self.expected,self.archive)['status'],'pass')
    def descriptor_zip(self,wide=False):
        class Stream(io.BytesIO):
            def seek(self,*args):raise io.UnsupportedOperation()
        stream=Stream()
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for row in self.expected['files']:
                with z.open(row['path'],'w',force_zip64=wide) as file:file.write((self.stage/row['path']).read_bytes())
        self.archive.write_bytes(stream.getvalue())
    def test_zip64_data_descriptors(self):
        self.descriptor_zip(True);self.assertEqual(check.verify_zip(self.expected,self.archive)['status'],'pass')
    def test_unsigned_data_descriptors(self):
        for wide in (False,True):
            with self.subTest(wide=wide):
                self.descriptor_zip(wide);data=bytearray(self.archive.read_bytes());cut=data.index(b'PK\x07\x08');del data[cut:cut+4];end=data.rfind(b'PK\x05\x06');central=struct.unpack_from('<I',data,end+16)[0]-4;struct.pack_into('<I',data,end+16,central);other=data.index(b'PK\x01\x02',central+4);struct.pack_into('<I',data,other+42,struct.unpack_from('<I',data,other+42)[0]-4);self.archive.write_bytes(data)
                self.assertEqual(check.verify_zip(self.expected,self.archive)['status'],'pass')
    def test_descriptor_conflict(self):
        for wide in (False,True):
            with self.subTest(wide=wide):
                self.descriptor_zip(wide);data=bytearray(self.archive.read_bytes());offset=data.index(b'PK\x07\x08');data[offset+4]^=1;self.archive.write_bytes(data)
                with self.assertRaises(check.Rejected) as error:check.verify_zip(self.expected,self.archive)
                self.assertEqual(str(error.exception),'archive_descriptor')
    def test_local_zip64_conflict(self):
        with zipfile.ZipFile(self.archive,'w') as z:
            for row in self.expected['files']:
                with z.open(row['path'],'w',force_zip64=True) as file:file.write((self.stage/row['path']).read_bytes())
        data=bytearray(self.archive.read_bytes());offset=30+struct.unpack_from('<H',data,26)[0]+4;data[offset]^=1;self.archive.write_bytes(data)
        with self.assertRaises(check.Rejected) as error:check.verify_zip(self.expected,self.archive)
        self.assertEqual(str(error.exception),'archive_local_size')
    def test_unclaimed_bytes_before_central_directory(self):
        self.zip();data=bytearray(self.archive.read_bytes());end=data.rfind(b'PK\x05\x06');central=struct.unpack_from('<I',data,end+16)[0];gap=b'undeclared bytes';data[central:central]=gap;struct.pack_into('<I',data,end+len(gap)+16,central+len(gap));self.archive.write_bytes(data)
        with self.assertRaises(check.Rejected) as error:check.verify_zip(self.expected,self.archive)
        self.assertEqual(str(error.exception),'archive_record_layout')
    def test_compressed_suffix(self):
        self.zip(compression=zipfile.ZIP_DEFLATED);data=bytearray(self.archive.read_bytes());end=data.rfind(b'PK\x05\x06');central=struct.unpack_from('<I',data,end+16)[0];second=data.index(b'PK\x03\x04',4);gap=b'hidden compressed suffix';data[second:second]=gap;central+=len(gap);end+=len(gap)
        struct.pack_into('<I',data,18,struct.unpack_from('<I',data,18)[0]+len(gap));struct.pack_into('<I',data,central+20,struct.unpack_from('<I',data,central+20)[0]+len(gap));other=data.index(b'PK\x01\x02',central+4);struct.pack_into('<I',data,other+42,second+len(gap));struct.pack_into('<I',data,end+16,central);self.archive.write_bytes(data)
        with self.assertRaises(check.Rejected) as error:check.verify_zip(self.expected,self.archive)
        self.assertEqual(str(error.exception),'archive_compressed_tail')
    def test_parent_directory_budget(self):
        paths=['dir'+str(i)+'/nested/file' for i in range(check.MAX_FILES//2+1)]
        with self.assertRaises(check.Rejected) as error:check.closure(paths)
        self.assertEqual(str(error.exception),'directory_budget')
    def test_crc_failure(self):
        self.zip();data=bytearray(self.archive.read_bytes());offset=30+struct.unpack_from('<H',data,26)[0];data[offset]^=1;self.archive.write_bytes(data)
        with self.assertRaises(check.Rejected):check.verify_zip(self.expected,self.archive)
    def test_truncated_archive(self):
        self.zip();self.archive.write_bytes(self.archive.read_bytes()[:-1])
        with self.assertRaises(check.Rejected):check.verify_zip(self.expected,self.archive)
    def test_trailing_archive_bytes(self):
        self.zip();self.archive.write_bytes(self.archive.read_bytes()+b'trailing')
        with self.assertRaises(check.Rejected):check.verify_zip(self.expected,self.archive)
    def test_metadata_budget_before_zip_reader(self):
        self.zip();data=bytearray(self.archive.read_bytes());offset=data.rfind(b'PK\x05\x06');struct.pack_into('<I',data,offset+12,check.MAX_CENTRAL+1);self.archive.write_bytes(data)
        with self.assertRaises(check.Rejected) as error:check.verify_zip(self.expected,self.archive)
        self.assertEqual(str(error.exception),'archive_metadata_budget')
    def test_multidisk_refused(self):
        self.zip();data=bytearray(self.archive.read_bytes());struct.pack_into('<H',data,data.rfind(b'PK\x05\x06')+4,1);self.archive.write_bytes(data)
        with self.assertRaises(check.Rejected):check.verify_zip(self.expected,self.archive)
    def test_local_name_conflict(self):
        self.zip();data=bytearray(self.archive.read_bytes());data[30]^=1;self.archive.write_bytes(data)
        with self.assertRaises(check.Rejected):check.verify_zip(self.expected,self.archive)
    def test_encryption_refused(self):
        self.zip();data=bytearray(self.archive.read_bytes());struct.pack_into('<H',data,6,1);offset=data.index(b'PK\x01\x02');struct.pack_into('<H',data,offset+8,1);self.archive.write_bytes(data)
        with self.assertRaises(check.Rejected):check.verify_zip(self.expected,self.archive)
    def test_inventory_contract(self):
        mutations=[lambda x:x.update(extra=True),lambda x:x.update(files=[]),lambda x:x.update(required_entrypoints=[]),lambda x:x['files'][0].update(bytes='01'),lambda x:x['files'][0].update(bytes=True),lambda x:x['files'][0].update(bytes=str(check.MAX_FILE+1)),lambda x:x['files'][0].update(sha256='other'),lambda x:x['files'].append(copy.deepcopy(x['files'][0])),lambda x:x['files'].reverse(),lambda x:x.update(required_entrypoints=['missing.exe']),lambda x:x['files'][0].update(type='link')]
        for change in mutations:
            value=copy.deepcopy(self.expected);change(value)
            with self.subTest(change=mutations.index(change)),self.assertRaises(check.Rejected):check.validate_inventory(value)
    def test_inventory_parent_case_collision(self):
        value=copy.deepcopy(self.expected);value['files'].append(dict(path='DOCS/other.txt',type='regular',bytes='1',sha256=check.digest(b'x')));value['files'].sort(key=lambda x:x['path'])
        with self.assertRaises(check.Rejected):check.validate_inventory(value)
    def test_file_directory_collision(self):
        with self.assertRaises(check.Rejected):check.closure(['a','a/b'])
    def test_source_namespace_refusal(self):
        for path in ('\\\\.\\PhysicalDrive99','\\\\?\\GLOBALROOT\\Device\\example','\\\\server\\share\\file.zip','file.zip:stream'):
            with self.subTest(path=path),self.assertRaises(check.Rejected):check.local_source(path)
    def test_inventory_byte_budget(self):
        p=self.work/'large.json';p.write_bytes(b' '*(check.MAX_JSON+1))
        with self.assertRaises(check.Rejected) as error:check.load_inventory(p)
        self.assertEqual(str(error.exception),'inventory_budget')
    def test_archive_byte_budget_before_reads(self):
        with self.assertRaises(check.Rejected) as error:check.preflight(object(),check.MAX_ARCHIVE+1)
        self.assertEqual(str(error.exception),'archive_budget_or_format')
    def test_empty_staging_directory(self):
        (self.stage/'empty').mkdir()
        with self.assertRaises(check.Rejected):check.inventory(self.stage,['disked.exe'])
    def test_staging_hardlink(self):
        os.link(self.stage/'disked.exe',self.work/'hardlink')
        with self.assertRaises(check.Rejected):check.inventory(self.stage,['disked.exe'])
    def test_staging_budgets(self):
        for limit in ('MAX_FILES','MAX_FILE','MAX_TOTAL'):
            with self.subTest(limit=limit),patch.object(check,limit,1),self.assertRaises(check.Rejected) as error:check.inventory(self.stage,['disked.exe'])
            self.assertEqual(str(error.exception),'staging_budget')
    def test_source_changes_during_read(self):
        original=check.hash_file
        def change(file,size):
            result=original(file,size);(self.stage/'docs/readme.txt').write_bytes(b'changed while file open');return result
        with patch.object(check,'hash_file',change),self.assertRaises(check.Rejected):check.inventory(self.stage,['disked.exe'])
    def test_inventory_json_duplicate_key(self):
        p=self.work/'expected.json';p.write_bytes(b'{"schema":"x","schema":"y"}')
        with self.assertRaises(check.Rejected):check.load_inventory(p)
    def test_cli_no_clobber_or_inside_staging(self):
        out=self.work/'expected.json';out.write_bytes(b'keep')
        for dest in (out,self.stage/'new.json'):
            p=subprocess.run([sys.executable,str(ROOT/'tools/release/artifact_check.py'),'inventory','--staging',str(self.stage),'--required','disked.exe','--output',str(dest)],capture_output=True)
            self.assertEqual(p.returncode,1);self.assertEqual(json.loads(p.stdout)['status'],'fail')
        self.assertEqual(out.read_bytes(),b'keep');self.assertFalse((self.stage/'new.json').exists())
    def test_cli_complete_flow(self):
        out=self.work/'expected.json';tool=ROOT/'tools/release/artifact_check.py'
        p=subprocess.run([sys.executable,str(tool),'inventory','--staging',str(self.stage),'--required','disked.exe','--output',str(out)],capture_output=True);self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        p=subprocess.run([sys.executable,str(tool),'verify','--inventory',str(out),'--archive',str(self.zip())],capture_output=True);self.assertEqual(p.returncode,0,p.stdout+p.stderr);self.assertEqual(json.loads(p.stdout)['publication'],'not_run')

class Recording(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.records=[]
    def addSuccess(self,test):super().addSuccess(test);self.records.append(dict(name=test.id(),status='pass'))
    def addFailure(self,test,error):super().addFailure(test,error);self.records.append(dict(name=test.id(),status='fail'))
    def addError(self,test,error):super().addError(test,error);self.records.append(dict(name=test.id(),status='error'))
    def addSubTest(self,test,subtest,error):super().addSubTest(test,subtest,error);self.records.append(dict(name=str(subtest),status='fail' if error else 'pass'))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',type=Path);args=parser.parse_args()
    result=unittest.TextTestRunner(verbosity=2,resultclass=Recording).run(unittest.defaultTestLoader.loadTestsFromTestCase(Artifacts))
    if args.evidence:args.evidence.write_text(json.dumps(dict(passed=result.wasSuccessful(),tests=result.testsRun,skipped=len(result.skipped),observations=result.records,archive_execution=False,publication=False,authenticity=False),indent=2)+'\n',encoding='utf-8',newline='\n')
    return 0 if result.wasSuccessful() else 1
if __name__=='__main__':sys.exit(main())
