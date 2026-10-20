"""Bounded disposable workspaces for development commands; standard library only."""
import argparse
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat as filemode
import subprocess
import sys
import tempfile
import time

LOCAL_LIMIT = 32 * 1024 * 1024
WORK_LIMIT = 1024 * 1024 * 1024
WORK_FILES = 20000
MIN_FREE = 20 * 1024 * 1024 * 1024
POLL_SECONDS = 0.25
REPO = Path(__file__).resolve().parents[1]


class StorageLimit(RuntimeError):
    pass


def stored_bytes(path, info):
    if os.name == 'nt' and getattr(info, 'st_file_attributes', 0) & (0x200 | 0x800):
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.GetCompressedFileSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
        api.GetCompressedFileSizeW.restype = wintypes.DWORD
        high = wintypes.DWORD()
        ctypes.set_last_error(0)
        low = api.GetCompressedFileSizeW(str(path), ctypes.byref(high))
        error = ctypes.get_last_error()
        if low == 0xffffffff and error:
            raise ctypes.WinError(error)
        return low | high.value << 32
    if os.name != 'nt' and hasattr(info, 'st_blocks'):
        return info.st_blocks * 512
    return info.st_size


def tree_bytes(root, *, allocated=False, stop_after=None, file_limit=None, allow_links=False):
    """Count conservatively. Refuse links instead of following other projects."""
    root = Path(root)
    total, files, pending = 0, 0, [root]
    while pending:
        path = pending.pop()
        try:
            stat = path.lstat()
        except FileNotFoundError:
            continue
        linked = getattr(stat, 'st_file_attributes', 0) & 0x400 or path.is_symlink()
        if linked:
            if not allow_links:
                raise StorageLimit('Reparse point in development workspace: ' + str(path))
            total += 4096
            files += 1
        elif path.is_dir():
            if path != root:
                files += 1  # Directories consume filesystem metadata too.
            try:
                with os.scandir(path) as entries:
                    for entry in entries:
                        pending.append(Path(entry.path))
                        if file_limit is not None and files + len(pending) > file_limit:
                            raise StorageLimit('Disposable workspace entry-count budget exceeded')
            except FileNotFoundError:
                continue
        else:
            try:
                total += stored_bytes(path, stat) if allocated else stat.st_size
            except FileNotFoundError:
                continue
            files += 1
        if file_limit is not None and files > file_limit:
            raise StorageLimit('Disposable workspace entry-count budget exceeded')
        if stop_after is not None and total > stop_after:
            return total
    return total


def check(root=REPO, planned_bytes=0, *, local_limit=LOCAL_LIMIT, min_free=MIN_FREE):
    root = Path(root).resolve()
    if planned_bytes < 0:
        raise ValueError('planned_bytes must be nonnegative')
    if planned_bytes > local_limit:
        raise StorageLimit('Planned context exceeds the entire .aide-local budget')
    size = tree_bytes(root / '.aide-local', stop_after=local_limit - planned_bytes,
                      file_limit=WORK_FILES)
    if size + planned_bytes > local_limit:
        raise StorageLimit('.aide-local budget exceeded; remove disposable context/cache before continuing')
    for volume in {root, Path(tempfile.gettempdir()).resolve()}:
        if shutil.disk_usage(volume).free < min_free:
            raise StorageLimit('Insufficient free space on ' + str(volume))
    return dict(local_bytes=size, local_limit_bytes=local_limit, planned_bytes=planned_bytes,
                work_limit_bytes=WORK_LIMIT, work_file_limit=WORK_FILES, minimum_free_bytes=min_free)


def workspace_identity(root):
    """Share campaign admission across DiskEd checkouts on this user's temp volume."""
    root = Path(root).resolve()
    namespace = str(root)
    bundle = root / 'spec/bundle.json'
    if bundle.is_file():
        try:
            if json.loads(bundle.read_text(encoding='utf-8')).get('bundle_id') == 'org.disked.spec':
                namespace = 'org.disked.spec'
        except (ValueError, AttributeError) as error:
            raise StorageLimit('Cannot establish the checkout identity for campaign admission') from error
    return hashlib.sha256(namespace.encode('utf-8')).hexdigest()[:16]


