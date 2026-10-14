"""Actual owned exFAT reader processes, strict frames and finite retirement."""
import argparse
import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from test_exfat_capture import Volume
from test_exfat_file import write, file_digest, digest, canonical

PROBE = FAULT = None
RECEIPTS = []
RETIREMENT_SAMPLES = []


def run(row, fault=False):
    data = canonical(row) + b'\n'
    result = subprocess.run([str(FAULT if fault else PROBE)], input=data, capture_output=True, timeout=35)
    assert result.returncode == 0 and not result.stderr, (result.returncode, result.stderr[:3000])
    values = result.stdout.splitlines()
    assert len(values) == 1
    RECEIPTS.append(dict(fault=fault, input_sha256=digest(data), exit_code=0))
    return json.loads(values[0])


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='disked-exfat-worker-')
        self.root = Path(self.temp.name).resolve()
        self.index = 0

    def tearDown(self):
        self.temp.cleanup()

    def fixture(self, volume=None):
        volume = volume or Volume(offset=173)
        self.index += 1
        path = self.root / f'generated-{self.index}.img'
        write(volume, path)
        return volume, path, dict(path=str(path), offset=str(volume.offset), length=str(volume.length),
                                 compressed=volume.compressed, capture_epoch='77')

    def preserve(self, path, row, fault=False):
        before = file_digest(path)
        out = run(row, fault)
        self.assertEqual(before, file_digest(path))
        return out

    def retired(self, out):
        state = out['retirement']
        self.assertEqual('exited', state['worker']['observation'], state)
        self.assertTrue(state['retired'], state)
        self.assertNotEqual('259', state['worker']['exit_code'], state)

    def test_real_profiles_typed_context_and_immutable_retention(self):
        for copies, active, compressed in [(1, 0, True), (2, 0, True), (2, 1, True), (1, 0, False)]:
            v, path, row = self.fixture(Volume(copies=copies, active=active, compressed=compressed, offset=173))
            out = self.preserve(path, row)
            self.assertNotIn('error', out)
            self.assertTrue(out['has_snapshot'], out)
            self.assertTrue(out['retained_unchanged'])
            snapshot, frame, context = out['snapshot'], out['frame'], out['context']
            self.assertTrue(snapshot['observation']['applicable'])
            self.assertEqual('77', context['capture_epoch'])
            self.assertEqual(frame['process_id'], context['pid'])
            self.assertEqual(frame['process_created'], context['created'])
            self.assertEqual(snapshot['capture']['process_id'], context['pid'])
            self.assertEqual('ordinary-file-exfat', context['image_profile'])
            for key in ['attempt_id', 'worker_epoch', 'observer_epoch', 'request_digest', 'code_sha256', 'frame_sha256']:
                self.assertTrue(context[key])
            self.assertEqual(digest(canonical(frame)), context['frame_sha256'])
            self.assertFalse(snapshot['authorizes_effects'])
            self.retired(out)

    def test_passive_frame_input_and_raw_replay_refuse_tampering(self):
        _, path, row = self.fixture()
        frame_row = dict(row, mode='frame')
        out = self.preserve(path, frame_row)
        self.assertNotIn('error', out)
        original = out['frame']
        self.assertEqual(original['result'], out['verified'])
        source = original['result']['capture']['source_before']
        base = dict(row, mode='verify', expected_source=source)
        for change in ['epoch', 'input', 'claim', 'metadata', 'domain', 'process', 'row', 'raw', 'result', 'stable', 'parent']:
            changed = copy.deepcopy(original)
            if change == 'epoch': changed['capture_epoch'] = '78'
            elif change == 'input': changed['input']['volume_offset'] = '174'
            elif change == 'claim': changed['result']['authorizes_effects'] = True
            elif change == 'metadata': changed['result']['capture']['source_before']['bytes'] = '1'
            elif change == 'domain': changed['result']['capture']['capture_domain'] = 'sha256:' + '0' * 64
            elif change == 'process': changed['process_id'] = '1'
            elif change == 'row': changed['regions'][0]['offset'] = '0'
            elif change == 'raw': changed['regions'][0]['bytes'] = '00'
            elif change == 'result': changed['result']['observation']['applicable'] = False
            elif change == 'stable': changed['result']['capture']['observed_stable'] = False
            else: changed['result']['capture']['parent_generations'] = []
            reply = self.preserve(path, dict(base, replace=changed))
            self.assertIn('error', reply, (change, reply))
        for values in [dict(capture_epoch='0'), dict(offset=str((1 << 64) - 1)),
                       dict(fixture={'worker_fault': 'hang'}), dict(limits={'read_bytes': '0'})]:
            candidate = dict(row, **values)
            reply = self.preserve(path, candidate)
            self.assertIn('error', reply)

    def test_actual_forged_publications_do_not_create_snapshots(self):
        _, path, row = self.fixture()
        for fault in ['payload_changed', 'result_changed', 'receipt_changed', 'process_changed',
                       'domain_changed', 'row_changed', 'claims']:
            out = self.preserve(path, dict(row, fixture={'worker_fault': fault}), True)
            self.assertNotIn('error', out, out)
            self.assertFalse(out['has_snapshot'], (fault, out))
            self.assertEqual('unknown', out['before']['status'], (fault, out))
            self.retired(out)
        for fault in ['capture', 'worker', 'code', 'request', 'scope', 'host', 'observer', 'attempt',
                       'pid', 'created', 'shape', 'status', 'claims', 'schema', 'digest']:
            out = self.preserve(path, dict(row, fixture={'reply_fault': fault}), True)
            self.assertNotIn('error', out, out)
            self.assertFalse(out['has_snapshot'], (fault, out))
            self.retired(out)

    def test_startup_hangs_cancel_late_exit_and_confirmed_retirement(self):
        _, path, row = self.fixture()
        for fault in ['before_spawn', 'after_spawn', 'after_spawn_alloc']:
            out = self.preserve(path, dict(row, fixture={'startup_fault': fault}), True)
            self.assertIn('startup_error', out)
            if fault == 'before_spawn':
                self.assertTrue(out['never_launched'])
            else:
                self.assertFalse(out['never_launched'])
                self.retired(out)
        for fault in ['hang', 'late']:
            out = self.preserve(path, dict(row, mode='pending', fixture={'worker_fault': fault}), True)
            self.assertFalse(out['has_snapshot'], out)
            self.assertNotEqual('exited', out['before']['worker']['observation'])
            self.assertFalse(out['before']['retired'])
            self.retired(out)
        out = self.preserve(path, dict(row, fixture={'worker_fault': 'exit'}), True)
        self.assertFalse(out['has_snapshot'])
        self.retired(out)
        out = self.preserve(path, dict(row, cancel=True))
        self.assertFalse(out['has_snapshot'])
        self.retired(out)
        out = self.preserve(path, dict(row, fixture={'worker_fault': 'late'}), True)
        self.assertTrue(out['has_snapshot'])
        self.assertTrue(out['retained_unchanged'])
        self.retired(out)

    def test_expected_source_changes_and_partial_native_failure_claims(self):
        _, path, row = self.fixture()
        frame = self.preserve(path, dict(row, mode='frame'))['frame']
        expected = copy.deepcopy(frame['result']['capture']['source_before'])
        expected['written'] = '1'
        out = self.preserve(path, dict(row, expected_source=expected))
        self.assertFalse(out['has_snapshot'], out)
        self.retired(out)
        for mode in ['short', 'error', 'changed', 'metadata', 'binding']:
            out = self.preserve(path, dict(row, fixture={'capture_fault': mode}), True)
            self.assertNotIn('error', out)
            if out['has_snapshot']:
                self.assertFalse(out['snapshot']['observation']['applicable'])
                self.assertFalse(out['snapshot']['capture']['observed_stable'])
            self.retired(out)

    def test_zero_wait_retirement_tracks_actual_owned_exit(self):
        _, path, row = self.fixture()
        for _ in range(12):
            out = self.preserve(path, dict(row, mode='retire-zero', fixture={'worker_fault': 'hang'}), True)
            self.assertFalse(out['before']['retired'])
            self.assertEqual('running', out['before']['worker']['observation'])
            zero = out['zero_retirement']
            RETIREMENT_SAMPLES.append(dict(pid=zero['worker']['pid'], observation=zero['worker']['observation'], retired=zero['retired']))
            self.assertEqual(zero['worker']['observation'] == 'exited', zero['retired'], zero)
            self.retired(out)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--fault', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    PROBE, FAULT = args.probe, args.fault
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    args.output.write_text(json.dumps(dict(passed=result.wasSuccessful(), methods=result.testsRun,
        cases=len(RECEIPTS), receipts=RECEIPTS, zero_wait_samples=RETIREMENT_SAMPLES), indent=2) + '\n', encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
