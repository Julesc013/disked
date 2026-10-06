"""Actual frontend commitment limits and host-policy preservation on Windows."""
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from memory_fixture import AssignedProcess, Job, K, MIB, checked, limits, member, memory, name
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'frontend'))
from gui_fixture import Gui, modules

P = argparse.ArgumentParser()
P.add_argument('--exe', type=Path, required=True)
P.add_argument('--fault', type=Path, required=True)
P.add_argument('--evidence', type=Path)
ARGS, REST = P.parse_known_args()
ARGS.exe = ARGS.exe.resolve(); ARGS.fault = ARGS.fault.resolve()
OBSERVATIONS = []

def request(index):
    return dict(schema='org.disked.request/1', request_id='memory:'+str(index), command='target.list',
                parameters={}, required_features=[])

def peak(process, cap):
    observations = []
    until = time.monotonic() + 5
    while process.poll() is None:
        observations.append(memory(process.handle))
        if time.monotonic() > until: raise TimeoutError('bounded allocation observation')
        time.sleep(.015)
    if not observations: raise AssertionError('allocation process was never observed alive')
    result = max(observations, key=lambda x: x['peak_commit_bytes'])
    if result['peak_commit_bytes'] > cap: raise AssertionError(result)
    return result

class FrontendMemory(unittest.TestCase):
    def receipt(self, result, diagnostic):
        code, out, err = result
        self.assertEqual(3, code, out+err); self.assertEqual(b'', err)
        value = json.loads(out)
        self.assertEqual('refused', value['status']); self.assertIsNone(value['operation_id'])
        self.assertEqual(diagnostic, value['diagnostics'][0]['code'])
        self.assertEqual(str(256*MIB), value['diagnostics'][0]['parameters']['process_limit_bytes'])
        return value

    def test_repeated_gui_workload(self):
        g = Gui(ARGS.exe, render=True); job = None
        try:
            job = checked(K.OpenJobObjectW(4, False, name()))
            self.assertTrue(member(g.process.handle, job))
            samples = []
            for _ in range(128):
                g.click(104); g.choose(0); g.click(108)
                self.assertEqual('fake:alpha@1', g.details()['result']['target']['id'])
                samples.append(memory(g.process.handle))
            self.assertLessEqual(max(s['peak_commit_bytes'] for s in samples), 256*MIB)
            OBSERVATIONS.append(dict(test='128 cached GUI inspections on private desktop', samples=samples,
                                     limits=limits(job), modules=modules(g.process.pid), final_response=g.details()))
        finally:
            if job: K.CloseHandle(job)
            g.close()
        self.assertEqual(0, g.code); self.assertEqual([], g.created_files)

    def test_repeated_console_workloads_restore_caller(self):
        for frontend in ('shell', 'tui'):
            with self.subTest(frontend=frontend), tempfile.TemporaryDirectory(prefix='disked-memory-console-') as directory:
                report = Path(directory)/'report.json'
                startup = subprocess.STARTUPINFO(); startup.dwFlags = subprocess.STARTF_USESHOWWINDOW; startup.wShowWindow = 0
                p = subprocess.run([sys.executable, str(Path(__file__).with_name('console_memory_fixture.py')),
                    str(ARGS.exe), str(report), frontend], cwd=directory, creationflags=subprocess.CREATE_NEW_CONSOLE,
                    startupinfo=startup, timeout=45)
                value = json.loads(report.read_text()); OBSERVATIONS.append(value)
                self.assertEqual(0, p.returncode, json.dumps(value, indent=2)); self.assertNotIn('fixture_error', value)

    def test_256_protocol_requests_share_one_bounded_frontend(self):
        with tempfile.TemporaryDirectory(prefix='disked-memory-protocol-') as directory:
            p = subprocess.Popen([str(ARGS.exe), 'protocol', 'serve', '--format=ndjson'], cwd=directory,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            job = None
            try:
                samples = []
                for i in range(256):
                    p.stdin.write(json.dumps(request(i)).encode()+b'\n'); p.stdin.flush()
                    value = json.loads(p.stdout.readline())
                    self.assertEqual('memory:'+str(i), value['request_id']); self.assertEqual('completed', value['status'])
                    if job is None: job = checked(K.OpenJobObjectW(4, False, name()))
                    self.assertTrue(member(int(p._handle), job))
                    samples.append(memory(int(p._handle)))
                observed = limits(job)
                observed_modules = modules(p.pid)
                self.assertEqual((0x100, 256*MIB, 0, 0),
                                 (observed['flags'], observed['process_bytes'], observed['job_bytes'], observed['active_limit']))
                self.assertLessEqual(max(s['peak_commit_bytes'] for s in samples), 256*MIB)
                p.stdin.close(); p.stdin = None
                out, err = p.communicate(timeout=5)
                self.assertEqual((0, b'', b''), (p.returncode, out, err))
                self.assertEqual([], list(Path(directory).iterdir()))
                OBSERVATIONS.append(dict(test='maximum NDJSON session', requests=256, limits=observed,
                                         samples=samples, modules=observed_modules, final_response=value))
            finally:
                if p.poll() is None: p.kill(); p.wait(timeout=3)
                for stream in (p.stdin, p.stdout, p.stderr):
                    if stream: stream.close()
                if job: K.CloseHandle(job)

    def test_actual_commit_denial_and_stricter_inherited_budget(self):
        env = dict(os.environ, DISKED_TEST_MEMORY_FAULT='allocate')
        for host_cap in (512*MIB, 64*MIB):
            with self.subTest(host_cap=host_cap), Job(host_cap) as host:
                before = limits(host.handle)
                with AssignedProcess([ARGS.fault, 'build', 'inspect', '--json'], host, env) as p:
                    self.assertTrue(member(p.handle, host.handle))
                    measured = peak(p, min(host_cap, 256*MIB))
                    value = self.receipt(p.result(), 'memory_budget_unavailable')
                    diagnostic = value['diagnostics'][0]
                    self.assertIn(int(diagnostic['platform_code']), (8, 1455, 1816))
                    allocated = int(diagnostic['parameters']['test_allocation_bytes'])
                    self.assertGreaterEqual(allocated, min(host_cap, 256*MIB)-32*MIB)
                    self.assertLess(allocated, min(host_cap, 256*MIB))
                after = limits(host.handle)
                for key in ('flags', 'process_bytes', 'job_bytes', 'active_limit'):
                    self.assertEqual(before[key], after[key])
                OBSERVATIONS.append(dict(test='actual allocation denial with inherited host job',
                    host_limit=host_cap, effective_limit=min(host_cap, 256*MIB), memory=measured, before=before, after=after, response=value))

    def test_existing_mismatch_is_not_rewritten(self):
        with Job(128*MIB, name(test=True)) as existing, tempfile.TemporaryDirectory(prefix='disked-memory-mismatch-') as directory:
            before = limits(existing.handle)
            result = subprocess.run([str(ARGS.fault), 'build', 'inspect', '--json'], cwd=directory,
                                    capture_output=True, timeout=5)
            value = self.receipt((result.returncode, result.stdout, result.stderr), 'memory_budget_mismatch')
            self.assertEqual(before, limits(existing.handle)); self.assertEqual([], list(Path(directory).iterdir()))
            invalid = subprocess.run([str(ARGS.fault), 'build', 'inspect', '--bad-option', '--json'],
                                     cwd=directory, capture_output=True, timeout=5)
            self.assertEqual(2, invalid.returncode)
            self.assertEqual('unknown_option', json.loads(invalid.stdout)['diagnostics'][0]['code'])
            OBSERVATIONS.append(dict(test='mismatch retained and invalid syntax independent', before=before, response=value))

    def test_initialization_contention_is_bounded(self):
        mutex = checked(K.CreateMutexW(None, True, name(test=True, mutex=True)))
        if C.get_last_error() == 183:
            K.CloseHandle(mutex); self.fail('isolated initialization mutex already exists')
        try:
            started = time.monotonic()
            result = subprocess.run([str(ARGS.fault), 'build', 'inspect', '--json'], capture_output=True, timeout=5)
            elapsed = time.monotonic()-started
            value = self.receipt((result.returncode, result.stdout, result.stderr), 'memory_budget_busy')
            self.assertEqual('258', value['diagnostics'][0]['platform_code'])
            self.assertGreaterEqual(elapsed, .23); self.assertLess(elapsed, 2)
            OBSERVATIONS.append(dict(test='initialization contention', elapsed_seconds=elapsed, response=value))
        finally: K.ReleaseMutex(mutex); K.CloseHandle(mutex)

    def test_host_ui_restriction_is_preserved_when_nesting_succeeds(self):
        with Job(128*MIB, ui=True) as host:
            before = limits(host.handle)
            with AssignedProcess([ARGS.fault, 'build', 'inspect', '--json'], host) as p:
                code, out, err = p.result()
                self.assertEqual((0, b''), (code, err)); value = json.loads(out)
                self.assertEqual('completed', value['status'])
            after = limits(host.handle)
            for key in ('flags', 'process_bytes', 'job_bytes', 'active_limit'):
                self.assertEqual(before[key], after[key])
            restriction = C.c_ulong()
            checked(K.QueryInformationJobObject(host.handle, 4, C.byref(restriction), C.sizeof(restriction), None))
            self.assertEqual(1, restriction.value)
            OBSERVATIONS.append(dict(test='observed compatible host UI restriction retained', before=before, after=after,
                                     ui_restrictions=restriction.value, response=value))

    def test_incompatible_host_hierarchies_refuse_without_weakening(self):
        # A live member under host A makes this common job a subset of A. A
        # process already under the independent host B cannot join that chain.
        env = dict(os.environ, DISKED_TEST_MEMORY_FAULT='allocate')
        with Job(512*MIB) as first_host, Job(64*MIB) as second_host:
            with AssignedProcess([ARGS.fault, 'build', 'inspect', '--json'], first_host, env) as first:
                job = None
                try:
                    deadline = time.monotonic()+2
                    while not job:
                        job = K.OpenJobObjectW(4, False, name(test=True))
                        if time.monotonic()>deadline: self.fail('no common test job')
                        if not job: time.sleep(.005)
                    while not member(first.handle, job):
                        self.assertIsNone(first.poll())
                        self.assertLess(time.monotonic(), deadline); time.sleep(.005)
                    before = limits(second_host.handle)
                    with AssignedProcess([ARGS.fault, 'build', 'inspect', '--json'], second_host) as second:
                        value = self.receipt(second.result(), 'memory_budget_incompatible')
                    self.assertIsNone(first.poll(), 'independent first process was terminated')
                    after = limits(second_host.handle)
                    for key in ('flags', 'process_bytes', 'job_bytes', 'active_limit'):
                        self.assertEqual(before[key], after[key])
                    first_value = self.receipt(first.result(), 'memory_budget_unavailable')
                    OBSERVATIONS.append(dict(test='incompatible independent host hierarchies', before=before,
                                             after=after, response=value, first_response=first_value))
                finally:
                    if job: K.CloseHandle(job)

    def test_product_ignores_private_allocation_control(self):
        env = dict(os.environ, DISKED_TEST_MEMORY_FAULT='allocate')
        result = subprocess.run([str(ARGS.exe), 'build', 'inspect', '--json'], env=env, capture_output=True, timeout=5)
        self.assertEqual((0, b''), (result.returncode, result.stderr))
        value = json.loads(result.stdout); self.assertEqual('completed', value['status'])
        self.assertEqual([], value['diagnostics'])
        OBSERVATIONS.append(dict(test='product ignores private memory control', response=value))

if __name__ == '__main__':
    programme = unittest.main(argv=[__file__]+REST, verbosity=2, exit=False)
    if ARGS.evidence:
        ARGS.evidence.write_text(json.dumps(dict(tests=programme.result.testsRun, passed=programme.result.wasSuccessful(),
            executable=str(ARGS.exe), sha256=hashlib.sha256(ARGS.exe.read_bytes()).hexdigest(),
            fault_executable=str(ARGS.fault), fault_sha256=hashlib.sha256(ARGS.fault.read_bytes()).hexdigest(),
            observations=OBSERVATIONS), indent=2)+'\n', encoding='utf-8', newline='\n')
    raise SystemExit(not programme.result.wasSuccessful())
