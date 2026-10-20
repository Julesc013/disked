"""Synthetic runner tests of packet collection; no native/reference tool runs."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import observe_native
import observe_external
import test_evidence_bindings as fixtures
from collector import Output, executable_hash
from compare import compare
from evidence import canonical_digest, digest


HERE = Path(__file__).resolve().parent


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=os.environ['DISKED_WORK_ROOT'])
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        maker = fixtures.BindingTests(methodName='runTest'); maker.root = self.root
        self.manifest, native, external = maker.packet()
        self.stdout = {}
        paths = set()
        self.tools = {}
        self.identities = {}
        for participant, receipt in [('native', native), ('reference', external['reference'])]:
            binary = self.root / 'tools' / (participant + '.bin')
            binary.parent.mkdir(exist_ok=True)
            binary.write_bytes(b'Synthetic identity only;never executed:' + participant.encode())
            self.tools[participant] = binary
            declared = self.manifest['evidence']['participants'][participant]
            identity = json.loads((self.root / declared['identity']['path']).read_bytes())
            identity['profile'].update(workspace=str(self.root), path_style='windows' if os.name == 'nt' else 'posix')
            identity['build']['executables'] = {str(binary): digest(binary.read_bytes())}
            self.identities[participant] = copy.deepcopy(identity)
            declared['profile'] = identity['profile']
            declared['identity'] = maker.artifact(declared['identity']['path'], json.dumps(identity).encode())
            for row in receipt['observations']:
                body = (self.root / row['raw']['stdout']['path']).read_bytes()
                if row['kind'] == 'sfdisk-json':
                    value = json.loads(body)
                    value['partitiontable']['partitions'][0]['node'] = str(self.root / row['input_after']['path']) + '1'
                    body = json.dumps(value).encode()
                self.stdout[participant, row['kind']] = body
                for descriptor in [row['input_before'], row['input_after'], *row['raw'].values()]:
                    paths.add(self.root / descriptor['path'])
        for path in paths:
            path.unlink()
        for row in self.manifest['expected_observations']:
            participant, kind, policy = row['participant'], row['kind'], row['policy']
            binary = str(self.tools[participant])
            policy['argv'] = [binary] if participant == 'native' else [binary,
                '--json' if kind == 'sfdisk-json' else '--verify', str(self.root / policy['input_path'])]
        self.snapshot = canonical_digest(self.manifest)
        self.calls = []

    def runner(self, **call):
        self.calls.append(call)
        self.assertEqual(call['cwd'], self.root)
        self.assertEqual(call['output_limit'], 1024 * 1024)
        participant = 'native' if call['payload'] is not None else 'reference'
        kind = 'native' if participant == 'native' else 'sfdisk-json' if '--json' in call['argv'] else 'sfdisk-verify'
        if participant == 'native':
            request = json.loads(call['payload'])
            self.assertEqual(request['blocks'], '2')
            self.assertEqual(bytes.fromhex(request['image']['0'])[510:512], b'\x55\xaa')
        else:
            self.assertEqual(Path(call['argv'][-1]).read_bytes()[510:512], b'\x55\xaa')
        return dict(outcome='exited', exit_code=0, elapsed_seconds=.01,
                    stdout=self.stdout[participant, kind], stderr=b'', terminal=True)

    def collect(self, participant, execute=None):
        runner = execute or self.runner
        if participant == 'native':
            return observe_native.collect(self.manifest, self.root, self.snapshot, self.identities['native'],
                                          self.tools['native'], self.tools['native'], runner)
        return observe_external.collect(self.manifest, self.root, self.snapshot, participant,
                                        self.identities[participant], self.tools[participant], None, runner)

    def receipt(self, participant):
        path = self.root / 'collections' / digest(participant.encode())[7:23] / 'results.json'
        return json.loads(path.read_bytes())

    def verify(self, native, reference):
        return compare(self.manifest, native, dict(reference=reference), artifact_root=self.root,
                       expected_manifest_sha256=self.snapshot)

    def test_both_adapters_emit_a_complete_packet_with_actual_distinct_files(self):
        native = self.collect('native'); reference = self.collect('reference')
        result = self.verify(native, reference)
        self.assertTrue(result['complete_success'], result.get('evidence_validation'))
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(native['status'], 'collected')
        self.assertEqual(result['comparison_status'], 'agreement')
        self.assertNotEqual((self.root / native['observations'][0]['input_after']['path']).stat().st_ino,
                            (self.root / reference['observations'][0]['input_after']['path']).stat().st_ino)
        self.assertEqual(native, self.receipt('native'))

    def test_path_and_handle_ctime_domains_are_compared_independently(self):
        from types import SimpleNamespace
        value = self.tools['native'].stat()
        handle = SimpleNamespace(**{name: getattr(value, name) for name in
            ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')})
        handle.st_ctime_ns += 1
        with patch('collector.os.fstat', return_value=handle):
            self.assertEqual(executable_hash(self.tools['native']), digest(self.tools['native'].read_bytes()))
        changed = copy.copy(handle); changed.st_ctime_ns += 1
        with patch('collector.os.fstat', side_effect=[handle, changed]), self.assertRaises(ValueError):
            executable_hash(self.tools['native'])

    def test_wrong_snapshot_identity_or_command_refuses_before_output_or_dispatch(self):
        for mode in ('snapshot', 'identity', 'command'):
            manifest, snapshot, identities = copy.deepcopy(self.manifest), self.snapshot, copy.deepcopy(self.identities)
            try:
                if mode == 'snapshot': self.snapshot = 'sha256:' + 'f' * 64
                elif mode == 'identity': self.identities['native']['profile']['token'] = 'another worker'
                else:
                    self.manifest['expected_observations'][0]['policy']['argv'].append('unapproved')
                    self.snapshot = canonical_digest(self.manifest)
                with self.subTest(mode=mode), self.assertRaises(ValueError): self.collect('native')
                self.assertEqual(self.calls, [])
                self.assertFalse((self.root / 'collections').exists())
            finally:
                self.manifest, self.snapshot, self.identities = manifest, snapshot, identities

    def test_existing_collection_or_copy_is_preserved(self):
        native = self.collect('native'); before = copy.deepcopy(native)
        with self.assertRaises(ValueError): self.collect('native')
        self.assertEqual(self.receipt('native'), before)
        self.assertEqual(len(self.calls), 1)

    def test_changed_input_keeps_real_after_bytes_and_stops_before_another_call(self):
        def changed(**call):
            result = self.runner(**call)
            path = Path(call['argv'][-1]); body = bytearray(path.read_bytes()); body[-1] ^= 1; path.write_bytes(body)
            return result
        with self.assertRaises(ValueError): self.collect('reference', changed)
        receipt = self.receipt('reference')
        self.assertEqual(receipt['status'], 'failed')
        self.assertEqual(receipt['error_code'], 'observed_input_or_executable_change')
        self.assertEqual(len(receipt['observations']), 1)
        self.assertFalse(receipt['observations'][0]['input_unchanged'])
        self.assertFalse(receipt['quiescence_unknown'])
        self.assertEqual(len(self.calls), 1)
        row = receipt['observations'][0]
        self.assertNotEqual(row['input_before']['sha256'], row['input_after']['sha256'])

    def test_replaced_identical_input_is_not_treated_as_the_same_copy(self):
        def replace(**call):
            result = self.runner(**call); path = Path(call['argv'][-1]); other = self.root / 'replacement'
            other.write_bytes(path.read_bytes()); os.replace(other, path)
            return result
        with self.assertRaises(ValueError): self.collect('reference', replace)
        self.assertFalse(self.receipt('reference')['observations'][0]['input_unchanged'])

    def test_changed_executable_is_retained_as_a_failed_observation(self):
        def changed(**call):
            result = self.runner(**call); self.tools['native'].write_bytes(b'changed executable identity')
            return result
        with self.assertRaises(ValueError): self.collect('native', changed)
        receipt = self.receipt('native'); row = receipt['observations'][0]
        self.assertEqual(receipt['status'], 'failed')
        self.assertNotEqual(row['executable_before_sha256'], row['executable_after_sha256'])
        self.assertFalse(receipt['quiescence_unknown'])

    def test_interruption_and_runner_failure_preserve_unfinished_call_without_retry(self):
        for participant, error in [('native', KeyboardInterrupt), ('reference', OSError)]:
            calls = []
            def interrupted(**call):
                calls.append(call); raise error('synthetic interruption;no process started')
            with self.subTest(participant=participant), self.assertRaises(error): self.collect(participant, interrupted)
            receipt = self.receipt(participant)
            self.assertIn(receipt['status'], ('failed', 'interrupted'))
            self.assertTrue(receipt['quiescence_unknown'])
            self.assertIsNotNone(receipt['active'])
            self.assertEqual(receipt['active']['executable_before_sha256'], digest(self.tools[participant].read_bytes()))
            self.assertEqual(receipt['observations'], [])
            self.assertEqual(len(calls), 1)

    def test_zero_exit_deadline_or_output_failure_never_passes_execution(self):
        native = self.collect('native')
        for mode in ('timeout', 'output_limit'):
            def failed(**call):
                result = self.runner(**call)
                if '--verify' in call['argv']: result.update(outcome=mode, exit_code=0)
                return result
            reference = self.collect('reference', failed)
            result = self.verify(native, reference)
            with self.subTest(mode=mode):
                self.assertEqual(result['evidence_status'], 'complete', result.get('evidence_validation'))
                self.assertFalse(result['complete_success'])
                self.assertFalse(result['execution_passed'])
            # Only this test's ordinary files under its owned temporary directory.
            directory = self.root / 'collections' / digest(b'reference')[7:23]
            for path in directory.iterdir(): path.unlink()
            directory.rmdir()
            for path in (self.root / 'copies/reference').iterdir(): path.unlink()

    def test_malformed_native_output_is_retained_without_a_projection(self):
        def malformed(**call):
            result = self.runner(**call); result['stdout'] = b'not json'; return result
        native = self.collect('native', malformed); reference = self.collect('reference')
        row = native['observations'][0]
        self.assertEqual(row['stdout'], 'not json'); self.assertIsNone(row['projection'])
        self.assertFalse(self.verify(native, reference)['complete_success'])

    def test_non_utf8_reference_diagnostic_remains_exact_bytes(self):
        def diagnostic(**call):
            result = self.runner(**call)
            if '--verify' in call['argv']: result['stderr'] = bytes.fromhex('eda080')
            return result
        native = self.collect('native'); reference = self.collect('reference', diagnostic)
        self.assertTrue(self.verify(native, reference)['complete_success'])
        row = reference['observations'][1]
        self.assertEqual(row['stderr_bytes_hex'], 'eda080')
        self.assertEqual((self.root / row['raw']['stderr']['path']).read_bytes(), bytes.fromhex('eda080'))

    def test_declared_diagnostic_refusal_is_a_complete_observation(self):
        self.manifest['expected_observations'][2]['policy']['allowed_outcomes'].append('refused')
        self.snapshot = canonical_digest(self.manifest)
        def refusal(**call):
            result = self.runner(**call)
            if '--verify' in call['argv']: result.update(exit_code=1, stderr=b'reference refused this fixture')
            return result
        native = self.collect('native'); reference = self.collect('reference', refusal)
        result = self.verify(native, reference)
        self.assertEqual(reference['observations'][1]['execution']['status'], 'refused')
        self.assertTrue(result['complete_success'], result.get('evidence_validation'))

    def test_missing_process_is_retained_without_inventing_a_successful_execution(self):
        def unavailable(**call):
            result = self.runner(**call)
            if '--verify' in call['argv']:
                result.update(outcome='unavailable', exit_code=None, stdout=b'', stderr=b'synthetic spawn refusal')
            return result
        native = self.collect('native'); reference = self.collect('reference', unavailable)
        result = self.verify(native, reference)
        self.assertEqual(result['evidence_status'], 'complete', result.get('evidence_validation'))
        self.assertEqual(reference['observations'][1]['execution']['status'], 'unavailable')
        self.assertFalse(result['complete_success'])

    def test_failed_final_checkpoint_never_yields_a_finalized_receipt(self):
        original = Output.checkpoint
        def interrupted(output, directory, value):
            if value['status'] == 'collected': raise OSError('synthetic checkpoint failure')
            return original(output, directory, value)
        with patch.object(Output, 'checkpoint', interrupted), self.assertRaises(OSError): self.collect('native')
        receipt = self.receipt('native')
        self.assertEqual(len(receipt['observations']), 1)
        self.assertEqual(receipt['status'], 'failed')
        self.assertFalse(receipt['quiescence_unknown'])
        reference = self.collect('reference')
        self.assertFalse(self.verify(receipt, reference)['complete_success'])

    def test_nonterminal_or_overlarge_runner_result_keeps_an_incomplete_call(self):
        for participant, mode in [('native', 'terminal'), ('reference', 'bytes')]:
            def invalid(**call):
                result = self.runner(**call)
                if mode == 'terminal': result['terminal'] = False
                else: result['stdout'] = b'a' * (1024 * 1024 + 1)
                return result
            with self.subTest(mode=mode), self.assertRaises(ValueError): self.collect(participant, invalid)
            receipt = self.receipt(participant)
            self.assertEqual(receipt['status'], 'failed')
            self.assertIsNotNone(receipt['active'])
            self.assertEqual(receipt['observations'], [])

    def test_output_bound_and_partial_checkpoint_preserve_prior_receipt(self):
        output = Output(self.root); directory = self.root / 'output'; directory.mkdir()
        output.checkpoint(directory, dict(status='collecting', observations=[]))
        old = (directory / 'results.json').read_bytes()
        output.bytes_written = 64 * 1024 * 1024 - 2
        with self.assertRaises(ValueError): output.checkpoint(directory, dict(status='collected'))
        self.assertEqual((directory / 'results.json').read_bytes(), old)
        self.assertLessEqual((directory / 'receipt.next.json').stat().st_size, 2)

    def test_explicit_unfinished_receipt_cannot_pass_finalized_validation(self):
        native = self.collect('native'); reference = self.collect('reference')
        reference['status'] = 'failed'
        self.assertFalse(self.verify(native, reference)['complete_success'])

    def test_legacy_cli_refuses_before_output_or_process_dispatch(self):
        with patch('subprocess.Popen', side_effect=AssertionError('No process dispatch')):
            with self.assertRaises(RuntimeError): observe_native.observe('unused')
            with self.assertRaises(RuntimeError): observe_external.observe('unused')
        for name in ('observe_native.py', 'observe_external.py'):
            output = self.root / ('unused-' + name)
            result = subprocess.run([sys.executable, '-B', str(HERE / name), '--output', str(output)],
                                    capture_output=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'Legacy', result.stderr)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
