"""Actual unprivileged self-spawn, disconnect and private evidence-store tests."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
import sys

PARSER = argparse.ArgumentParser()
PARSER.add_argument('--exe', required=True)
PARSER.add_argument('--guard', required=True)
PARSER.add_argument('--delayed', required=True)
PARSER.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
PARSER.add_argument('--validate-schemas', action='store_true')
PARSER.add_argument('--evidence', type=Path)
ARGS, REST = PARSER.parse_known_args()
EXE = str(Path(ARGS.exe).resolve())
OBSERVATIONS = []
BUNDLE = None
if ARGS.validate_schemas:
    sys.path.insert(0, str(ARGS.root / 'spec/tools'))
    import specctl
    BUNDLE = specctl.Bundle(ARGS.root / 'spec')
K = C.WinDLL('kernel32', use_last_error=True)
K.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
K.OpenProcess.restype = W.HANDLE
K.CloseHandle.argtypes = [W.HANDLE]
K.TerminateProcess.argtypes = [W.HANDLE, W.UINT]
K.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
K.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, W.HANDLE]
K.CreateFileW.restype = W.HANDLE
K.GetExitCodeProcess.argtypes = [W.HANDLE, C.POINTER(W.DWORD)]
K.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)]
K.GetProcessTimes.argtypes = [W.HANDLE] + [C.POINTER(W.FILETIME)] * 4
K.SetHandleInformation.argtypes = [W.HANDLE, W.DWORD, W.DWORD]
class Memory(C.Structure):
    _fields_ = [('cb', W.DWORD), ('faults', W.DWORD)] + [(name, C.c_size_t) for name in
        ('peak_working', 'working', 'peak_paged', 'paged', 'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile', 'private')]
K.K32GetProcessMemoryInfo.argtypes = [W.HANDLE, C.POINTER(Memory), W.DWORD]

def invoke(*words, executable=EXE):
    command = [executable, *map(str, words), '--json']
    result = subprocess.run(command, capture_output=True, text=True, timeout=8)
    if result.stderr:
        raise AssertionError(result.stderr)
    value = json.loads(result.stdout)
    if BUNDLE:
        BUNDLE.validate('urn:disked:schema:response:1', value)
        if isinstance(value['result'], dict) and 'state' in value['result']:
            BUNDLE.validate('urn:disked:schema:fake-operation:1', value['result']['state'])
    OBSERVATIONS.append(dict(command=command, exit_code=result.returncode, response=value))
    return result.returncode, value

def inspect(directory, ident):
    return invoke('operation', 'inspect', ident, '--state-dir', directory)

def await_outcome(directory, ident, timeout=6):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        code, result = inspect(directory, ident)
        state = result['result'].get('state', {})
        if state.get('phase') == 'finished' or result['result'].get('worker_observation') in ('exited', 'reused_identity'):
            return code, result
        time.sleep(.025)
    raise AssertionError('worker did not reach finite fixture outcome')

class Worker(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='disked-worker-')
        self.directory = Path(self.temp.name)
        self.ident = None

    def tearDown(self):
        # Product workers have a finite <3s workload. Retain open process handles
        # only in individual tests; cleanup never searches/kills by executable name.
        deadline = time.monotonic() + 6
        while True:
            try:
                self.temp.cleanup()
                break
            except PermissionError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(.025)

    def start(self, fixture='fake:complete'):
        code, value = invoke('plan', 'simulate', fixture, '--state-dir', self.directory)
        self.assertEqual(5, code, value)
        self.assertEqual('accepted_running', value['status'])
        self.ident = value['operation_id']
        self.assertRegex(self.ident, r'^fake-op:[0-9a-f]{32}$')
        return value

    def test_actual_self_image_identity_and_terminal_reconnect(self):
        initial = self.start('fake:cancel-checkpoint')
        binding = initial['result']['state']['binding']
        self.assertEqual(hashlib.sha256(Path(EXE).read_bytes()).hexdigest(), binding['image_digest'])
        process = K.OpenProcess(0x1000 | 0x100000, False, int(binding['process_id']))
        self.assertTrue(process)
        try:
            name = C.create_unicode_buffer(32768)
            size = W.DWORD(len(name))
            self.assertTrue(K.QueryFullProcessImageNameW(process, 0, name, C.byref(size)))
            self.assertEqual(Path(EXE), Path(name.value))
            times = [W.FILETIME() for _ in range(4)]
            self.assertTrue(K.GetProcessTimes(process, *map(C.byref, times)))
            self.assertEqual(int(binding['process_created']), times[0].dwLowDateTime | (times[0].dwHighDateTime << 32))
            memory = Memory()
            memory.cb = C.sizeof(memory)
            self.assertTrue(K.K32GetProcessMemoryInfo(process, C.byref(memory), C.sizeof(memory)))
            self.assertLess(memory.private, 128 * 1024 * 1024)
            sys.path.insert(0, str(ARGS.root / 'tests/frontend'))
            from gui_fixture import modules
            OBSERVATIONS.append(dict(test='worker_process', process_id=binding['process_id'], process_created=binding['process_created'],
                                     image=name.value, private_bytes=memory.private, peak_working_bytes=memory.peak_working,
                                     modules=modules(int(binding['process_id']))))
            self.assertEqual(0, K.WaitForSingleObject(process, 5000))
            exit_code = W.DWORD()
            self.assertTrue(K.GetExitCodeProcess(process, C.byref(exit_code)))
            self.assertEqual(0, exit_code.value)
        finally:
            K.CloseHandle(process)
        code, final = inspect(self.directory, self.ident)
        self.assertEqual(0, code, final)
        self.assertEqual('succeeded', final['result']['state']['outcome'])
        self.assertEqual('exited', final['result']['worker_observation'])
        self.assertEqual({'request.json', 'operation.records', 'cancel.request'}, {p.name for p in self.directory.iterdir()})
        records = [json.loads(line) for line in (self.directory / 'operation.records').read_bytes().splitlines()]
        if BUNDLE:
            for record in records:
                BUNDLE.validate('urn:disked:schema:fake-operation-record:1', record)
        OBSERVATIONS.append(dict(test='terminal_reconnect', records=records))

    def test_killed_stdio_client_does_not_own_worker_lifetime(self):
        sentinel_temp = tempfile.TemporaryDirectory(prefix='disked-inherit-')
        sentinel = Path(sentinel_temp.name) / 'sentinel.txt'
        sentinel.write_text('test-owned inheritance sentinel')
        sentinel_handle = K.CreateFileW(str(sentinel), 0x80000000, 1, None, 3, 0, None)
        self.assertNotEqual(C.c_void_p(-1).value, sentinel_handle)
        self.assertTrue(K.SetHandleInformation(sentinel_handle, 1, 1))
        process = subprocess.Popen([EXE, 'protocol', 'serve', '--format=ndjson'], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, close_fds=False)
        K.CloseHandle(sentinel_handle)
        try:
            request = dict(schema='org.disked.request/1', request_id='killed-client', command='plan.simulate',
                           parameters=dict(fixture_id='fake:cancel-checkpoint', state_directory=str(self.directory)), required_features=[])
            process.stdin.write(json.dumps(request) + '\n')
            process.stdin.flush()
            first = json.loads(process.stdout.readline())
            self.assertEqual('accepted_running', first['status'], first)
            self.ident = first['operation_id']
            self.assertIsNone(process.poll())
            with self.assertRaises(PermissionError):
                sentinel.rename(sentinel.with_name('moved.txt'))  # client really inherited the sentinel
            process.kill()
            process.wait(timeout=3)
            sentinel.rename(sentinel.with_name('moved.txt'))  # worker did not inherit it
            _, active = inspect(self.directory, self.ident)
            self.assertEqual('running', active['result']['worker_observation'])
            code, value = await_outcome(self.directory, self.ident)
            self.assertEqual(0, code, value)
            self.assertEqual('succeeded', value['result']['state']['outcome'])
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=3)
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()
            sentinel_temp.cleanup()

    def test_duplicate_has_one_identity_and_conflicting_start_is_refused(self):
        initial = self.start('fake:cancel-checkpoint')
        code, repeated = invoke('plan', 'simulate', 'fake:cancel-checkpoint', '--state-dir', self.directory)
        self.assertEqual(0, code, repeated)
        self.assertEqual(self.ident, repeated['operation_id'])
        self.assertEqual('existing', repeated['result']['admission'])
        self.assertEqual(initial['result']['state']['binding'], repeated['result']['state']['binding'])
        code, conflict = invoke('plan', 'simulate', 'fake:complete', '--state-dir', self.directory)
        self.assertEqual(2, code)
        self.assertEqual('idempotency_conflict', conflict['diagnostics'][0]['code'])
        await_outcome(self.directory, self.ident)

    def test_cancellation_acknowledges_only_before_dispatch(self):
        self.start('fake:cancel-checkpoint')
        code, receipt = invoke('op', 'cancel', self.ident, '--state-dir', self.directory)
        self.assertEqual(0, code, receipt)
        self.assertEqual('requested', receipt['result']['cancellation_request'])
        code, final = await_outcome(self.directory, self.ident)
        self.assertEqual(0, code, final)
        state = final['result']['state']
        self.assertEqual(('cancelled', 'acknowledged', 'not_started', '0'),
                         tuple(state[k] for k in ('outcome', 'cancellation', 'effect_certainty', 'synthetic_effect_count')))
        _, late = invoke('op', 'cancel', self.ident, '--state-dir', self.directory)
        self.assertEqual('too_late', late['result']['cancellation_request'])

    def test_cancel_after_dispatch_preserves_completed_effect(self):
        self.start()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            _, value = inspect(self.directory, self.ident)
            if value['result'].get('state', {}).get('phase') == 'in_flight':
                break
            time.sleep(.015)
        else:
            self.fail('did not observe in-flight effect')
        _, receipt = invoke('operation', 'cancel', self.ident, '--state-dir', self.directory)
        self.assertEqual('requested', receipt['result']['cancellation_request'])
        _, value = await_outcome(self.directory, self.ident)
        self.assertEqual(('succeeded', 'requested', '1'), tuple(value['result']['state'][k] for k in ('outcome', 'cancellation', 'synthetic_effect_count')))

    def test_verification_failure_remains_inspectable(self):
        self.start('fake:verification-failure')
        code, value = await_outcome(self.directory, self.ident)
        self.assertEqual(0, code, value)  # successful read, independently failed operation
        self.assertEqual(('verification_failed', 'unresolved', 'required'),
                         tuple(value['result']['state'][k] for k in ('outcome', 'logical_state', 'recovery')))

    def test_admission_timeout_does_not_kill_or_restart_worker(self):
        started = time.monotonic()
        code, value = invoke('plan', 'simulate', 'fake:complete', '--state-dir', self.directory,
                             executable=str(Path(ARGS.delayed).resolve()))
        elapsed = time.monotonic() - started
        self.assertEqual(6, code, value)
        self.assertEqual('operation_admission_unresolved', value['diagnostics'][0]['code'])
        self.assertLess(elapsed, 4.7, 'parent waited for the delayed worker instead of its 3-second admission bound')
        self.ident = value['operation_id']
        code, repeated = invoke('plan', 'simulate', 'fake:complete', '--state-dir', self.directory,
                                executable=str(Path(ARGS.delayed).resolve()))
        self.assertEqual(6, code, repeated)
        self.assertEqual(self.ident, repeated['operation_id'])
        code, final = await_outcome(self.directory, self.ident)
        self.assertEqual(0, code, final)
        self.assertEqual('succeeded', final['result']['state']['outcome'])
        self.assertEqual(self.ident, final['result']['state']['binding']['operation_id'])
        OBSERVATIONS.append(dict(test='admission_timeout', elapsed_seconds=elapsed, response=value, final=final))

    def test_worker_exit_during_effect_is_unknown_and_never_retried(self):
        self.start('fake:unknown')
        code, value = await_outcome(self.directory, self.ident)
        self.assertEqual(6, code, value)
        self.assertEqual('unknown', value['status'])
        self.assertEqual('in_flight', value['result']['state']['effect_certainty'])
        before = (self.directory / 'operation.records').read_bytes()
        code, repeated = invoke('plan', 'simulate', 'fake:unknown', '--state-dir', self.directory)
        self.assertEqual(6, code, repeated)
        self.assertEqual(self.ident, repeated['operation_id'])
        self.assertEqual(before, (self.directory / 'operation.records').read_bytes())

    def test_killed_worker_retains_uncertainty_and_prevents_second_writer(self):
        value = self.start('fake:cancel-checkpoint')
        # A second writer cannot modify the held journal, even within this user.
        raw = K.CreateFileW(str(self.directory / 'operation.records'), 0x40000000, 3, None, 3, 0, None)
        self.assertEqual(C.c_void_p(-1).value, raw)
        self.assertEqual(32, C.get_last_error())
        process = K.OpenProcess(0x100001, False, int(value['result']['state']['binding']['process_id']))
        self.assertTrue(process)
        try:
            self.assertTrue(K.TerminateProcess(process, 88))
            self.assertEqual(0, K.WaitForSingleObject(process, 3000))
        finally:
            K.CloseHandle(process)
        code, final = inspect(self.directory, self.ident)
        self.assertEqual(6, code, final)
        self.assertEqual('not_started', final['result']['state']['effect_certainty'])
        self.assertIsNone(final['result']['state']['outcome'])

    def test_corrupt_and_partial_history_never_reports_success_or_repairs(self):
        self.start()
        await_outcome(self.directory, self.ident)
        path = self.directory / 'operation.records'
        original = path.read_bytes()
        for corrupt in (original[:-1], original.replace(b'fake-only', b'fake-mess', 1)):
            path.write_bytes(corrupt)
            code, value = inspect(self.directory, self.ident)
            self.assertEqual(6, code, value)
            self.assertEqual('unknown', value['status'])
            self.assertEqual(corrupt, path.read_bytes())

    def test_invalid_commands_create_no_files_or_provider(self):
        for arguments in (('plan', 'simulate', 'physical:0', '--state-dir', self.directory),
                          ('plan', 'simulate', 'fake:complete', '--state-dir', 'relative'),
                          ('operation', 'inspect', 'not-an-operation', '--state-dir', self.directory),
                          ('plan', 'simulate', 'fake:complete')):
            code, value = invoke(*arguments, executable=str(Path(ARGS.guard).resolve()))
            self.assertEqual(2, code, value)
            self.assertEqual([], list(self.directory.iterdir()))

    def test_wrong_operation_identity_and_nonempty_directory_refused(self):
        (self.directory / 'owned.txt').write_text('sentinel')
        code, value = invoke('plan', 'simulate', 'fake:complete', '--state-dir', self.directory)
        self.assertEqual(2, code, value)
        self.assertEqual('operation_directory_not_empty', value['diagnostics'][0]['code'])
        self.assertEqual(['owned.txt'], [p.name for p in self.directory.iterdir()])
        (self.directory / 'owned.txt').unlink()
        self.start()
        code, value = inspect(self.directory, 'fake-op:' + '0' * 32)
        self.assertEqual(2, code, value)
        self.assertEqual('operation_identity_mismatch', value['diagnostics'][0]['code'])
        await_outcome(self.directory, self.ident)

    def test_incomplete_claim_cannot_readmit_work(self):
        claim = self.directory / 'request.json'
        claim.write_bytes(b'{"schema":')
        code, value = invoke('plan', 'simulate', 'fake:complete', '--state-dir', self.directory)
        self.assertEqual(6, code, value)
        self.assertIsNone(value['operation_id'])
        self.assertEqual('operation_existing_claim_unreadable', value['diagnostics'][0]['code'])
        self.assertEqual(b'{"schema":', claim.read_bytes())
        self.assertEqual(['request.json'], [p.name for p in self.directory.iterdir()])

    def test_evidence_files_have_explicit_current_user_dacls(self):
        self.start('fake:cancel-checkpoint')
        script = """$sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$files=@('request.json','operation.records','cancel.request') | ForEach-Object {
 $acl=Get-Acl -LiteralPath (Join-Path $env:DISKED_TEST_STATE $_)
 [PSCustomObject]@{name=$_;protected=$acl.AreAccessRulesProtected;aces=@($acl.Access | ForEach-Object {
  [PSCustomObject]@{sid=$_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value;type=$_.AccessControlType.ToString();rights=[int64]$_.FileSystemRights;inherited=$_.IsInherited}
 })}
}
[PSCustomObject]@{current_sid=$sid;files=@($files)} | ConvertTo-Json -Depth 5 -Compress
"""
        environment = dict(os.environ, DISKED_TEST_STATE=str(self.directory))
        result = subprocess.run(['pwsh', '-NoProfile', '-NonInteractive', '-Command', script], env=environment,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(0, result.returncode, result.stderr)
        acl = json.loads(result.stdout)
        for file in acl['files']:
            self.assertTrue(file['protected'])
            self.assertEqual([dict(sid=acl['current_sid'], type='Allow', rights=0x1f01ff, inherited=False)], file['aces'])
        OBSERVATIONS.append(dict(test='current_user_dacl', acl=acl))
        invoke('operation', 'cancel', self.ident, '--state-dir', self.directory)
        await_outcome(self.directory, self.ident)

    def test_private_role_has_no_public_path_or_command_execution(self):
        result = subprocess.run([EXE, '__disked_fake_worker', str(self.directory), '1', '2', '3'],
                                capture_output=True, timeout=3)
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(b'', result.stdout)
        self.assertEqual(b'', result.stderr)
        self.assertEqual([], list(self.directory.iterdir()))

if __name__ == '__main__':
    programme = unittest.main(argv=[__file__] + REST, exit=False)
    if ARGS.evidence:
        ARGS.evidence.parent.mkdir(parents=True, exist_ok=True)
        ARGS.evidence.write_text(json.dumps(dict(executable=EXE, sha256=hashlib.sha256(Path(EXE).read_bytes()).hexdigest(),
            tests=programme.result.testsRun, passed=programme.result.wasSuccessful(), producer_schemas=ARGS.validate_schemas,
            observations=OBSERVATIONS), indent=2) + '\n', encoding='utf-8')
    raise SystemExit(0 if programme.result.wasSuccessful() else 1)
