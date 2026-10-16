"""Actual held images, independent logical bytes and exact retained replay."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

parser = argparse.ArgumentParser()
parser.add_argument('--probe', type=Path, required=True)
parser.add_argument('--fault', type=Path, required=True)
parser.add_argument('--pure', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args, _ = parser.parse_known_args()
from test_exfat_tree import fixture, name
from test_exfat_file import file_digest, canonical

receipts = []
cases = 0


def run(row, fault=False):
    global cases
    payload = canonical([row])
    result = subprocess.run([str((args.fault if fault else args.probe).resolve())],
        input=payload, capture_output=True, timeout=100)
    assert result.returncode == 0 and not result.stderr, (result.returncode, result.stderr)
    value = json.loads(result.stdout)[0]
    assert value['fault_controls_available'] == fault
    cases += 1
    receipts.append(dict(input_sha256=hashlib.sha256(payload).hexdigest(),
        output_sha256=hashlib.sha256(result.stdout).hexdigest(), fault=fault))
    return value


class TreeFile(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='disked-tree-file-')
        self.root = Path(self.temp.name).resolve()
        self.serial = 0

    def tearDown(self):
        self.temp.cleanup()

    def fixture(self, **options):
        volume, sparse, directories, clusters, expected = fixture(**options)
        self.serial += 1
        path = self.root / ('image-' + str(self.serial) + '.img')
        with path.open('xb') as stream:
            stream.truncate(int(sparse['source_bytes']))
            for region in sparse['regions']:
                stream.seek(int(region['offset']))
                stream.write(bytes.fromhex(region['hex']))
        row = dict(tree=True, path=str(path), offset=sparse['offset'], length=sparse['length'],
            upcase_format='auto')
        return volume, sparse, row, path, expected

    def observe(self, row, path, fault=False):
        before = file_digest(path)
        value = run(row, fault)
        self.assertEqual(before, file_digest(path))
        self.assertFalse(Path(str(path) + '.rename-probe').exists())
        return value

    def assert_bound(self, value):
        result = value['result']
        self.assertEqual(result['schema'], 'org.disked.exfat-tree-file/1')
        self.assertFalse(result['authorizes_effects'])
        self.assertFalse(result['product_dispatch_admitted'])
        capture = result['capture']
        self.assertFalse(capture['atomic_snapshot'])
        self.assertFalse(capture['current_source_authority'])
        self.assertTrue(capture['metadata_equal'])
        self.assertTrue(capture['replay_equal'])
        self.assertTrue(capture['applicability_replay_ok'])
        self.assertEqual(capture['applicability_replay_count'], str(len(capture['applicability'])))

    def test_actual_nested_allocations_and_retained_pure_replay(self):
        for contiguous in [False, True]:
            for copies, active in [(1, 0), (2, 0), (2, 1)]:
                volume, sparse, row, path, expected = self.fixture(contiguous=contiguous,
                    copies=copies, active=active, offset=65536)
                value = self.observe(row, path)
                self.assert_bound(value)
                result = value['result']
                self.assertTrue(result['capture']['observed_stable'])
                self.assertTrue(result['observation']['complete'])
                alpha = next(e for e in result['observation']['entries']
                    if e['entry']['original_units'] == list(map(str, name('alpha'))))
                self.assertEqual(alpha['content_hex'], expected.hex())
                self.assertEqual(alpha['content_sha256'], 'sha256:' + hashlib.sha256(expected).hexdigest())
                pure = copy.deepcopy(sparse)
                capture = result['capture']
                pure.update(source_id=capture['source_identity_digest'], epoch=capture['sequence'],
                    source_bytes=capture['source_before']['bytes'], upcase_format='auto',
                    regions=[dict(offset=r['offset'], hex=r['bytes']) for r in value['regions']])
                pure.pop('compressed', None)
                replay = subprocess.run([str(args.pure.resolve())], input=canonical([pure]),
                    capture_output=True, timeout=100)
                self.assertEqual(replay.returncode, 0, replay.stderr)
                self.assertEqual(json.loads(replay.stdout)[0]['observation'], result['observation'])
                self.assertEqual(len(value['regions']), int(result['observation']['read_requests']))

    def test_valid_data_length_and_undefined_tail_exclusion(self):
        for valid in [0, 1, 511, 512, 513, 699, 700]:
            _, _, row, path, expected = self.fixture(valid=valid)
            value = self.observe(row, path)
            self.assert_bound(value)
            alpha = next(e for e in value['result']['observation']['entries']
                if e['entry']['original_units'] == list(map(str, name('alpha'))))
            self.assertEqual(alpha['content_hex'], expected.hex())
            self.assertEqual(alpha['source_data_bytes'], str(valid))
            self.assertEqual(alpha['defined_zero_bytes'], str(700 - valid))

    def test_actual_held_source_excludes_write_delete_and_rename(self):
        _, _, row, path, _ = self.fixture()
        row.update(mode='held_access', call='1')
        value = self.observe(row, path, True)
        self.assert_bound(value)
        self.assertEqual(len(value['held_access']), 3)
        self.assertTrue(all(r['error'] == '32' for r in value['held_access']))
        self.assertTrue(all(not r.get('opened', False) and not r.get('rename_succeeded', False)
            for r in value['held_access']))

    def test_read_metadata_binding_and_cancellation_failures(self):
        for mode, call in [('short', 1), ('error', 1), ('changed', 1), ('throw', 1),
                           ('metadata', 1), ('binding', 10), ('cancel', 10), ('cancel_throw', 10)]:
            _, _, row, path, _ = self.fixture()
            row.update(mode=mode, call=str(call))
            value = self.observe(row, path, True)
            self.assertNotIn('refusal', value, (mode, value))
            self.assertFalse(value['result']['capture']['observed_stable'], (mode, value))
            self.assertFalse(value['result']['observation']['complete'], (mode, value))
            self.assertTrue(value['result']['observation']['diagnostics'], (mode, value))

    def test_replay_read_and_applicability_mismatch_withdraws_stability(self):
        for mode in ['replay_bytes', 'replay_offset', 'replay_applicability']:
            _, _, row, path, _ = self.fixture()
            row.update(mode=mode, call='1')
            value = self.observe(row, path, True)
            self.assertFalse(value['result']['capture']['replay_equal'])
            self.assertFalse(value['result']['capture']['observed_stable'])
            self.assertFalse(value['result']['observation']['complete'])

    def test_limits_and_invalid_controls_before_open(self):
        for field, limit in [('directories', 1), ('records', 4), ('read_requests', 3),
                             ('read_bytes', 512), ('retained_bytes', 64), ('content_bytes', 10)]:
            _, _, row, path, _ = self.fixture()
            row['tree_limits'] = {field: str(limit)}
            value = self.observe(row, path)
            self.assertFalse(value['result']['observation']['complete'], field)
        for field, limit in [('directories', 257), ('read_requests', 0), ('output_bytes', 1)]:
            row = dict(tree=True, path=str(self.root / 'missing.img'), offset='0', length='512',
                upcase_format='auto', tree_limits={field: str(limit)})
            self.assertEqual(run(row)['refusal'], 'exfat_tree_inputs')

    def test_expected_source_and_limit_mutation_cannot_weaken_inputs(self):
        _, _, row, path, _ = self.fixture()
        first = self.observe(row, path)
        expected = first['result']['capture']['source_before']
        matched = dict(row, expected_source=expected)
        self.assert_bound(self.observe(matched, path))
        wrong = copy.deepcopy(expected)
        wrong['bytes'] = '1'
        for tree in [False, True]:
            changed = dict(row, tree=tree, expected_source=wrong, replace_expected_with=expected,
                mode='mutate_expected', call='1')
            self.assertEqual(self.observe(changed, path, True)['refusal'], 'exfat_file_source_changed')
        limited = dict(row, tree_limits={'content_bytes': '10'}, mode='mutate_limits', call='1')
        value = self.observe(limited, path, True)
        self.assertFalse(value['result']['observation']['complete'])
        self.assertIn('exfat_tree_content_budget', value['result']['observation']['diagnostics'])

    def test_invalid_windows_and_nonordinary_sources_refuse_without_changes(self):
        _, _, row, path, _ = self.fixture()
        before = file_digest(path)
        alias = self.root / 'same-image.img'
        os.link(path, alias)
        self.assertEqual(run(row)['refusal'], 'image_file_aliases')
        alias.unlink()
        for changed in [dict(row, path=str(self.root)),
                        dict(row, path=str(self.root / 'missing.img')),
                        dict(row, offset=str(2**63), length='512'),
                        dict(row, offset='0', length=str(2**64 - 1)),
                        dict(row, length=str(path.stat().st_size + 1)),
                        dict(row, upcase_format='not-an-encoding')]:
            self.assertIn('refusal', run(changed))
        self.assertEqual(before, file_digest(path))


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TreeFile))
    args.output.write_text(json.dumps(dict(passed=result.wasSuccessful(), cases=cases,
        methods=result.testsRun, receipts=receipts), indent=2) + '\n', encoding='utf8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
