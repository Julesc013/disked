"""Actual disposable ordinary-image reads, retained replay and native refusals."""
import argparse
import copy
import hashlib
import json
import os
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from test_exfat_capture import Volume, source_bytes, Tests as CaptureOracle

PROBE = FAULT = None
RECEIPTS = []
UNVERIFIED = []


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def digest(value):
    return 'sha256:' + hashlib.sha256(value).hexdigest()


def file_digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1048576):
            value.update(block)
    return 'sha256:' + value.hexdigest()


def write(volume, path):
    with path.open('xb') as stream:
        stream.truncate(volume.offset + volume.length)
        for offset, raw in volume.regions().items():
            stream.seek(offset)
            stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def request(volume, path, **extra):
    return dict(path=str(path), offset=str(volume.offset), length=str(volume.length),
                compressed=volume.compressed, **extra)


def run(rows, fault=False, env=None):
    data = canonical(rows)
    result = subprocess.run([str(FAULT if fault else PROBE)], input=data, capture_output=True,
                            timeout=100, env=env)
    assert result.returncode == 0 and not result.stderr, (result.returncode, result.stderr[:3000])
    out = json.loads(result.stdout)
    assert len(out) == len(rows)
    RECEIPTS.append(dict(cases=len(rows), fault=fault, input_sha256=digest(data), exit_code=0))
    for value in out:
        assert value['fault_controls_available'] == fault
    return out


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='disked-exfat-owned-')
        self.root = Path(self.temp.name).resolve()
        self.index = 0

    def tearDown(self):
        self.temp.cleanup()

    def fixture(self, volume):
        self.index += 1
        path = self.root / f'generated-{self.index}.img'
        write(volume, path)
        return path

    def preserve(self, path, rows, fault=False, env=None):
        before = file_digest(path)
        size = path.stat().st_size
        out = run(rows, fault, env)
        renamed = Path(str(path) + '.rename-probe')
        if renamed.exists() and not path.exists():
            renamed.rename(path)
            self.fail('Source rename unexpectedly succeeded under held binding')
        self.assertEqual(before, file_digest(path))
        self.assertEqual(size, path.stat().st_size)
        return out

    def good(self, volume, path, extra=None, fault=False):
        row = request(volume, path, **(extra or {}))
        out = self.preserve(path, [row], fault)[0]
        self.assertNotIn('refusal', out)
        result = out['result']
        obs, capture = result['observation'], result['capture']
        self.assertTrue(obs['applicable'], out)
        self.assertTrue(obs['complete'])
        for key in ['metadata_equal', 'binding_checks_ok', 'replay_equal', 'observed_stable']:
            self.assertTrue(capture[key], (key, out))
        self.assertEqual(capture['source_before'], capture['source_after'])
        self.assertEqual(str(path.stat().st_size), capture['source_before']['bytes'])
        self.assertEqual('1', capture['source_before']['hardlinks'])
        self.assertEqual(digest(canonical(capture['source_before'])), capture['source_identity_digest'])
        self.assertEqual(capture['source_identity_digest'], obs['source_id'])
        self.assertEqual(capture['sequence'], obs['epoch'])
        self.assertGreater(int(capture['process_id']), 0)
        self.assertGreater(int(capture['process_created']), 0)
        domain = dict(provider='exfat-file-prototype', process_id=capture['process_id'],
                      process_created=capture['process_created'], sequence=capture['sequence'],
                      source=capture['source_before'])
        self.assertEqual(digest(canonical(domain)), capture['capture_domain'])
        self.assertFalse(result['authorizes_effects'])
        self.assertFalse(result['product_dispatch_admitted'])
        self.assertFalse(capture['atomic_snapshot'])
        self.assertEqual('live-uncoordinated', capture['source_consistency'])
        self.assertFalse(obs['current_source_authority'])
        self.assertTrue(capture['parent_generations'])
        self.assertEqual(digest(struct.pack('<65536H', *volume.table)), obs['upcase']['mapping_sha256'])
        trace = CaptureOracle().last_requests(volume.request())
        self.assertEqual([(r['offset'], r['bytes']) for r in trace],
                         [(r['offset'], r['requested']) for r in out['regions']])
        self.assertEqual(str(len(trace)), obs['read_requests'])
        for region in out['regions']:
            self.assertTrue(region['read_attempted'])
            self.assertEqual('0', region['error'])
            self.assertEqual('', region['refusal'])
            self.assertEqual(source_bytes(volume.request(), int(region['offset']), int(region['requested'])),
                             bytes.fromhex(region['bytes']))
        return out

    def test_actual_profiles_offsets_maps_and_exact_region_replay(self):
        for copies, active in [(1, 0), (2, 0), (2, 1)]:
            for compressed in [True, False]:
                v = Volume(copies=copies, active=active, compressed=compressed, offset=173)
                self.good(v, self.fixture(v))
        for shift, cluster_shift in [(10, 0), (12, 2)]:
            v = Volume(shift=shift, cluster_shift=cluster_shift, offset=33)
            self.good(v, self.fixture(v))
        v = Volume(clusters=4099)
        v.bitmap[-1] |= 0xf8
        self.good(v, self.fixture(v))

    def test_refusals_limits_windows_paths_and_actual_nonordinary_aliases(self):
        v = Volume()
        path = self.fixture(v)
        rows = [request(v, path, limits={name: '0'}) for name in ['read_bytes', 'read_requests', 'retained_bytes', 'records', 'clusters']]
        rows += [request(v, path, limits=dict(output_bytes='16383'))]
        for offset, length in [((1 << 63), 512), ((1 << 63) - 512, 1024), ((1 << 64) - 1, 512), (0, 0), (0, path.stat().st_size + 1)]:
            row = request(v, path)
            row.update(offset=str(offset), length=str(length))
            rows.append(row)
        out = self.preserve(path, rows)
        self.assertTrue(all('refusal' in result for result in out))
        for item in out:
            self.assertNotIn('regions', item)
        for value, code in [(str(self.root / 'missing.img'), 'exfat_file_open'),
                            (str(self.root), 'image_file_type'), ('NUL', 'image_path_profile'),
                            (str(path) + ':alternate', 'image_path_profile'),
                            (str(self.root / ('x' * 250 + '.img')), 'image_path_profile')]:
            row = request(v, path)
            row['path'] = value
            self.assertEqual(code, run([row])[0]['refusal'])
        alias = self.root / 'owned-hardlink.img'
        os.link(path, alias)
        try:
            self.assertEqual('image_file_aliases', self.preserve(path, [request(v, path)])[0]['refusal'])
        finally:
            alias.unlink()

    def test_actual_reparse_leaf_and_ancestor_when_available(self):
        v = Volume()
        target = self.root / 'owned-target'
        target.mkdir()
        path = target / 'image.img'
        write(v, path)
        link = self.root / 'owned-junction'
        result = subprocess.run(['cmd', '/d', '/c', 'mklink', '/J', str(link), str(target)], capture_output=True)
        self.assertEqual(0, result.returncode, result.stderr)
        try:
            row = request(v, link / 'image.img')
            self.assertEqual('image_reparse_source', self.preserve(path, [row])[0]['refusal'])
            self.assertEqual('image_reparse_source', self.preserve(path, [request(v, link)])[0]['refusal'])
        finally:
            os.rmdir(link)
        leaf = self.root / 'owned-link.img'
        try:
            os.symlink(path, leaf)
        except OSError as error:
            UNVERIFIED.append(dict(check='actual-file-symlink', reason=str(error)))
        else:
            try:
                self.assertEqual('image_reparse_source', self.preserve(path, [request(v, leaf)])[0]['refusal'])
            finally:
                leaf.unlink()

    def test_failure_prefixes_cancellation_binding_and_replay_disagreement(self):
        v = Volume()
        path = self.fixture(v)
        for mode, code in [('short', 'exfat_read_length'), ('error', 'exfat_reader_failure'),
                           ('throw', 'exfat_reader_failure'), ('changed', 'exfat_source_changed')]:
            out = self.preserve(path, [request(v, path, mode=mode, call='2')], True)[0]
            obs = out['result']['observation']
            self.assertFalse(obs['applicable'])
            self.assertIn(code, obs['diagnostics'])
            self.assertTrue(out['result']['capture']['replay_equal'])
            self.assertFalse(out['result']['capture']['observed_stable'])
            self.assertEqual(2, len(out['regions']))
        for mode in ['metadata', 'replay_bytes', 'replay_offset']:
            out = self.preserve(path, [request(v, path, mode=mode, call='1')], True)[0]
            self.assertFalse(out['result']['observation']['applicable'])
            self.assertIn('exfat_file_binding_disagreement', out['result']['observation']['diagnostics'])
            self.assertFalse(out['result']['capture']['observed_stable'])
            self.assertEqual(mode != 'metadata', out['result']['capture']['metadata_equal'])
            self.assertEqual(mode == 'metadata', out['result']['capture']['replay_equal'])
        for call in [1, 3, 15]:
            out = self.preserve(path, [request(v, path, mode='cancel', call=str(call))], True)[0]
            if call == 1:
                self.assertEqual('exfat_file_cancelled', out['refusal'])
                continue
            self.assertFalse(out['result']['observation']['applicable'])
            self.assertTrue(out['regions'])
            self.assertEqual('exfat_file_cancelled', out['regions'][-1]['refusal'])
            self.assertFalse(out['regions'][-1]['read_attempted'])
            self.assertTrue(out['result']['capture']['replay_equal'])
            self.assertEqual('exfat_file_cancelled', out['result']['capture']['binding_error'])
        normal = self.good(v, path)
        total = int(normal['result']['capture']['binding_checks'])
        for mode in ['binding', 'cancel']:
            out = self.preserve(path, [request(v, path, mode=mode, call=str(total))], True)[0]
            self.assertFalse(out['result']['observation']['applicable'])
            self.assertTrue(out['result']['observation']['complete'])
            self.assertTrue(out['result']['capture']['replay_equal'])
            self.assertFalse(out['result']['capture']['binding_checks_ok'])
            self.assertTrue(out['regions'])
        out = self.preserve(path, [request(v, path, mode='cancel_throw', call='3')], True)[0]
        self.assertFalse(out['result']['observation']['applicable'])
        self.assertEqual('exfat_file_cancel_callback', out['regions'][-1]['refusal'])
        self.assertFalse(out['regions'][-1]['read_attempted'])
        self.assertTrue(out['result']['capture']['replay_equal'])
        self.assertEqual('exfat_file_cancel_callback', out['result']['capture']['binding_error'])

    def test_actual_malformed_sources_and_native_budget_prefixes(self):
        for kind in ['checksum', 'missing_upcase', 'free_system_cluster', 'root_cycle']:
            v = Volume()
            if kind == 'checksum':
                v.boot[-1] ^= 1
                code = 'exfat_boot_invalid'
            elif kind == 'missing_upcase':
                v.records = [r for r in v.records if r[0] != 0x82]
                code = 'exfat_root_cardinality'
            elif kind == 'free_system_cluster':
                v.bitmap[0] &= ~1
                code = 'exfat_system_cluster_available'
            else:
                v.links[9] = 2
                code = 'exfat_chain_cycle'
            path = self.fixture(v)
            out = self.preserve(path, [request(v, path)])[0]
            self.assertFalse(out['result']['observation']['applicable'])
            self.assertIn(code, out['result']['observation']['diagnostics'])
            self.assertTrue(out['result']['capture']['replay_equal'])
            self.assertFalse(out['result']['capture']['observed_stable'])
        v = Volume()
        path = self.fixture(v)
        for name, value, code in [('read_requests', 1, 'exfat_read_budget'), ('read_bytes', 512, 'exfat_read_budget'),
                                  ('retained_bytes', 512, 'exfat_retained_budget'), ('clusters', 1, 'exfat_chain_budget'),
                                  ('records', 1, 'exfat_record_budget')]:
            out = self.preserve(path, [request(v, path, limits={name: str(value)})])[0]
            self.assertFalse(out['result']['observation']['applicable'])
            self.assertEqual([code], out['result']['observation']['diagnostics'])
            self.assertTrue(out['result']['capture']['replay_equal'])
            self.assertEqual(len(out['regions']), int(out['result']['observation']['read_requests']))

    def test_held_write_delete_and_rename_access_is_denied(self):
        v = Volume()
        path = self.fixture(v)
        out = self.good(v, path, dict(mode='held_access', call='2'), True)
        self.assertEqual(3, len(out['held_access']))
        self.assertFalse(out['held_access'][0]['opened'])
        self.assertFalse(out['held_access'][1]['opened'])
        self.assertFalse(out['held_access'][2]['rename_succeeded'])
        self.assertTrue(all(int(item['error']) > 0 for item in out['held_access']))

    def test_normal_adapter_ignores_fixture_controls_and_epochs_do_not_alias(self):
        v = Volume()
        path = self.fixture(v)
        rows = [request(v, path, mode=mode, call='1') for mode in ['short', 'error', 'changed', 'metadata', 'cancel', 'binding', 'replay_bytes', 'replay_offset']]
        env = dict(os.environ, DISKED_FAT_TEST_CAPTURE_ERROR='1', DISKED_EXFAT_TEST_ERROR='1')
        out = self.preserve(path, rows, env=env)
        captures = [item['result']['capture'] for item in out]
        self.assertTrue(all(c['observed_stable'] for c in captures))
        sequences = [int(c['sequence']) for c in captures]
        self.assertEqual(sorted(set(sequences)), sequences)
        self.assertEqual(len(out), len({c['capture_domain'] for c in captures}))
        self.assertEqual(1, len({c['source_identity_digest'] for c in captures}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--fault', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    PROBE, FAULT = args.probe, args.fault
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    args.output.write_text(json.dumps(dict(passed=result.wasSuccessful(), methods=result.testsRun,
        cases=sum(r['cases'] for r in RECEIPTS), receipts=RECEIPTS, unverified=UNVERIFIED), indent=2) + '\n', encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
