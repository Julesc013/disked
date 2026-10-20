"""Raw-byte adapter for the existing confined Windows guest launcher.

The caller supplies its worker, bounded job factory and verified job retirement.
This module grants no permissions and is not an execution qualification record.
"""
import hashlib
import math
import os
from pathlib import Path
import stat
import time


def ordinary(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or getattr(info, 'st_file_attributes', 0) & 0x400:
        raise ValueError('Raw stdio must remain an ordinary single-link file')
    return info


class WindowsFileExecutor:
    def __init__(self, worker, environment, new_job, retire_job):
        self.worker, self.environment = worker, dict(environment)
        self.new_job, self.retire_job = new_job, retire_job
        self.observations = []
        self.active_job = self.child = None
        self.poisoned = False
        self.calls = 0

    def __call__(self, *, argv, cwd, payload, timeout, output_limit):
        if self.poisoned or self.active_job is not None:
            raise RuntimeError('Executor has an unresolved call;reuse is prohibited')
        if (not isinstance(argv, list) or not argv or not all(isinstance(v, str) and v and '\0' not in v for v in argv) or
                payload is not None and type(payload) is not bytes or
                len(payload or b'') > 2097152 or type(timeout) not in (float, int) or not math.isfinite(timeout) or not 0 < timeout <= 300 or
                type(output_limit) is not int or not 0 < output_limit <= 1048576):
            raise ValueError('Invalid bounded native invocation')
        cwd = self.worker.base.plain_directory(cwd)
        if not cwd.is_relative_to(self.worker.work):raise ValueError('Invocation cwd escaped owned work')
        self.calls += 1
        if self.calls > 256:raise ValueError('Executor call bound')
        request = self.worker.work / ('raw-input-' + str(self.calls))
        body = payload or b''
        with request.open('xb') as stream:stream.write(body)
        row = dict(index=self.calls, argv=list(argv), stdin_bytes=len(body),
                   stdin_sha256=hashlib.sha256(body).hexdigest(), timeout=timeout, output_limit=output_limit,
                   temporary_files_removed=False, terminal=False)
        self.observations.append(row)
        started = time.monotonic(); outcome = 'exited'; code = None
        paths = dict(stdin=request)
        try:
            self.active_job = self.new_job()
            self.child = self.worker.launch(argv, self.environment, self.active_job, variant='basic-raw-stdio', raw_input=request, cwd=cwd)
            paths = dict(self.worker.raw_paths)
            row['launch'] = self.worker.last_launch
            while True:
                sizes = {name: ordinary(paths[name]).st_size for name in ('stdout', 'stderr')}
                code = self.child.poll()
                if sum(sizes.values()) > output_limit:
                    outcome = 'output_limit';break
                if code is not None:break
                if time.monotonic() - started >= timeout:
                    outcome = 'timeout';break
                time.sleep(.01)
            row['job_retirement'] = self.retire_job(self.active_job)
            if row['job_retirement'].get('active_processes') != 0:
                raise RuntimeError('Owned job quiescence unverified')
            self.active_job = None
            final_code = self.child.wait(timeout=1)
            if code is None:code = final_code
            self.child.close();self.child = None
            row['terminal'] = True
            for name,path in paths.items():
                ordinary(path)
                if self.worker.file_identity(path)!=row['launch']['stdio_identities'][name]:
                    raise ValueError('Native stdio file identity changed')
            with request.open('rb') as stream:after_input=stream.read(len(body)+1)
            if ordinary(request).st_size != len(body) or after_input != body:
                raise ValueError('Native stdin changed during invocation')
            buffers = {}; left = output_limit
            row['produced_bytes'] = {name: ordinary(paths[name]).st_size for name in ('stdout', 'stderr')}
            if sum(row['produced_bytes'].values()) > output_limit:outcome = 'output_limit'
            for name in ('stdout', 'stderr'):
                with paths[name].open('rb') as stream:buffers[name] = stream.read(left)
                left -= len(buffers[name])
            row.update(outcome=outcome, exit_code=code, elapsed_seconds=time.monotonic() - started,
                       returned_bytes={k: len(v) for k, v in buffers.items()},
                       stream_sha256={k: hashlib.sha256(v).hexdigest() for k, v in buffers.items()})
            for name,path in paths.items():
                ordinary(path)
                if self.worker.file_identity(path)!=row['launch']['stdio_identities'][name]:raise ValueError('Native stdio changed before cleanup')
                path.unlink()
            row['temporary_files_removed'] = True
            return dict(outcome=outcome, exit_code=code, elapsed_seconds=row['elapsed_seconds'], terminal=True, **buffers)
        except BaseException:
            self.poisoned = True
            row['launch'] = self.worker.last_launch
            row['stdio_paths'] = {k:str(v) for k,v in getattr(self.worker,'raw_paths',{}).items()}
            raise
        finally:
            if self.active_job is not None:
                try:
                    row['failure_retirement'] = self.retire_job(self.active_job)
                    if row['failure_retirement'].get('active_processes') != 0:raise RuntimeError('Unresolved owned job')
                    self.active_job = None
                    if self.child:self.child.wait(timeout=1);self.child.close();self.child = None
                    row['terminal'] = True
                except BaseException:
                    row['quiescence_unknown'] = True
                    raise

    def close(self):
        if self.active_job is not None:
            result = self.retire_job(self.active_job)
            if result.get('active_processes') != 0:raise RuntimeError('Owned job still active')
            self.active_job = None
        if self.child:self.child.wait(timeout=1);self.child.close();self.child = None
