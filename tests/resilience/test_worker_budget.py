"""Measure the shared job using only owned fake workers and disposable files."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

P = argparse.ArgumentParser()
P.add_argument('--exe', type=Path, required=True)
P.add_argument('--delayed', type=Path, required=True)
P.add_argument('--memory', type=Path, required=True)
P.add_argument('--evidence', type=Path)
ARGS, REST = P.parse_known_args()
ARGS.exe = ARGS.exe.resolve(); ARGS.delayed = ARGS.delayed.resolve()
ARGS.memory = ARGS.memory.resolve()
OBSERVATIONS = []
K = C.WinDLL('kernel32', use_last_error=True)
K.OpenJobObjectW.argtypes = [W.DWORD, W.BOOL, W.LPCWSTR]
K.OpenJobObjectW.restype = W.HANDLE
K.QueryInformationJobObject.argtypes = [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p]
K.CloseHandle.argtypes = [W.HANDLE]
K.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
K.OpenProcess.restype = W.HANDLE
K.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
K.GetProcessTimes.argtypes = [W.HANDLE] + [C.POINTER(W.FILETIME)] * 4
K.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)]
K.GetExitCodeProcess.argtypes = [W.HANDLE, C.POINTER(W.DWORD)]

class Basic(C.Structure):
    _fields_ = [('process_time', C.c_int64), ('job_time', C.c_int64), ('flags', W.DWORD),
                ('minimum_working', C.c_size_t), ('maximum_working', C.c_size_t), ('active_limit', W.DWORD),
                ('affinity', C.c_size_t), ('priority', W.DWORD), ('scheduling', W.DWORD)]
class Limits(C.Structure):
    _fields_ = [('basic', Basic), ('io', C.c_uint64 * 6), ('process_memory', C.c_size_t),
                ('job_memory', C.c_size_t), ('peak_process', C.c_size_t), ('peak_job', C.c_size_t)]
class Processes(C.Structure):
    _fields_ = [('assigned', W.DWORD), ('listed', W.DWORD), ('ids', C.c_size_t * 8)]
class Accounting(C.Structure):
    _fields_ = [('time', C.c_int64 * 4), ('faults', W.DWORD), ('total', W.DWORD),
                ('active', W.DWORD), ('terminated', W.DWORD)]

def query(job, kind, record):
    if not K.QueryInformationJobObject(job, kind, C.byref(record), C.sizeof(record), None):
        raise C.WinError(C.get_last_error())
    return record

def eventually(callback, timeout=3):
    deadline = time.monotonic() + timeout
    while True:
        value = callback()
        if value: return value
        if time.monotonic() >= deadline: raise AssertionError('bounded fixture wait expired')
        time.sleep(.01)

def header(directory):
    try: return json.loads((directory / 'request.json').read_bytes())
    except (FileNotFoundError, json.JSONDecodeError): return None

def launch(directory):
    return subprocess.Popen([str(ARGS.delayed), 'plan', 'simulate', 'fake:complete', '--state-dir', str(directory), '--json'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def outcome(process):
    stdout, stderr = process.communicate(timeout=8)
    if stderr: raise AssertionError(stderr)
    return process.returncode, json.loads(stdout)

class Budget(unittest.TestCase):
    def test_actual_allocation_failure_retains_unresolved_operation(self):
        with tempfile.TemporaryDirectory(prefix='disked-memory-') as directory:
            result = subprocess.run([str(ARGS.memory), 'plan', 'simulate', 'fake:complete', '--state-dir', directory, '--json'],
                                    capture_output=True, text=True, timeout=8)
            self.assertEqual(5, result.returncode, result.stdout)
            admitted = json.loads(result.stdout); binding = admitted['result']['state']['binding']
            handle = K.OpenProcess(0x1000 | 0x100000, False, int(binding['process_id']))
            self.assertTrue(handle)
            job = K.OpenJobObjectW(4, False, 'Local\\DiskEd.Fake.Workers.v1.' + binding['host_id'])
            self.assertTrue(job)
            try:
                times = [W.FILETIME() for _ in range(4)]
                self.assertTrue(K.GetProcessTimes(handle, *map(C.byref, times)))
                self.assertEqual(int(binding['process_created']), times[0].dwLowDateTime | (times[0].dwHighDateTime << 32))
                self.assertEqual(0, K.WaitForSingleObject(handle, 5000))
                exit_code = W.DWORD(); self.assertTrue(K.GetExitCodeProcess(handle, C.byref(exit_code)))
                self.assertIn(exit_code.value, (8, 1455, 1816), 'test-only worker did not encounter a memory/commit/quota denial')
                memory = query(job, 9, Limits())
                self.assertGreaterEqual(memory.peak_process, 96*1024*1024)
                self.assertLessEqual(memory.peak_process, 128*1024*1024)
                inspected = subprocess.run([str(ARGS.exe), 'operation', 'inspect', admitted['operation_id'],
                    '--state-dir', directory, '--json'], capture_output=True, text=True, timeout=8)
                self.assertEqual(6, inspected.returncode, inspected.stdout)
                value = json.loads(inspected.stdout)
                self.assertEqual('unknown', value['status']); self.assertEqual('not_started', value['result']['state']['effect_certainty'])
                self.assertIsNone(value['result']['state']['outcome'])
                before = {p.name: p.read_bytes() for p in Path(directory).iterdir()}
                retry = subprocess.run([str(ARGS.memory), 'plan', 'simulate', 'fake:complete', '--state-dir', directory, '--json'],
                                       capture_output=True, text=True, timeout=8)
                self.assertEqual(6, retry.returncode); self.assertEqual(admitted['operation_id'], json.loads(retry.stdout)['operation_id'])
                self.assertEqual(before, {p.name: p.read_bytes() for p in Path(directory).iterdir()})
                OBSERVATIONS.append(dict(test='actual committed-memory denial in test-only worker',
                    executable=str(ARGS.memory), sha256=hashlib.sha256(ARGS.memory.read_bytes()).hexdigest(),
                    process_memory_limit=memory.process_memory, peak_process_bytes=memory.peak_process,
                    worker_exit=exit_code.value, outcome=value))
            finally:
                K.WaitForSingleObject(handle, 5000); K.CloseHandle(handle); K.CloseHandle(job)

    def test_four_workers_hold_the_limit_across_disconnected_clients(self):
        temp = tempfile.TemporaryDirectory(prefix='disked-budget-')
        processes, workers = [], []
        job = None
        try:
            directories = [Path(temp.name) / str(i) for i in range(5)]
            for directory in directories: directory.mkdir()
            started = time.monotonic()
            processes.append(launch(directories[0]))
            first = eventually(lambda: header(directories[0]))
            name = 'Local\\DiskEd.Fake.Workers.v1.' + first['definition']['host_id']
            job = eventually(lambda: K.OpenJobObjectW(4, False, name))  # query only
            eventually(lambda: query(job, 3, Processes()).listed == 1)
            for directory in directories[1:4]: processes.append(launch(directory))
            eventually(lambda: query(job, 3, Processes()).listed == 4)
            members = query(job, 3, Processes())
            self.assertEqual(4, members.assigned)
            identities = {}
            for pid in members.ids[:members.listed]:
                handle = K.OpenProcess(0x1000 | 0x100000, False, pid)
                self.assertTrue(handle); workers.append(handle)
                times = [W.FILETIME() for _ in range(4)]
                self.assertTrue(K.GetProcessTimes(handle, *map(C.byref, times)))
                path = C.create_unicode_buffer(32768); length = W.DWORD(len(path))
                self.assertTrue(K.QueryFullProcessImageNameW(handle, 0, path, C.byref(length)))
                self.assertEqual(ARGS.delayed, Path(path.value))
                identities[str(pid)] = str(times[0].dwLowDateTime | (times[0].dwHighDateTime << 32))
            limits = query(job, 9, Limits())
            self.assertEqual((0x308, 4, 128*1024*1024, 512*1024*1024),
                             (limits.basic.flags, limits.basic.active_limit, limits.process_memory, limits.job_memory))
            fifth = launch(directories[4]); processes.append(fifth)
            fifth_code, fifth_result = outcome(fifth)
            self.assertEqual(6, fifth_code, fifth_result)
            self.assertEqual('unknown', fifth_result['status'])
            self.assertEqual('operation_spawn_failed', fifth_result['diagnostics'][0]['code'])
            self.assertEqual(4, query(job, 3, Processes()).listed)
            self.assertEqual(b'', (directories[4] / 'operation.records').read_bytes())
            responses = [outcome(process) for process in processes[:4]]
            self.assertTrue(all(code == 6 and value['status'] == 'unknown' for code, value in responses), responses)
            # Every client has exited after its 3s bound. All four workers still
            # occupy their slots during the test-only 5s admission delay.
            self.assertEqual(4, query(job, 3, Processes()).listed)
            self.assertTrue(all(K.WaitForSingleObject(handle, 0) == 258 for handle in workers))
            for handle in workers: self.assertEqual(0, K.WaitForSingleObject(handle, 8000))
            self.assertEqual(0, query(job, 3, Processes()).listed)
            finals = []
            for directory, (_, admitted) in zip(directories, responses):
                result = subprocess.run([str(ARGS.exe), 'operation', 'inspect', admitted['operation_id'],
                                         '--state-dir', str(directory), '--json'], capture_output=True, text=True, timeout=8)
                self.assertEqual(0, result.returncode, result.stdout)
                final = json.loads(result.stdout); binding = final['result']['state']['binding']
                self.assertEqual(identities[binding['process_id']], binding['process_created'])
                self.assertEqual('succeeded', final['result']['state']['outcome']); finals.append(final)
            # A now-free slot does not turn an existing unresolved claim into a
            # retry. The fifth store retains its exact bytes and operation ID.
            before = {p.name: p.read_bytes() for p in directories[4].iterdir()}
            repeated = launch(directories[4]); processes.append(repeated)
            code, value = outcome(repeated)
            self.assertEqual(6, code, value); self.assertEqual(fifth_result['operation_id'], value['operation_id'])
            self.assertEqual(before, {p.name: p.read_bytes() for p in directories[4].iterdir()})
            self.assertEqual(0, query(job, 3, Processes()).listed)
            accounting = query(job, 1, Accounting()); memory = query(job, 9, Limits())
            self.assertLessEqual(memory.peak_process, 128*1024*1024)
            self.assertLessEqual(memory.peak_job, 512*1024*1024)
            OBSERVATIONS.append(dict(scope='current user and Windows logon session; cooperating fake composition',
                elapsed_seconds=time.monotonic()-started, identities=identities,
                flags=limits.basic.flags, max_workers=limits.basic.active_limit,
                process_memory_limit=limits.process_memory, job_memory_limit=limits.job_memory,
                peak_process_bytes=memory.peak_process, peak_job_bytes=memory.peak_job,
                total_assigned=accounting.total, fifth=fifth_result, retry=value, finals=finals))
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill(); process.wait(timeout=3)  # owned clients only
                for stream in (process.stdout, process.stderr):
                    if stream: stream.close()
            for handle in workers: K.WaitForSingleObject(handle, 8000); K.CloseHandle(handle)
            if job: K.CloseHandle(job)
            # Also cover a fixture assertion before process identities arrived.
            # Waiting for these finite test fixtures is not a quiescence claim.
            deadline = time.monotonic() + 8
            while True:
                try: temp.cleanup(); break
                except PermissionError:
                    if time.monotonic() >= deadline: raise
                    time.sleep(.025)

if __name__ == '__main__':
    programme = unittest.main(argv=[__file__]+REST, verbosity=2, exit=False)
    if ARGS.evidence:
        ARGS.evidence.write_text(json.dumps(dict(tests=programme.result.testsRun, passed=programme.result.wasSuccessful(),
            executable=str(ARGS.delayed), sha256=hashlib.sha256(ARGS.delayed.read_bytes()).hexdigest(),
            observations=OBSERVATIONS), indent=2)+'\n', encoding='utf-8', newline='\n')
    raise SystemExit(not programme.result.wasSuccessful())
