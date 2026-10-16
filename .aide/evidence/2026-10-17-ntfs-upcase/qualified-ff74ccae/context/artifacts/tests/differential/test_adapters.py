"""Controls for evidence loss, unsafe fixture routing and bounded external runs."""
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'corpus'))
import partition_images as corpus
import observe_native as native
from compare import compare
if os.name == 'posix':
    import observe_external as external


class CorpusTests(unittest.TestCase):
    def test_deterministic_corpus_and_distinct_receipts(self):
        a, b = corpus.recipes(), corpus.recipes()
        self.assertEqual(a, b); self.assertEqual(len(a), 35)
        self.assertEqual(len({x['name'] for x in a}), len(a))
        a[0]['checks']['mbr.issues'] = -1
        self.assertEqual(b[0]['checks']['mbr.issues'], 0)

    def test_containment_and_tamper_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()/'corpus'; manifest = corpus.generate(root)
            case = manifest['cases'][0]; data = native.load_case(root, case)
            self.assertEqual(len(data), case['bytes'])
            altered = dict(case, file='../'+case['file'])
            with self.assertRaises(ValueError): native.load_case(root, altered)
            (root/case['file']).write_bytes(data[:-1]+b'!')
            with self.assertRaises(ValueError): native.load_case(root, case)

    @unittest.skipUnless(os.name == 'posix', 'Linux external fixture boundary')
    def test_symlink_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); (root/'real.img').write_bytes(b'123')
            (root/'link.img').symlink_to(root/'real.img')
            with self.assertRaises(ValueError):
                native.load_case(root, dict(file='link.img', bytes=3, sha256=corpus.digest(b'123')))

    def test_array_views_follow_observed_headers_with_budget(self):
        case = next(x for x in corpus.recipes() if x['name'] == 'gpt-valid')
        request = native.request(case['data'], case)
        self.assertEqual(len(bytes.fromhex(request['primary_array'])), 16384)
        data = bytearray(case['data']); data[512+72:512+80] = (1<<63).to_bytes(8, 'little')
        self.assertEqual(native.request(data, case)['primary_array'], '')
        data[512+80:512+84] = b'\xff'*4
        self.assertEqual(native.request(data, case)['primary_array'], '')

    def test_conflicting_candidates_remain_conflicting(self):
        fixture = dict(cases=[dict(name='conflict', common_projection=False)])
        primary = dict(role='primary', rows=[dict(slot=1, start=34, end=61)])
        backup = dict(role='backup', rows=[dict(slot=1, start=35, end=61)])
        observed = dict(observations=[dict(name='conflict', projection=dict(label='gpt', comparison=2,
                                  candidates=[primary, backup]))])
        tool = dict(name='conflict', kind='sfdisk-json', sha256='fixture', outcome='exited', exit_code=0,
                    stdout='raw', stderr='', projection=dict(label='gpt', rows=backup['rows'], fields=['slot', 'start', 'end']))
        before = copy.deepcopy(observed)
        result = compare(fixture, observed, dict(tool=dict(observations=[tool])))
        self.assertEqual(result['comparisons'][0]['matching_candidates'], ['backup'])
        self.assertEqual(observed, before); self.assertEqual(result['comparisons'][0]['native']['comparison'], 2)
        tool['projection'] = None
        result = compare(fixture, observed, dict(tool=dict(observations=[tool])))
        self.assertEqual(result['comparisons'][0]['discrepancy'], 'no_projection')
        self.assertEqual(result['comparisons'][0]['stdout'], 'raw')

    def test_disk_identity_is_not_ignored_when_rows_match(self):
        rows = [dict(slot=1, start=34, end=61)]
        candidates = [dict(role='primary', rows=rows, disk_uuid='a'), dict(role='backup', rows=rows, disk_uuid='b')]
        native_value = dict(observations=[dict(name='id', projection=dict(label='gpt', candidates=candidates, comparison=2))])
        record = dict(name='id', kind='sfdisk-json', sha256='fixture', outcome='exited', exit_code=0,
                      stdout='raw', stderr='', projection=dict(label='gpt', rows=rows, disk_uuid='a', fields=['slot','start','end']))
        result = compare(dict(cases=[dict(name='id', common_projection=False)]), native_value, dict(tool=dict(observations=[record])))
        self.assertEqual(result['comparisons'][0]['matching_candidates'], ['primary'])


@unittest.skipUnless(os.name == 'posix', 'Installed Linux tool runner')
class ExternalTests(unittest.TestCase):
    def test_exit_zero_with_invalid_json_is_not_a_projection(self):
        for text in ['warning\n{}', '{"name":"\\xed\\xa0\\x80"}', '{}']:
            self.assertIsNone(external.normalize(dict(exit_code=0, outcome='exited', stdout=text), 'sfdisk-json', Path('/fixture.img')))

    def test_timeout_is_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = external.run([sys.executable, '-c', 'import time; time.sleep(2)'], Path(tmp), timeout=0.1)
            self.assertEqual(result['outcome'], 'timeout'); self.assertNotEqual(result['exit_code'], 0)

    def test_closed_output_streams_do_not_end_the_process_deadline(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = external.run([sys.executable, '-c', 'import os,time; os.close(1); os.close(2); time.sleep(5)'],
                                  Path(tmp), timeout=0.1)
            self.assertEqual(result['outcome'], 'timeout'); self.assertNotEqual(result['exit_code'], 0)
            self.assertLess(result['elapsed_seconds'], 3)

    def test_output_limit_is_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = external.run([sys.executable, '-c', 'import os; os.write(1,b"A"*8192)'], Path(tmp), output_limit=1024)
            self.assertEqual(result['outcome'], 'output_limit'); self.assertEqual(len(result['stdout']), 1024)

    def test_invalid_utf8_retains_exact_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = external.run([sys.executable, '-c', 'import os; os.write(1,bytes([237,160,128]))'], Path(tmp))
            self.assertEqual(result['stdout_bytes_hex'], 'eda080')
            self.assertEqual(result['stdout_sha256'], corpus.digest(bytes.fromhex('eda080')))

    def test_nonzero_exit_not_successful_table(self):
        value = dict(exit_code=1, outcome='exited', stdout=json.dumps(dict(partitiontable=dict(label='gpt', partitions=[]))))
        self.assertIsNone(external.normalize(value, 'sfdisk-json', Path('/fixture.img')))

    def test_unknown_units_are_not_compared_as_512_byte_sectors(self):
        for unit, size in [('bytes', 512), ('sectors', 4096), ('sectors', None)]:
            value = dict(exit_code=0, outcome='exited', stdout=json.dumps(dict(partitiontable=dict(
                label='gpt', unit=unit, sectorsize=size, partitions=[]))))
            self.assertIsNone(external.normalize(value, 'sfdisk-json', Path('/fixture.img')))

    def test_malformed_structured_output_is_retained_without_projection(self):
        values = [None, [], {'label':'gpt','unit':'sectors','sectorsize':512,'partitions':None},
                  {'label':'gpt','unit':'sectors','sectorsize':512,'partitions':[{'node':'/fixture.img1','start':True,'size':2}]},
                  {'label':'gpt','unit':'sectors','sectorsize':512,'id':None,'partitions':[]}]
        for table in values:
            value = dict(exit_code=0, outcome='exited', stdout=json.dumps(dict(partitiontable=table)))
            self.assertIsNone(external.normalize(value, 'sfdisk-json', Path('/fixture.img')))


if __name__ == '__main__': unittest.main()