@contextmanager
def exclusive_run(path):
    with Path(path).open('a+b') as lock:
        lock.seek(0, 2)
        if not lock.tell():
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise StorageLimit('Another managed development command is already running') from error
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == 'nt':
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)


class WindowsJob:
    """Keep trusted build descendants owned until the workspace is cleaned."""
    def __init__(self, *, memory_bytes=None, process_limit=None):
        if memory_bytes is not None and (type(memory_bytes) is not int or not 1024*1024 <= memory_bytes <= 1024*1024*1024):
            raise ValueError('Explicit job commit limit must be1MiB..1GiB')
        if process_limit is not None and (type(process_limit) is not int or not 1 <= process_limit <= 64):
            raise ValueError('Explicit job process limit must be1..64')
        class Basic(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                        ('flags', wintypes.DWORD), ('minimum', ctypes.c_size_t),
                        ('maximum', ctypes.c_size_t), ('active', wintypes.DWORD),
                        ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
                        ('scheduling', wintypes.DWORD)]

        class Extended(ctypes.Structure):
            _fields_ = [('basic', Basic), ('io', ctypes.c_uint64 * 6),
                        ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                        ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]

        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.api.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = Extended()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if memory_bytes is not None:
            limits.basic.flags |= 0x200  # JOB_OBJECT_LIMIT_JOB_MEMORY
            limits.job_memory = memory_bytes
        if process_limit is not None:
            limits.basic.flags |= 8  # JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            limits.basic.active = process_limit
        self.limit_info_type = Extended
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def assign(self, process):
        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            self.api.TerminateJobObject(self.handle, 1)
            self.api.CloseHandle(self.handle)
            self.handle = None


def remove_owned_work(path, base, prefix):
    path, base = Path(path).absolute(), Path(base).resolve()
    if path.parent != base or not path.name.startswith(prefix) or path.is_symlink():
        raise StorageLimit('Refusing cleanup outside the owned temporary workspace')
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if getattr(info, 'st_file_attributes', 0) & 0x400:
        raise StorageLimit('Refusing cleanup of a workspace root that is a reparse point')
    if (path / 'appcontainer-profiles.json').exists():
        if os.name != 'nt':
            raise StorageLimit('Windows worker profile recovery requires its original host')
        import importlib.util
        definition = importlib.util.spec_from_file_location('disked_windows_worker', REPO / 'tools/windows-worker.py')
        worker = importlib.util.module_from_spec(definition)
        definition.loader.exec_module(worker)
        try:
            worker.recover_profiles(path)
        except (OSError, ValueError) as error:
            raise StorageLimit('Worker profile cleanup requires review: ' + str(error)) from error
    def writable(function, name, error):
        target = Path(name).absolute()
        if target != path and path not in target.parents:
            raise StorageLimit('Cleanup callback escaped its owned workspace')
        if target.is_symlink() or getattr(target.lstat(), 'st_file_attributes', 0) & 0x400:
            raise error
        if not target.is_dir() and target.stat().st_nlink > 1:
            raise StorageLimit('Refusing to change attributes shared by a hard link; review owned workspace: ' + str(path))
        if os.name == 'nt':
            # Python's chmod can itself fail opening an exactly READONLY file
            # under the restricted owner token. Change only that attribute;
            # never replace an owned file's DACL to make cleanup succeed.
            attributes = target.stat().st_file_attributes
            if not attributes & filemode.FILE_ATTRIBUTE_READONLY:
                raise error
            api = ctypes.WinDLL('kernel32', use_last_error=True)
            api.SetFileAttributesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
            api.SetFileAttributesW.restype = wintypes.BOOL
            attributes &= ~filemode.FILE_ATTRIBUTE_READONLY
            if not api.SetFileAttributesW(str(target), attributes or filemode.FILE_ATTRIBUTE_NORMAL):
                raise ctypes.WinError(ctypes.get_last_error())
        else:
            mode = target.stat().st_mode | filemode.S_IWUSR | filemode.S_IRUSR
            if target.is_dir():
                mode |= filemode.S_IXUSR
            target.chmod(mode)
        function(name)
    for attempt in range(20):
        try:
            if sys.version_info >= (3, 12):
                shutil.rmtree(path, onexc=writable)
            else:
                shutil.rmtree(path, onerror=lambda f, n, e: writable(f, n, e[1]))
            return
        except FileNotFoundError:
            return
        except OSError:
            if attempt == 19:
                raise
            time.sleep(0.1)


