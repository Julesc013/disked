"""Real packet I/O with synthetic worker ports; no native/reference tool launches."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import coordinator
from collector import Output
from evidence import canonical_digest, digest, read_receipt
import observe_native
import observe_external


DISK = '12345678-9abc-4def-8123-456789abcdef'
TYPE = 'ebd0a0a2-b9e5-4433-87c0-68b6b72699c7'
UUIDS = ['00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000002']


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        managed = Path(os.environ['DISKED_WORK_ROOT']).resolve()
        self.directory = tempfile.TemporaryDirectory(dir=managed)
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name).resolve()
        self.assertTrue(self.base.is_relative_to(managed))
        self.packet = self.base / 'packet'
        self.calls = []

    def definitions(self, names=('reference',), sgdisk=True):
        result = {}
        for participant in ('native', *names):
            executable = self.base / (participant + '.bin')
            executable.write_bytes(b'Synthetic binary identity;never launched:' + participant.encode())
            profile = dict(os='synthetic/no-execution', build='unit-test', architecture='synthetic', runtime='unit-test-data',
                           token='synthetic-worker', workspace=str(self.packet), path_style='windows' if os.name == 'nt' else 'posix')
            identity = dict(schema='org.disked.differential-identity/1', participant=participant,
                role='native' if participant == 'native' else 'reference', profile=profile,
                source=dict(revision='a'*40 if participant == 'native' else None,
                            inputs={'synthetic-source': digest(b'unit-test-only')}, upstream_source_verified=False),
                build=dict(configuration='synthetic metadata only', toolchain={'synthetic': digest(b'not a compiler')},
                           executables={str(executable): digest(executable.read_bytes())}))
            tools = dict(mbr=str(executable), gpt=str(executable)) if participant == 'native' else dict(sfdisk=str(executable))
            if participant != 'native' and sgdisk: tools['sgdisk'] = str(executable)
            result[participant] = dict(identity=identity, tools=tools)
        return result

    def execute(self, **call):
        self.calls.append(call)
        if call['payload'] is not None:
            request = json.loads(call['payload'])
            if 'image' in request:
                first = bytes.fromhex(request['image']['0'])
                self.assertEqual(first[446:462].hex(), '0000020007ffffff010000001f000000')
                entries = [dict(active=True, range_valid=True, start='1', end='32', raw='0000020007ffffff010000001f000000'),
                           dict(active=True, range_valid=True, start='40', end='100', raw='0000020083ffffff280000003c000000')]
                stdout = json.dumps(dict(mbr=dict(issues=0, entries=entries), walks=[])).encode()
            else:
                self.assertEqual(bytes.fromhex(request['primary'])[:8], b'EFI PART')
                copies = []
                for starts in ((34, 70), (35, 70)):
                    entries = [dict(active=True, range_valid=True, first=str(start), end=str(end), type_guid=TYPE, unique_guid=uid)
                               for start, end, uid in zip(starts, (61, 91), UUIDS)]
                    copies.append(dict(header=dict(disk_guid=DISK, issues=0),
                        candidate=dict(entries=entries, issues=0, complete=True, consistent=True)))
                stdout = json.dumps(dict(comparison=2, copies=copies)).encode()
        else:
            path = Path(call['argv'][-1]); data = path.read_bytes()
            if '--json' in call['argv']:
                if data[512:520] == b'EFI PART':
                    parts = [dict(node=str(path)+str(i+1), start=start, size=size, type=TYPE, uuid=uid)
                             for i, (start, size, uid) in enumerate(zip((35,70), (26,21), UUIDS))]
                    table = dict(label='gpt', id=DISK, unit='sectors', sectorsize=512, partitions=parts)
                else:
                    self.assertEqual(data[510:512], b'\x55\xaa')
                    table = dict(label='dos', unit='sectors', sectorsize=512, partitions=[
                        dict(node=str(path)+'1', start=1, size=31, type='7'),
                        dict(node=str(path)+'2', start=40, size=60, type='83')])
                stdout = json.dumps(dict(partitiontable=table)).encode()
            elif '--print' in call['argv']:
                stdout = ('Disk identifier (GUID): '+DISK+'\nNumber  Start (sector) End (sector) Size Code Name\n'
                          ' 1 35 60 13KiB 0700 Alpha\n 2 70 90 10KiB 0700 Beta\n').encode()
            else:
                stdout = b'Independent synthetic diagnostic'
        return dict(outcome='exited', exit_code=0, elapsed_seconds=.01, stdout=stdout, stderr=b'', terminal=True)

    def ports(self, definitions, mode='normal'):
        ports = {}
        for participant, definition in definitions.items():
            def collect(*, manifest, snapshot, packet_root, who=participant, config=copy.deepcopy(definition)):
                def execute(**call):
                    if mode == 'interrupted':
                        self.calls.append(call); raise KeyboardInterrupt('Synthetic interruption;no child launched')
                    if mode == 'unavailable':
                        self.calls.append(call)
                        return dict(outcome='unavailable', exit_code=None, elapsed_seconds=0,
                                    stdout=b'', stderr=b'synthetic spawn refusal', terminal=True)
                    return self.execute(**call)
                if who == 'native':
                    value = observe_native.collect(manifest, packet_root, snapshot, config['identity'],
                        config['tools']['mbr'], config['tools']['gpt'], execute)
                else:
                    value = observe_external.collect(manifest, packet_root, snapshot, who, config['identity'],
                        config['tools']['sfdisk'], config['tools'].get('sgdisk'), execute)
                return dict(passed=True, receipt=value)  # The coordinator must ignore this flag.
            ports[participant] = dict(copy.deepcopy(definition), collect=collect)
        return ports

    def comparison(self):
        return json.loads((self.packet / 'coordinator/comparison.json').read_bytes())

    def receipt(self):
        return json.loads((self.packet / 'coordinator/results.json').read_bytes())

    def test_preparation_defaults_to_all35_cases_and_exact_tool_observation_set(self):
        definitions = self.definitions(('ubuntu', 'debian'))
        del definitions['debian']['tools']['sgdisk']
        prepared = coordinator.prepare(self.packet, definitions)
        manifest = prepared['manifest']
        self.assertEqual(manifest['selection']['mode'], 'all')
        self.assertEqual(len(manifest['cases']), 35)
        counts = {p: sum(row['participant'] == p for row in manifest['expected_observations']) for p in definitions}
        self.assertEqual(counts, dict(native=35, ubuntu=92, debian=70))
        self.assertEqual(prepared['manifest_sha256'], canonical_digest(manifest))
        self.assertEqual(self.calls, [])
        self.assertFalse((self.packet / 'copies').exists())

    def test_positive_control_and_gpt_conflict_survive_the_complete_coordinator_path(self):
        definitions = self.definitions()
        prepared = coordinator.prepare(self.packet, definitions, ['mbr-two', 'gpt-valid-disagreement'])
        with patch('coordinator.read_receipt', wraps=read_receipt) as reads:
            result = coordinator.run(self.packet, prepared['manifest_sha256'], self.ports(definitions))
        self.assertTrue(result['complete_success'], self.comparison())
        self.assertEqual(result['status'], 'evidence_complete')
        self.assertEqual(result['qualification'], 'not_assessed')
        self.assertEqual(result['cleanup'], 'outer_runner_pending')
        self.assertEqual(result['comparison']['sha256'], digest((self.packet / result['comparison']['path']).read_bytes()))
        self.assertEqual(len(self.calls), 7)
        conflict = [v for v in self.comparison()['comparisons'] if v['name'] == 'gpt-valid-disagreement']
        self.assertEqual(len(conflict), 2)
        self.assertTrue(all(v['matching_candidates'] == ['backup'] and v['native']['comparison'] == 2 for v in conflict))
        self.assertTrue(all([c['rows'][0]['start'] for c in v['native']['candidates']] == [34,35] for v in conflict))
        self.assertLess(reads.call_args_list[2].args[1], reads.call_args_list[1].args[1])
        self.directory.cleanup()
        self.assertFalse(self.base.exists())

    def test_all35_unavailable_cases_remain_complete_observations_but_never_success(self):
        definitions = self.definitions(('ubuntu', 'debian')); del definitions['debian']['tools']['sgdisk']
        prepared = coordinator.prepare(self.packet, definitions)
        result = coordinator.run(self.packet, prepared['manifest_sha256'], self.ports(definitions, 'unavailable'))
        self.assertFalse(result['complete_success'])
        self.assertEqual(result['status'], 'evidence_failed')
        self.assertEqual(len(self.calls), 197)
        report = self.comparison()
        self.assertEqual(report['evidence_status'], 'complete', report.get('evidence_validation'))
        self.assertEqual(len(report['execution']), 197)
        self.assertTrue(all(v['status'] == 'unavailable' for v in report['execution']))
        self.assertFalse(report['execution_passed'])
        self.directory.cleanup()
        self.assertFalse(self.base.exists())

    def test_missing_extra_mismatched_or_changed_worker_commands_refuse_before_dispatch(self):
        definitions = self.definitions(); prepared = coordinator.prepare(self.packet, definitions, ['mbr-two'])
        for mode in ('missing', 'extra', 'identity', 'commands', 'snapshot'):
            ports = self.ports(definitions); snapshot = prepared['manifest_sha256']
            if mode == 'missing': ports.pop('reference')
            elif mode == 'extra': ports['unexpected'] = ports['reference']
            elif mode == 'identity': ports['reference']['identity']['profile']['token'] = 'other token'
            elif mode == 'commands': ports['reference']['tools']['sfdisk'] = str(self.base / 'unapproved.bin')
            else: snapshot = 'sha256:' + 'f'*64
            with self.subTest(mode=mode), self.assertRaises(ValueError): coordinator.run(self.packet, snapshot, ports)
            self.assertEqual(self.calls, [])
            self.assertFalse((self.packet / 'coordinator').exists())

    def test_changed_manifest_or_tool_inputs_cannot_be_accepted_with_new_output_flags(self):
        definitions = self.definitions(); prepared = coordinator.prepare(self.packet, definitions, ['mbr-two'])
        manifest = copy.deepcopy(prepared['manifest']); manifest['comparison_inputs']['tests/differential/compare.py'] = 'sha256:'+'f'*64
        (self.packet / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaises(ValueError): coordinator.run(self.packet, canonical_digest(manifest), self.ports(definitions))
        self.assertFalse((self.packet / 'coordinator').exists())
        self.assertEqual(self.calls, [])

    def test_new_snapshot_cannot_mislabel_a_subset_or_redefine_authored_fixture_facts(self):
        definitions = self.definitions(); prepared = coordinator.prepare(self.packet, definitions, ['mbr-two'])
        for mode in ('selection', 'facts'):
            manifest = copy.deepcopy(prepared['manifest'])
            if mode == 'selection': manifest['selection']['mode'] = 'all'
            else: manifest['cases'][0]['checks']['mbr.issues'] = 99
            (self.packet / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                coordinator.run(self.packet, canonical_digest(manifest), self.ports(definitions))
            self.assertFalse((self.packet / 'coordinator').exists())
            self.assertEqual(self.calls, [])

    def test_success_flags_cannot_replace_receipts_or_raw_artifacts(self):
        definitions = self.definitions(); prepared = coordinator.prepare(self.packet, definitions, ['mbr-two'])
        ports = self.ports(definitions); ports['native']['collect'] = lambda **kwargs: dict(passed=True)
        with self.assertRaises(OSError): coordinator.run(self.packet, prepared['manifest_sha256'], ports)
        receipt = self.receipt()
        self.assertFalse(receipt['complete_success'])
        self.assertEqual(receipt['active_participant'], 'native')
        self.assertEqual(receipt['participants'], [])

    def test_returned_success_cannot_hide_changed_raw_artifacts(self):
        definitions = self.definitions(); prepared = coordinator.prepare(self.packet, definitions, ['mbr-two'])
        ports = self.ports(definitions); original = ports['reference']['collect']
        def tamper(**kwargs):
            returned = original(**kwargs)
            path = returned['receipt']['observations'][0]['raw']['stdout']['path']
            (self.packet / path).write_bytes(b'changed after collection')
            return dict(passed=True)
        ports['reference']['collect'] = tamper
        result = coordinator.run(self.packet, prepared['manifest_sha256'], ports)
        self.assertFalse(result['complete_success'])
        self.assertEqual(self.comparison()['evidence_status'], 'invalid')

    def test_existing_later_participant_copy_refuses_before_the_first_worker(self):
        definitions = self.definitions(); prepared = coordinator.prepare(self.packet, definitions, ['mbr-two'])
        row = next(v for v in prepared['manifest']['expected_observations'] if v['participant'] == 'reference')
        path = self.packet / row['policy']['input_path']; path.parent.mkdir(parents=True); path.write_bytes(b'preserve this copy')
        with self.assertRaises(ValueError): coordinator.run(self.packet, prepared['manifest_sha256'], self.ports(definitions))
        self.assertEqual(path.read_bytes(), b'preserve this copy')
        self.assertEqual(self.calls, [])
        self.assertFalse((self.packet / 'coordinator').exists())

    def test_interrupted_worker_stops_without_retry_and_owned_data_can_be_removed(self):
        definitions = self.definitions(); prepared = coordinator.prepare(self.packet, definitions, ['mbr-two'])
        with self.assertRaises(KeyboardInterrupt):
            coordinator.run(self.packet, prepared['manifest_sha256'], self.ports(definitions, 'interrupted'))
        receipt = self.receipt()
        self.assertEqual(receipt['status'], 'interrupted')
        self.assertTrue(receipt['quiescence_unknown'])
        self.assertFalse(receipt['complete_success'])
        self.assertEqual(len(self.calls), 1)
        self.directory.cleanup()
        self.assertFalse(self.base.exists())

    def test_existing_packet_and_coordinator_output_are_preserved(self):
        definitions = self.definitions(); prepared = coordinator.prepare(self.packet, definitions, ['mbr-two'])
        manifest_bytes = (self.packet / 'manifest.json').read_bytes()
        with self.assertRaises(ValueError): coordinator.prepare(self.packet, definitions)
        self.assertEqual((self.packet / 'manifest.json').read_bytes(), manifest_bytes)
        result = coordinator.run(self.packet, prepared['manifest_sha256'], self.ports(definitions))
        with self.assertRaises(ValueError): coordinator.run(self.packet, prepared['manifest_sha256'], self.ports(definitions))
        self.assertEqual(self.receipt(), result)

    def test_invalid_selections_and_unmanaged_roots_do_not_create_packets(self):
        definitions = self.definitions()
        for names in ([], ['unknown-case'], ['mbr-two', 'mbr-two']):
            with self.subTest(names=names), self.assertRaises(ValueError): coordinator.prepare(self.packet, definitions, names)
            self.assertFalse(self.packet.exists())
        with patch.dict(os.environ, {'DISKED_WORK_ROOT': ''}), self.assertRaises(ValueError):
            coordinator.prepare(self.packet, definitions)
        with self.assertRaises(ValueError): coordinator.prepare(Path(__file__).parent / 'forbidden-packet', definitions)

    def test_standalone_script_refuses_before_output_creation(self):
        process = subprocess.run([sys.executable, '-B', coordinator.__file__, '--output', str(self.packet)],
                                 capture_output=True, timeout=10)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn(b'No standalone execution profile', process.stderr)
        self.assertFalse(self.packet.exists())

    def test_preparation_preserves_original_windows_and_posix_worker_paths(self):
        definitions = self.definitions()
        for participant, style, workspace, binary in [
            ('native', 'windows', 'W:\\disked\\packet', 'C:\\tools\\probe.exe'),
            ('reference', 'posix', '/scratch/packet', '/usr/sbin/sfdisk')]:
            value = definitions[participant]; identity = value['identity']
            identity['profile'].update(path_style=style, workspace=workspace)
            identity['build']['executables'] = {binary: digest(b'synthetic remote identity;not executed')}
            value['tools'] = dict(mbr=binary, gpt=binary) if participant == 'native' else dict(sfdisk=binary)
        prepared = coordinator.prepare(self.packet, definitions, ['mbr-two'])
        rows = prepared['manifest']['expected_observations']
        self.assertEqual(rows[0]['policy']['argv'], ['C:\\tools\\probe.exe'])
        self.assertEqual(rows[1]['policy']['argv'][0], '/usr/sbin/sfdisk')
        self.assertTrue(rows[1]['policy']['argv'][-1].startswith('/scratch/packet/copies/'))
        self.assertEqual(self.calls, [])

    def test_agreement_without_a_declared_positive_control_is_not_coordinator_success(self):
        definitions = self.definitions(); prepared = coordinator.prepare(self.packet, definitions, ['gpt-valid-disagreement'])
        result = coordinator.run(self.packet, prepared['manifest_sha256'], self.ports(definitions))
        self.assertTrue(self.comparison()['complete_success'])
        self.assertFalse(result['complete_success'])
        self.assertFalse(any(result['positive_controls_declared'].values()))

    def test_failed_final_checkpoint_cannot_leave_a_successful_coordinator_receipt(self):
        definitions = self.definitions(); prepared = coordinator.prepare(self.packet, definitions, ['mbr-two'])
        original = Output.checkpoint
        def fail(output, directory, value):
            if directory.name == 'coordinator' and value['status'] == 'evidence_complete':
                raise OSError('Synthetic final checkpoint failure')
            return original(output, directory, value)
        with patch.object(Output, 'checkpoint', fail), self.assertRaises(OSError):
            coordinator.run(self.packet, prepared['manifest_sha256'], self.ports(definitions))
        self.assertEqual(self.receipt()['status'], 'failed')
        self.assertFalse(self.receipt()['complete_success'])
        self.directory.cleanup()
        self.assertFalse(self.base.exists())


if __name__ == '__main__':
    unittest.main()
