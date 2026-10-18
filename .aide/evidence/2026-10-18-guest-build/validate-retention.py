"""Bounded host coordinator checks; no guest, product or privileged API execution."""
import importlib.util
import io
import json
import os
from pathlib import Path
import tarfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
definition = importlib.util.spec_from_file_location('driver', HERE/'build-driver.py')
driver = importlib.util.module_from_spec(definition)
definition.loader.exec_module(driver)
WORK = Path(os.environ['DISKED_WORK_ROOT'])

def sharing(code):
    error = OSError('Simulated sharing denial')
    error.winerror = code
    return error

class Tests(unittest.TestCase):
    def setUp(self):
        self.work = WORK/self._testMethodName
        self.work.mkdir()

    def test_replies_requests_stderr_and_summary_survive_cleanup(self):
        expected = {'ntfs-a-cases'+suffix: (suffix+'\r\n').encode()
                    for suffix in ('.json','-response-0.json','-request-0.json','-response-0.stderr')}
        for name,data in expected.items():
            (self.work/name).write_bytes(data)
        other = self.work/'ntfs-b-cases.json'
        other.write_bytes(b'other-group')
        archive = driver.Observations(self.work/'observations.tar.xz')
        rows = driver.retain_test_outputs(archive,self.work,'ntfs-a-cases')
        self.assertEqual(len(rows),4)
        self.assertEqual(other.read_bytes(),b'other-group')
        self.assertFalse(list(self.work.glob('ntfs-a-cases*')))
        archive.close_verify()
        with tarfile.open(archive.path,'r:xz') as reader:
            self.assertEqual({m.name:reader.extractfile(m).read() for m in reader},
                             {'cases/'+n:b for n,b in expected.items()})

    def test_only_sharing_errors_are_retried(self):
        path = self.work/'log'
        with mock.patch.object(Path,'unlink',side_effect=[sharing(32),sharing(33),None]) as unlink, mock.patch.object(driver.time,'sleep'):
            self.assertEqual(driver.retire_file(path),2)
            self.assertEqual(unlink.call_count,3)
        with mock.patch.object(Path,'unlink',side_effect=PermissionError('denied')) as unlink, mock.patch.object(driver.time,'sleep') as sleep:
            with self.assertRaises(PermissionError): driver.retire_file(path)
            self.assertEqual(unlink.call_count,1)
            sleep.assert_not_called()

    def test_persistent_lock_expires(self):
        with mock.patch.object(Path,'unlink',side_effect=sharing(32)), mock.patch.object(driver.time,'monotonic',side_effect=[0,6]), mock.patch.object(driver.time,'sleep') as sleep:
            with self.assertRaises(OSError): driver.retire_file(self.work/'log')
            sleep.assert_not_called()

    def test_archive_is_not_duplicated_after_a_deletion_failure(self):
        path = self.work/'ntfs-a-cases.json'
        path.write_bytes(b'exact raw reply')
        archive = driver.Observations(self.work/'observations.tar.xz')
        with mock.patch.object(driver,'retire_file',side_effect=sharing(32)):
            with self.assertRaises(OSError): driver.retain_test_outputs(archive,self.work,'ntfs-a-cases')
        self.assertTrue(path.exists())
        driver.retain_test_outputs(archive,self.work,'ntfs-a-cases')
        archive.close_verify()
        with tarfile.open(archive.path,'r:xz') as reader:
            self.assertEqual(len(reader.getmembers()),1)

    def test_hard_link_output_is_refused_without_deleting_either_name(self):
        path = self.work/'other-data'
        path.write_bytes(b'preserve')
        linked = self.work/'ntfs-a-cases.json'
        os.link(path,linked)
        archive = driver.Observations(self.work/'observations.tar.xz')
        with self.assertRaisesRegex(RuntimeError,'linked/non-file'):
            driver.retain_test_outputs(archive,self.work,'ntfs-a-cases')
        self.assertEqual(path.read_bytes(),b'preserve')
        self.assertTrue(linked.exists())
        archive.close_verify()

    def published(self):
        stem='ntfs-a-cases'
        receipt={}
        for role,key in (('request','input'),('response','output'),('stderr','stderr')):
            path=self.work/(stem+'-'+role+'-0.json')
            path.write_bytes((role+' exact bytes\r\n').encode())
            receipt['raw_'+('input' if role=='request' else 'output' if role=='response' else role)]=str(path)
            receipt[key+'_sha256']='sha256:'+driver.sha(path)
        publication=self.work/(stem+'-raw-receipts.json')
        publication.write_text(json.dumps([receipt]))
        return stem,receipt,publication

    def test_only_published_closed_outputs_stream_and_roundtrip(self):
        stem,receipt,publication=self.published()
        pending=self.work/(stem+'-response-1.json');pending.write_bytes(b'not yet published')
        archive=driver.Observations(self.work/'observations.tar.xz')
        rows=driver.drain_completed_outputs(archive,self.work,stem)
        self.assertEqual(len(rows),3)
        self.assertTrue(pending.exists() and publication.exists())
        self.assertEqual(driver.drain_completed_outputs(archive,self.work,stem),[])
        archive.close_verify()
        with tarfile.open(archive.path,'r:xz') as reader:
            for role in ('input','output','stderr'):
                path=Path(receipt['raw_'+role])
                raw=reader.extractfile('cases/'+path.name).read()
                self.assertEqual('sha256:'+driver.hashlib.sha256(raw).hexdigest(),receipt[('input' if role=='input' else 'output' if role=='output' else role)+'_sha256'])

    def test_partial_receipt_is_deferred_only_while_producer_is_live(self):
        stem,receipt,publication=self.published()
        publication.write_text('[{')
        archive=driver.Observations(self.work/'observations.tar.xz')
        self.assertEqual(driver.drain_completed_outputs(archive,self.work,stem),[])
        with self.assertRaises(json.JSONDecodeError):driver.drain_completed_outputs(archive,self.work,stem,final=True)
        self.assertTrue(Path(receipt['raw_input']).exists())
        archive.close_verify()

    def test_receipt_cannot_escape_or_replace_published_bytes(self):
        stem,receipt,publication=self.published()
        archive=driver.Observations(self.work/'observations.tar.xz')
        outside=WORK/'other-project';outside.write_bytes(b'preserve')
        receipt['raw_input']=str(outside);publication.write_text(json.dumps([receipt]))
        with self.assertRaisesRegex(RuntimeError,'outside'):driver.drain_completed_outputs(archive,self.work,stem)
        self.assertEqual(outside.read_bytes(),b'preserve')
        receipt['raw_input']=str(self.work/(stem+'-request-0.json'));receipt['input_sha256']='sha256:'+'0'*64
        publication.write_text(json.dumps([receipt]))
        with self.assertRaisesRegex(RuntimeError,'differs'):driver.drain_completed_outputs(archive,self.work,stem)
        self.assertTrue(Path(receipt['raw_input']).exists())
        archive.close_verify()

stream = io.StringIO()
result = unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
record = dict(status='pass' if result.wasSuccessful() else 'fail',tests_run=result.testsRun,
              failures=len(result.failures),errors=len(result.errors),log=stream.getvalue(),
              scope='Ordinary temporary-file coordinator checks; no guest, product or privileged API execution',
              driver_sha256=driver.sha(HERE/'build-driver.py'))
(HERE/'retention-validation.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(record))
raise SystemExit(0 if result.wasSuccessful() else 1)