def run(command, root=REPO, *, work_limit=WORK_LIMIT, local_limit=LOCAL_LIMIT,
        min_free=MIN_FREE, poll=POLL_SECONDS):
    root = Path(root).resolve()
    check(root, local_limit=local_limit, min_free=min_free)
    base = Path(tempfile.gettempdir()).resolve()
    identity = workspace_identity(root)
    prefix = 'disked-work-' + identity + '-'
    result = dict(status='running', peak_work_bytes=0, workspace_removed=False)
    with exclusive_run(base / (prefix + 'lock')):
        # A hard-killed prior runner leaves at most its one bounded workspace.
        for stale in base.glob(prefix + '*'):
            if stale.is_dir():
                marker = stale / 'owner.json'
                if not marker.is_file() or json.loads(marker.read_bytes()).get('root') != str(root):
                    raise StorageLimit('Unidentified stale workspace; refusing to create another')
                remove_owned_work(stale, base, prefix)
        work = Path(tempfile.mkdtemp(prefix=prefix, dir=base))
        (work / 'owner.json').write_text(json.dumps(dict(root=str(root))) + '\n', encoding='utf-8')
        process, job, assigned = None, None, False
        try:
            args = [part.replace('{work}', str(work)) for part in command]
            env = dict(os.environ, DISKED_WORK_ROOT=str(work), TMP=str(work), TEMP=str(work), TMPDIR=str(work),
                       PIP_NO_CACHE_DIR='1', PYTHONDONTWRITEBYTECODE='1', CMAKE_BUILD_PARALLEL_LEVEL='2')
            with (work / 'command.log').open('wb') as log:
                if os.name == 'nt':
                    job = WindowsJob()
                process = subprocess.Popen(args, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT,
                    start_new_session=os.name != 'nt',
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0)
                if job:
                    job.assign(process)
                    assigned = True
                while True:
                    check(root, local_limit=local_limit, min_free=min_free)
                    size = tree_bytes(work, allocated=True, stop_after=work_limit,
                                      file_limit=WORK_FILES, allow_links=True)
                    result['peak_work_bytes'] = max(result['peak_work_bytes'], size)
                    if size > work_limit:
                        raise StorageLimit('Disposable build/test workspace budget exceeded')
                    code = process.poll()
                    if code is not None:
                        result.update(status='pass' if code == 0 else 'fail', exit_code=code)
                        break
                    time.sleep(poll)
        except (StorageLimit, KeyboardInterrupt) as error:
            result.update(status='blocked', exit_code=78, reason=str(error) or 'Interrupted')
        finally:
            try:
                if job:
                    job.close()
                if process is not None:
                    if os.name == 'nt' and not assigned:
                        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    elif os.name != 'nt':
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=10)
            finally:
                remove_owned_work(work, base, prefix)
                result['workspace_removed'] = not work.exists()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    checker = commands.add_parser('check')
    checker.add_argument('--planned-bytes', type=int, default=0)
    runner = commands.add_parser('run')
    runner.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.action == 'check':
            result = dict(status='pass', **check(planned_bytes=args.planned_bytes))
        else:
            command = args.command[1:] if args.command[:1] == ['--'] else args.command
            if not command:
                parser.error('run requires a command after --')
            result = run(command)
        print(json.dumps(result))
        return result.get('exit_code', 0)
    except (StorageLimit, OSError) as error:
        print(json.dumps(dict(status='blocked', reason=str(error))), file=sys.stderr)
        return 78


if __name__ == '__main__':
    raise SystemExit(main())
