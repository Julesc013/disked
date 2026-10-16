"""Generated held files, independent raw correspondence, exact traces and replay faults."""
import argparse
import copy
import json
import os
from pathlib import Path
import unittest

import test_ntfs_file as held
from ntfs_membership_fixture import MembershipVolume, filename, ref
from test_ntfs_membership import complete as membership_complete
from test_ntfs_capture import bytes_at
from test_ntfs_directory_file import foundation as directory_foundation
import test_ntfs_directory_file as directory_file

SOURCE_RECEIPTS = []


def foundation(observation):
    result = directory_foundation(observation)
    result['requested_target_limit'] = observation['requested_target_limit']
    return result


class Tests(unittest.TestCase):
    setUp = held.Tests.setUp
    tearDown = held.Tests.tearDown
    fixture = held.Tests.fixture

    def row(self, volume, source_path, **extra):
        result = dict(path=str(source_path), offset=volume.input['offset'], length=volume.input['length'],
                      directory=copy.deepcopy(volume.input['directory']),
                      membership=copy.deepcopy(volume.input['membership']))
        result.update(extra)
        return result

    def preserve(self, path, rows, fault=False, env=None):
        before = held.file_digest(path), path.stat().st_size
        results = held.run(rows, fault, env)
        after = held.file_digest(path), path.stat().st_size
        self.assertEqual(before, after)
        SOURCE_RECEIPTS.append(dict(before_sha256=before[0], after_sha256=after[0], bytes=before[1],
                                    inputs=[held.digest(held.canonical(row)) for row in rows],
                                    results=[held.digest(held.canonical(row)) for row in results]))
        return results

    def batches(self, path, rows, fault=True):
        result = []
        for at in range(0, len(rows), 5):
            result += self.preserve(path, rows[at:at+5], fault)
        return result

    def good(self, volume, path, extra=None, fault=False, mismatch=False):
        row = self.row(volume, path, **(extra or {}))
        value = self.preserve(path, [row], fault)[0]
        self.assertNotIn('refusal', value, value)
        result = value['result'];capture = result['capture'];obs = result['observation']
        self.assertEqual(result['schema'], 'org.disked.ntfs-membership-file-capture/1')
        membership_complete(obs, volume)
        self.assertEqual(obs['applicable'], not mismatch)
        self.assertEqual(obs['diagnostic'], 'ntfs_membership_name_mismatch' if mismatch else '')
        self.assertNotIn('binding_diagnostic', obs)
        for name in ('metadata_complete', 'metadata_equal', 'binding_checks_ok', 'replay_equal', 'profile_selection_equal'):
            self.assertTrue(capture[name], (name, value))
        self.assertEqual(capture['observed_stable'], not mismatch)
        self.assertEqual(capture['source_before'], capture['source_after'])
        self.assertEqual(capture['source_before'], capture['source_final'])
        self.assertEqual(capture['source_before']['bytes'], str(path.stat().st_size))
        self.assertEqual(capture['source_identity_digest'], held.digest(held.canonical(capture['source_before'])))
        self.assertEqual(obs['source_id'], capture['source_identity_digest'])
        self.assertEqual(obs['epoch'], capture['sequence'])
        domain = capture['domain']
        self.assertEqual(domain['provider'], 'ntfs-membership-file-prototype')
        self.assertEqual(domain['target_limit'], row['membership'].get('targets', '64'))
        self.assertEqual(domain['directory_reference'], row['directory'].get('reference', '0'))
        self.assertEqual(capture['capture_domain'], held.digest(held.canonical(domain)))
        self.assertEqual(capture['selected_profile'], '3.'+volume.input['minor'])
        self.assertFalse(result['authorizes_effects'] or result['product_dispatch_admitted'] or capture['atomic_snapshot'])
        self.assertEqual(capture['source_consistency'], 'live-uncoordinated')
        wanted = volume.initial_reads*2
        self.assertEqual([(int(r['offset']), int(r['requested'])) for r in value['regions']], wanted)
        for region, (start, size) in zip(value['regions'], wanted):
            self.assertTrue(region['seek_attempted'] and region['read_attempted'])
            self.assertEqual(region['error'], '0');self.assertEqual(region['refusal'], '')
            self.assertEqual(bytes.fromhex(region['bytes']), bytes_at(volume.input, start, size))
        auto30 = volume.input['minor']=='0' and row.get('profile', 'auto')=='auto'
        for name in ('profile_prefix_validation_attempted', 'profile_prefix_validated', 'profile_prefix_boundary', 'profile_prefix_continued'):
            self.assertEqual(capture[name], auto30)
        prefix = len(volume.bootstrap_reads) if auto30 else 0
        self.assertEqual(capture['profile_prefix_validation_calls'], str(prefix))
        self.assertEqual(capture['profile_prefix_reused'], str(prefix))
        self.assertEqual(capture['profile_probe_response_count'], str(prefix if auto30 else len(wanted)))
        self.assertEqual(capture['replay_calls'], str(len(wanted)+2*prefix))
        self.assertEqual(capture['retained_replays'], '2' if auto30 else '1')
        if auto30:
            self.assertEqual(capture['profile_probe_foundation_sha256'], capture['profile_selected_foundation_sha256'])
            self.assertRegex(capture['profile_prefix_validation_sha256'], r'^sha256:[0-9a-f]{64}$')
        return value

    def test_profiles_graphs_names_and_exact_native_trace(self):
        for minor in (0, 1):
            for kind in ('empty', 'leaf', 'single', 'siblings', 'deep', 'preallocated'):
                volume, path = self.fixture(MembershipVolume(minor=minor, kind=kind))
                for profile in ('auto', '3.'+str(minor)):
                    self.good(volume, path, dict(profile=profile))
            for form in ('resident', 'nonresident'):
                volume, path = self.fixture(MembershipVolume(minor=minor, list_form=form,
                    directory_list_form='nonresident', mft_closure=True, bitmap_form='nonresident',
                    fragmented_allocation=True, split_allocation=True))
                self.good(volume, path)
            volume, path = self.fixture(MembershipVolume(minor=minor, usa=42, number=17, sequence=65535))
            self.good(volume, path)
        for name in (b'\0\0', b'\x1b\0[\0m\0', b'\0\xd8\xff\xdc', b'\xff\xff'*255):
            volume, path = self.fixture(MembershipVolume(kind='single', size=4096, name=name, namespace=3))
            self.good(volume, path)
        volume, path = self.fixture(MembershipVolume(offset=(1 << 32)+173))
        self.good(volume, path)

    def test_distinct_instances_empty_inventories_and_complete_mismatch(self):
        for mode in ('identical', 'parent', 'namespace', 'name', 'empty'):
            volume = MembershipVolume()
            values = copy.deepcopy(volume.target_recipes[ref(14, 9)]['values'])
            if mode=='identical':values += [values[0], values[0]]
            elif mode=='empty':values = []
            else:
                values = [filename(b'X\0' if mode=='name' else raw[66:66+raw[64]*2],
                                   parent=ref(5, 4) if mode=='parent' else volume.reference,
                                   namespace=2 if mode=='namespace' else raw[65])[0] for raw in values]
            volume.replace_target(values=values)
            volume, path = self.fixture(volume)
            self.good(volume, path, mismatch=mode!='identical')
        volume, path = self.fixture(MembershipVolume(target_flags=3))
        for limit in (1, 64, 256):self.good(volume, path, dict(membership=dict(targets=str(limit))))

    def test_profile_foundations_bind_exact_target_controls_and_reports(self):
        for minor in (0, 1):
            volume, path = self.fixture(MembershipVolume(minor=minor, list_form='nonresident'))
            for limit in (1, 64, 256):
                volume.input['membership']['targets'] = str(limit)
                value = self.good(volume, path)
                capture = value['result']['capture']
                probe = directory_file.pure_report(volume, value, 1)
                self.assertEqual(capture['profile_probe_sha256'], held.digest(held.canonical(probe)))
                self.assertEqual(value['result']['observation'], directory_file.pure_report(volume, value, minor))
                if minor == 0:
                    prefix = directory_file.pure_report(volume, value, 0,
                        dict(fault=dict(mode='throw', call=str(len(volume.bootstrap_reads)+1))))
                    self.assertEqual(capture['profile_prefix_validation_sha256'], held.digest(held.canonical(prefix)))
                    self.assertEqual(capture['profile_probe_foundation_sha256'], held.digest(held.canonical(foundation(probe))))
                    self.assertEqual(capture['profile_selected_foundation_sha256'], held.digest(held.canonical(foundation(prefix))))

    def test_source_profile_window_and_alias_refusals(self):
        for minor in (0, 1):
            volume, path = self.fixture(MembershipVolume(minor=minor))
            value = self.preserve(path, [self.row(volume, path, profile='3.'+str(1-minor))])[0]
            self.assertEqual(value['result']['observation']['diagnostic'], 'ntfs_volume_version')
            self.assertFalse(value['result']['observation']['applicable'])
            self.assertEqual(len(value['regions']), len(volume.bootstrap_reads))
        before = self.good(volume, path)['result']['capture']['source_before']
        self.good(volume, path, dict(expected_source=before, mode='mutate_request'), True)
        cases = [(dict(profile='unknown'), 'ntfs_file_profile'),
                 (dict(length=str(path.stat().st_size+1)), 'ntfs_capture_window'),
                 (dict(expected_source=dict(before, bytes='1')), 'ntfs_file_source_changed')]
        values = self.preserve(path, [self.row(volume, path, **extra) for extra, _ in cases], True)
        for (_, code), value in zip(cases, values):
            self.assertEqual(value['refusal'], code)
            self.assertEqual(value['read_calls'], '0')
        alias = self.root/'alias.img'
        os.link(path, alias)
        try:
            value = self.preserve(path, [self.row(volume, path)])[0]
            self.assertEqual(value['refusal'], 'image_file_aliases')
        finally:
            alias.unlink()

    def test_each_live_read_error_and_changed_final_reread(self):
        for minor in (0, 1):
            volume, path = self.fixture(MembershipVolume(minor=minor, list_form='nonresident'))
            count = len(volume.initial_reads)*2
            rows = [self.row(volume, path, mode=mode, call=str(call))
                    for call in range(1, count+1)
                    for mode in ('short', 'error', 'partial_error', 'throw', 'read_throw')]
            for actual in self.batches(path, rows):
                self.assertNotIn('refusal', actual, actual)
                obs = actual['result']['observation'];capture = actual['result']['capture']
                self.assertFalse(obs['complete'] or obs['applicable'] or capture['observed_stable'])
                self.assertEqual(obs['diagnostic'], 'ntfs_reader_failure')
                self.assertTrue(capture['replay_equal'])
            rows = [self.row(volume, path, mode='changed', call=str(call))
                    for call in range(len(volume.initial_reads)+1, count+1)]
            for actual in self.batches(path, rows):
                self.assertFalse(actual['result']['observation']['complete'])
                self.assertEqual(actual['result']['observation']['diagnostic'], 'ntfs_source_changed')

    def test_prefix_binding_and_continuation_refuse_before_native_suffix(self):
        volume, path = self.fixture(MembershipVolume(minor=0, list_form='nonresident'))
        prefix = len(volume.bootstrap_reads)
        rows = [self.row(volume, path, mode=mode, call=str(call))
                for call in range(1, 2*prefix+1)
                for mode in ('replay_bytes', 'replay_offset', 'replay_provenance', 'replay_throw')]
        for actual in self.batches(path, rows):
            self.assertNotIn('refusal', actual, actual)
            capture = actual['result']['capture']
            self.assertFalse(actual['result']['observation']['applicable'] or capture['observed_stable'])
            self.assertLessEqual(len(actual['regions']), prefix)
            self.assertLessEqual(int(actual['read_calls']), prefix)

    def test_each_final_replay_fault_cannot_qualify_capture(self):
        for minor in (0, 1):
            volume, path = self.fixture(MembershipVolume(minor=minor, list_form='nonresident'))
            offset = 2*len(volume.bootstrap_reads) if minor==0 else 0
            rows = [self.row(volume, path, mode=mode, call=str(offset+call))
                    for call in range(1, 2*len(volume.initial_reads)+1)
                    for mode in ('replay_bytes', 'replay_offset', 'replay_provenance', 'replay_throw')]
            for actual in self.batches(path, rows):
                self.assertNotIn('refusal', actual, actual)
                obs = actual['result']['observation'];capture = actual['result']['capture']
                self.assertFalse(obs['applicable'] or capture['observed_stable'] or capture['replay_equal'])
                self.assertEqual(len(actual['regions']), 2*len(volume.initial_reads))

    def test_invalid_controls_precede_path_and_native_callbacks(self):
        volume, path = self.fixture(MembershipVolume())
        rows = [self.row(volume, path, path='not-an-absolute-local-file', membership=dict(targets=str(n)), mode='binding')
                for n in (0, 257, (1 << 32)+1, (1 << 64)-1)]
        for actual in self.batches(path, rows):
            self.assertEqual(actual['refusal'], 'ntfs_membership_limits')
            self.assertNotIn('result', actual)
            self.assertEqual(actual['read_calls'], '0')
            self.assertEqual(actual['stop_calls'], '0')
        rows = [self.row(volume, path, directory=dict(reference='1')),
                self.row(volume, path, directory=dict(limits=dict(entries='0')))]
        for actual in self.batches(path, rows):
            self.assertIn(actual['refusal'], ('ntfs_directory_reference', 'ntfs_directory_limits'))
            self.assertEqual(actual['read_calls'], '0')

    def test_exact_budgets_and_incomplete_target_prefix(self):
        volume, path = self.fixture(MembershipVolume(list_form='nonresident'))
        count = len(volume.initial_reads);total = sum(n for _, n in volume.initial_reads)
        self.good(volume, path, dict(limits=dict(read_requests=str(2*count), read_bytes=str(2*total), retained_bytes=str(total), attributes='10', runs='6')))
        rows = [self.row(volume, path, limits={name:str(value)}) for name, value in
                [('read_requests', 2*count-1), ('read_bytes', 2*total-1), ('retained_bytes', total-1),
                 ('attributes', 9), ('runs', 5), ('output_bytes', 16384)]]
        for actual in self.batches(path, rows):
            self.assertNotIn('refusal', actual, actual)
            self.assertFalse(actual['result']['observation']['complete'] or actual['result']['observation']['applicable'])
            self.assertTrue(actual['result']['observation']['diagnostic'].endswith('_budget'))
        volume = MembershipVolume();volume.mutate_record(14, 16, b'\x08\0')
        volume, path = self.fixture(volume)
        value = self.preserve(path, [self.row(volume, path)])[0]
        self.assertEqual(value['result']['observation']['diagnostic'], 'ntfs_membership_target_record')
        self.assertFalse(value['result']['observation']['membership']['targets'][0]['inventory_complete'])

    def test_metadata_binding_cancellation_and_frozen_controls(self):
        volume, path = self.fixture(MembershipVolume(minor=0, list_form='nonresident'))
        for call in (1, len(volume.bootstrap_reads)+1, 2*len(volume.initial_reads)):
            self.good(volume, path, dict(mode='mutate_request', call=str(call)), True)
        rows = [self.row(volume, path, mode=mode, call='1')
                for mode in ('metadata', 'metadata_throw', 'cancel', 'cancel_once', 'cancel_throw', 'binding', 'binding_throw')]
        for actual in self.batches(path, rows):
            if 'result' in actual:
                self.assertFalse(actual['result']['observation']['applicable'] or actual['result']['capture']['observed_stable'])
            else:self.assertIn('refusal', actual)

    def test_held_exclusion_release_and_normal_fault_isolation(self):
        volume, path = self.fixture(MembershipVolume(minor=0), name='owned/inner/source.img')
        value = self.good(volume, path, dict(mode='held_access', call=str(len(volume.bootstrap_reads)+1),
            release_check=True, access_parents=[str(path.parent), str(path.parent.parent)]), True)
        for group in value['held_access']:
            self.assertFalse(group[0]['opened'] or group[1]['opened'] or group[2]['moved'])
        self.assertTrue(all(row['opened'] for row in value['released_access']))
        self.assertTrue(all(row['opened'] for group in value['released_parent_access'] for row in group))
        environment = dict(os.environ, DISKED_NTFS_FILE_TEST_MODE='error', DISKED_NTFS_FILE_FAULT='1')
        value = self.good(volume, path, dict(mode='cancel', call='1'), False)
        self.assertEqual(value['stop_calls'], '0')
        value = self.preserve(path, [self.row(volume, path)], False, environment)[0]
        membership_complete(value['result']['observation'], volume)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--fault', type=Path, required=True)
    parser.add_argument('--pure', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    held.PROBE = args.probe.resolve();held.FAULT = args.fault.resolve()
    directory_file.PURE = args.pure.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    summary = dict(cases=len(held.RECEIPTS), methods=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                   receipts=held.RECEIPTS, source_receipts=SOURCE_RECEIPTS, unverified=held.UNVERIFIED,
                   pure_receipts=directory_file.PURE_RECEIPTS,
                   scope='Held ordinary-file exact correspondence; no worker/public/physical or full-product admission.')
    args.output.write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8', newline='\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
