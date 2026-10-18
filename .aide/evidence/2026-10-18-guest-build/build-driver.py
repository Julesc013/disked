"""Same-source guest CMake/Win32 qualification under the capped native worker."""
import base64
import ctypes
from ctypes import wintypes as T
import hashlib
import importlib.util
import io
import json
import lzma
import os
from pathlib import Path
import re
import shutil
import struct
import stat
import sys
import tarfile
import time
import traceback
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'source'


def load(name, path):
    definition = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(definition)
    definition.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def retire_file(path):
    """Allow bounded delayed release after the owned job is already quiescent."""
    until, retries = time.monotonic() + 5, 0
    while True:
        try:
            path.unlink()
            return retries
        except OSError as error:
            if getattr(error, 'winerror', None) not in (32, 33) or time.monotonic() >= until:
                raise
            retries += 1
            time.sleep(.05)


def retain_test_outputs(archive, directory, stem):
    """Preserve exact per-call inputs/replies/stderr before releasing their space."""
    rows = []
    for path in sorted(directory.glob(stem + '*')):
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400 or info.st_nlink != 1:
            raise RuntimeError('Unexpected linked/non-file test output: ' + path.name)
        member = 'cases/' + path.name
        if member in archive.entries:
            if archive.entries[member] != {'bytes': info.st_size, 'sha256': sha(path)}:
                raise RuntimeError('Previously retained output changed: ' + path.name)
        else:
            archive.write(path, member)
        retries = retire_file(path)
        rows.append({'name': path.name, 'bytes': info.st_size, 'retirement_retries': retries})
    return rows


def drain_completed_outputs(archive, directory, stem, *, final=False):
    """Archive closed per-call files named by the harness's published receipts."""
    receipt_path = directory / (stem+'-raw-receipts.json')
    if not receipt_path.exists():
        return []
    publication = receipt_path.lstat()
    if not stat.S_ISREG(publication.st_mode) or getattr(publication,'st_file_attributes',0) & 0x400 or publication.st_nlink != 1:
        raise RuntimeError('Raw receipt publication is not a plain owned file')
    if publication.st_size > 1048576:
        raise RuntimeError('Raw receipt list exceeds its declared bound')
    try:
        receipts = json.loads(receipt_path.read_bytes())
    except json.JSONDecodeError:
        if final:
            raise
        return []  # A live writer has not published its complete JSON yet.
    rows = []
    for receipt in receipts:
        for path_key,hash_key in (('raw_input','input_sha256'),('raw_output','output_sha256'),('raw_stderr','stderr_sha256')):
            path = Path(receipt[path_key])
            if path.parent != directory or not path.name.startswith(stem+'-'):
                raise RuntimeError('Raw receipt names an output outside its selected group')
            member = 'cases/'+path.name
            expected = receipt[hash_key].removeprefix('sha256:')
            if member in archive.entries:
                if archive.entries[member]['sha256'] != expected:
                    raise RuntimeError('Published raw receipt changed after archival')
                continue
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or getattr(info,'st_file_attributes',0) & 0x400 or info.st_nlink != 1:
                raise RuntimeError('Raw receipt does not name a plain owned output')
            with path.open('rb') as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest() != expected:
                    raise RuntimeError('Published raw output differs from its receipt')
            archive.write(path,member)
            # Receipt publication follows write_bytes/close and communicate.
            # Do not apply the job-retirement retry policy to a live group.
            path.unlink()
            rows.append(dict(name=path.name,bytes=info.st_size))
    return rows


class Observations:
    def __init__(self, path):
        self.path, self.entries = path, {}
        self.stream = lzma.LZMAFile(path, 'xb', preset=9 | lzma.PRESET_EXTREME)
        self.tar = tarfile.open(fileobj=self.stream, mode='w|')

    def writestr(self, name, data):
        if name in self.entries:
            raise RuntimeError('Duplicate retained observation: ' + name)
        info = tarfile.TarInfo(name)
        info.size = len(data)
        self.tar.addfile(info, io.BytesIO(data))
        self.entries[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

    def write(self, path, name):
        if name in self.entries:
            raise RuntimeError('Duplicate retained observation: ' + name)
        info = tarfile.TarInfo(name)
        info.size = path.stat().st_size
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            stream.seek(0)
            self.tar.addfile(info, stream)
        self.entries[name] = {'bytes': info.size, 'sha256': digest}

    def close_verify(self):
        self.tar.close()
        self.stream.close()
        seen = set()
        # LZMAFile bounds decompressed reads. tarfile's combined r|xz stream can
        # repeatedly copy a very large expansion buffer for compressed JSON.
        with lzma.open(self.path, 'rb') as decoded:
            with tarfile.open(fileobj=decoded, mode='r|') as archive:
                for entry in archive:
                    expected = self.entries[entry.name]
                    with archive.extractfile(entry) as stream:
                        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                    if digest != expected['sha256'] or entry.size != expected['bytes']:
                        raise RuntimeError('Retained observation archive does not reproduce its input')
                    seen.add(entry.name)
        if seen != set(self.entries):
            raise RuntimeError('Retained archive omitted observations')


def main():
    if os.name != 'nt' or ROOT != Path('C:/ProgramData/DiskEd/qualification') or not __debug__:
        raise RuntimeError('Verified guest source and active assertions required')
    w = load('worker', SOURCE / 'tools/windows-worker.py')
    s = load('workspace', SOURCE / 'tools/workspace.py')
    state = json.loads((ROOT / 'scratch/state.json').read_bytes())
    manifest = json.loads((ROOT / 'source.json').read_bytes())
    control = Path(os.environ['DISKED_WORK_ROOT'])
    if json.loads((control / 'owner.json').read_bytes())['root'] != str(SOURCE):
        raise RuntimeError('Runner/source ownership differs')
    work = Path(state['work']) / 'build'
    work.mkdir()
    (work / 'owner.json').write_text(json.dumps({'root': str(SOURCE)}))
    result = {'schema': 'org.disked.guest-win32-qualification/1', 'status': 'running',
              'source_revision': manifest['revision'], 'commands': [], 'tests': [], 'executables': {},
              'full_x64_product_suite_run': False, 'owner_accepted': False}
    worker = None
    archive = None
    common_data_grant = False
    retained = work / 'retained'
    retained.mkdir()
    archive_path = retained / 'observations.tar.xz'
    try:
        # Worker requires a fresh directory, so move the empty retained holder
        # outside its root until after construction.
        retained.rmdir()
        worker = w.Worker(work, control=control, private_station=True, profile_name=state['profile_names'][0])
        if worker.restricting_sid != state['profile_sids'][0]:
            raise RuntimeError('Worker/device package identity differs')
        retained.mkdir()
        archive = Observations(archive_path)
        descriptor = ctypes.c_void_p()
        w.require(worker.a.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            'D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;' + worker.user_sid +
            ')(A;OICI;0x1200a9;;;' + worker.restricting_sid + ')', 1, ctypes.byref(descriptor), None))
        try:
            present, defaulted, acl = T.BOOL(), T.BOOL(), ctypes.c_void_p()
            w.require(worker.a.GetSecurityDescriptorDacl(descriptor, ctypes.byref(present), ctypes.byref(acl), ctypes.byref(defaulted)))
            code = worker.a.SetNamedSecurityInfoW(str(SOURCE), 1, 0x80000004, None, None, acl, None)
            if code:
                raise ctypes.WinError(code)
        finally:
            worker.k.LocalFree(descriptor)
        env = dict(os.environ, DISKED_WORK_ROOT=str(work), GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0',
                   GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='safe.directory', GIT_CONFIG_VALUE_0=str(SOURCE),
                   MSBUILDDISABLENODEREUSE='1', CMAKE_BUILD_PARALLEL_LEVEL='1',
                   DISKED_TEST_OTHER_VOLUME_ROOT='C:\\')
        cmake = 'C:/Program Files/CMake/bin/cmake.exe'
        ctest = 'C:/Program Files/CMake/bin/ctest.exe'
        python = sys.executable
        active_output_stem = None

        def drain(final=False):
            if active_output_stem not in ('ntfs-name-order-file-cases','ntfs-name-order-worker-cases'):
                return
            rows = drain_completed_outputs(archive,work / 'win32-build',active_output_stem,final=final)
            if rows:
                totals = result.setdefault('streamed_outputs',{}).setdefault(active_output_stem,dict(files=0,uncompressed_bytes=0))
                totals['files'] += len(rows)
                totals['uncompressed_bytes'] += sum(row['bytes'] for row in rows)

        def budget():
            s.check(SOURCE)
            # The fixed image below already charges every backing byte. Inspect
            # its owned work tree separately for allocation/entry observations;
            # count test reparse objects without following their targets.
            allocated = s.tree_bytes(work, allocated=True, file_limit=20000, allow_links=True)
            result['peak_scratch_allocated_bytes'] = max(result.get('peak_scratch_allocated_bytes',0),allocated)
            total = s.tree_bytes(ROOT / 'scratch', allocated=True, file_limit=20000, allow_links=False)
            total += s.tree_bytes(SOURCE, allocated=True, file_limit=20000, allow_links=False)
            total += s.tree_bytes(control, allocated=True, file_limit=20000, allow_links=True)
            if total > s.WORK_LIMIT:
                raise s.StorageLimit('Combined guest campaign storage exceeded')
            if archive_path.exists() and archive_path.stat().st_size > 32 * 1024 * 1024:
                raise s.StorageLimit('Compressed retained evidence exceeds declared bound')

        def run(label, arguments, timeout=300, allow_failure=False):
            job, child = s.WindowsJob(), None
            started = time.monotonic()
            saved = False
            try:
                child = worker.launch(list(map(str, arguments)), env, job)
                pid = child.pid
                deadline = started + timeout
                while child.poll() is None:
                    drain()
                    budget()
                    if (work / 'worker.log').stat().st_size > 524288:
                        raise s.StorageLimit('Native command log exceeds bounded retention')
                    if time.monotonic() > deadline:
                        raise TimeoutError('Native phase deadline reached: ' + label)
                    time.sleep(.1)
                code = child.wait()
                drain(final=True)
                raw = (work / 'worker.log').read_bytes()
                if len(raw) > 524288:
                    raise s.StorageLimit('Native command output exceeds bound')
                archive.writestr(label + '.log', raw)
                saved = True
                result['commands'].append({'label': label, 'arguments': list(map(str, arguments)), 'pid': pid,
                                           'exit_code': code, 'seconds': time.monotonic()-started,
                                           'log_sha256': hashlib.sha256(raw).hexdigest(),
                                           'tail': raw[-8192:].decode(errors='replace')})
                if code and not allow_failure:
                    raise RuntimeError(label + ' failed: ' + raw[-8192:].decode(errors='replace'))
                return code, raw
            finally:
                class Accounting(ctypes.Structure):
                    _fields_ = [('times', ctypes.c_longlong * 4), ('faults', T.DWORD),
                                ('total', T.DWORD), ('active', T.DWORD), ('terminated', T.DWORD)]
                try:
                    w.require(job.api.TerminateJobObject(job.handle, 78))
                    query = w.bind(job.api, 'QueryInformationJobObject', T.BOOL, T.HANDLE,
                                   ctypes.c_int, ctypes.c_void_p, T.DWORD, ctypes.c_void_p)
                    until = time.monotonic() + 10
                    while True:
                        accounting = Accounting()
                        w.require(query(job.handle, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None))
                        if accounting.active == 0:
                            break
                        if time.monotonic() > until:
                            raise RuntimeError('Owned command descendants have not retired')
                        time.sleep(.05)
                finally:
                    job.close()
                if child:
                    child.wait()
                    child.close()
                log = work / 'worker.log'
                if log.exists():
                    if not saved:
                        archive.writestr(label + '-incomplete.log', log.read_bytes()[:524288])
                    retries = retire_file(log)
                    if retries:
                        result.setdefault('retirement_retries', []).append({'command': label, 'retries': retries})

        def common_data_access(add):
            nonlocal common_data_grant
            # Only this fresh package identity, only directory read/execute,
            # never inheritance. Do not restore an old whole DACL over another
            # agent's concurrent changes; remove our exact rule instead.
            sid = worker.restricting_sid
            if not re.fullmatch(r'S-1-15-2-(?:[0-9]+-)*[0-9]+', sid):
                raise RuntimeError('Invalid fresh package identity')
            paths = [str(Path('C:/')), str(Path('C:/ProgramData')), str(Path('C:/ProgramData/DiskEd')), str(ROOT)]
            journal = ROOT / 'scoped-directory-access.json'
            state_record = {'nonce': state['nonce'], 'sid': sid, 'paths': paths, 'phase': 'pending' if add else 'removing'}
            journal.write_text(json.dumps(state_record)+'\n', encoding='utf-8', newline='\n')
            source_setup = load('source_setup', ROOT / 'guest-source.py')
            script = source_setup.directory_script(sid, paths, add)
            import subprocess
            # Partial admission must also be retired by finally/recovery.
            if add:
                common_data_grant = True
            changed = subprocess.run([str(Path(os.environ['WINDIR']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'),
                                      '-NoProfile', '-EncodedCommand', base64.b64encode(script.encode('utf-16-le')).decode('ascii')], capture_output=True, timeout=30)
            observations = changed.stdout.decode(errors='replace')
            result.setdefault('directory_access_observations', []).append({'add': add, 'output': observations[-32768:]})
            if changed.returncode:
                raise RuntimeError('Scoped common-data access update failed: ' + changed.stderr.decode(errors='replace'))
            common_data_grant = add
            state_record['phase'] = 'active' if add else 'retired'
            journal.write_text(json.dumps(state_record)+'\n', encoding='utf-8', newline='\n')
            result.setdefault('common_data_access', []).append({'added': add, 'sid': sid, 'paths': paths,
                                                               'rights': 'ReadAndExecute', 'inheritance': 'None'})

        probe = r'''
import ctypes,json,pathlib,sys
from ctypes import wintypes as T
k=ctypes.WinDLL('kernel32',use_last_error=True);a=ctypes.WinDLL('advapi32',use_last_error=True)
k.GetCurrentProcess.restype=T.HANDLE;a.OpenProcessToken.argtypes=[T.HANDLE,T.DWORD,ctypes.POINTER(T.HANDLE)]
a.GetTokenInformation.argtypes=[T.HANDLE,ctypes.c_int,ctypes.c_void_p,T.DWORD,ctypes.POINTER(T.DWORD)]
k.CloseHandle.argtypes=[T.HANDLE];token=T.HANDLE();n=T.DWORD();e=T.DWORD();c=T.DWORD()
assert a.OpenProcessToken(k.GetCurrentProcess(),8,ctypes.byref(token))
assert a.GetTokenInformation(token,20,ctypes.byref(e),4,ctypes.byref(n));assert a.GetTokenInformation(token,29,ctypes.byref(c),4,ctypes.byref(n));k.CloseHandle(token)
denied=False
try:pathlib.Path(sys.argv[1]).write_bytes(b'unexpected')
except PermissionError:denied=True
print(json.dumps(dict(elevated=e.value,appcontainer=c.value,source_write_denied=denied)))
assert e.value==0 and c.value==1 and denied
'''
        _, raw = run('source-confinement', [python, '-B', '-c', probe, SOURCE / 'forbidden-write'])
        result['source_confinement'] = json.loads(raw.decode().splitlines()[-1])
        run('msbuild-version', ['C:/BuildTools/MSBuild/Current/Bin/amd64/MSBuild.exe', '-nologo', '-version'], timeout=60, allow_failure=True)
        folder_project = work / 'folders.proj'
        folder_project.write_text('''<Project DefaultTargets="Observe"><PropertyGroup><Common>$([System.Environment]::GetFolderPath(SpecialFolder.CommonApplicationData))</Common></PropertyGroup><Target Name="Observe"><Message Importance="high" Text="DISKED_COMMON=[$(Common)]" /></Target></Project>''', encoding='utf-8')
        _, before = run('common-data-before', ['C:/BuildTools/MSBuild/Current/Bin/amd64/MSBuild.exe', '-nologo', folder_project], timeout=60)
        if b'DISKED_COMMON=[]' in before:
            common_data_access(True)
            _, after = run('common-data-after', ['C:/BuildTools/MSBuild/Current/Bin/amd64/MSBuild.exe', '-nologo', folder_project], timeout=60)
            if b'DISKED_COMMON=[]' in after:
                raise RuntimeError('Scoped directory read did not resolve the common-data path')
        fixture_preflight = r'''
import json,pathlib,sys
sys.path.insert(0,sys.argv[1])
from support.tempdir import temporary_directory
directory=temporary_directory(prefix='disked-fixture-preflight-')
path=pathlib.Path(directory.name)
with directory:
    target=path/'generated.img';target.write_bytes(b'owned fixture')
    assert target.read_bytes()==b'owned fixture'
assert not path.exists()
print(json.dumps(dict(status='pass',fixture_created_read_and_removed=True)))
'''
        run('fixture-temporary-preflight', [python, '-B', '-c', fixture_preflight, SOURCE / 'tests'], timeout=30)
        sparse_preflight = r'''
import json,pathlib,sys
sys.path.insert(0,sys.argv[1]);sys.path.insert(0,sys.argv[2])
from support.tempdir import temporary_directory
from test_ntfs_file import size_fixture,record_sparse_fixture,SPARSE_OBSERVATIONS
with temporary_directory(prefix='disked-sparse-preflight-') as directory:
    target=pathlib.Path(directory)/'high-offset.img';offset=(1<<32)+173
    with target.open('xb') as stream:
        size_fixture(stream,offset+4096);stream.seek(offset);stream.write(b'owned high-offset data')
        record_sparse_fixture(stream,offset+4096)
    with target.open('rb') as stream:
        assert stream.read(64)==bytes(64);stream.seek(offset);assert stream.read(22)==b'owned high-offset data'
    assert target.stat().st_size==offset+4096
    small=pathlib.Path(directory)/'small.img'
    with small.open('xb') as stream:
        size_fixture(stream,8*1024*1024);stream.seek(4096);stream.write(b'owned small data')
        record_sparse_fixture(stream,8*1024*1024,all_sizes=True)
    assert small.stat().st_file_attributes & 0x200
    assert SPARSE_OBSERVATIONS[-1]['allocated_bytes']<=65536
    with small.open('rb') as stream:
        assert stream.read(64)==bytes(64);stream.seek(4096);assert stream.read(16)==b'owned small data'
assert not target.exists() and not small.exists()
print(json.dumps(dict(status='pass',fixtures=SPARSE_OBSERVATIONS,removed=True)))
'''
        run('fixture-sparse-preflight', [python, '-B', '-c', sparse_preflight, SOURCE / 'tests', SOURCE / 'tests/images'], timeout=30)
        mode = json.loads((ROOT / 'expected.json').read_bytes()).get('execution_kind', 'win32')
        if mode in ('path-probe','object-probe'):
            name = 'worker-object-probe.py' if mode == 'object-probe' else 'path-api-probe.py'
            result['schema'] = 'org.disked.guest-'+mode+'/1'
            archive.write(ROOT / name, 'recipe/'+name)
            argument = state['profile_sids'][1] if mode == 'object-probe' else SOURCE / 'tests'
            _, raw = run(mode, [python, '-B', '-c', (ROOT / name).read_text(), argument], timeout=30)
            result[mode.replace('-','_')] = json.loads(raw.decode().splitlines()[-1])
        elif mode == 'win32':
            # Creating a symlink needs a guest setup privilege; reading/refusing
            # it remains a test of the actual unprivileged native executable.
            fixture_root = work / 'symlink-fixture'
            fixture_root.mkdir()
            target,link = fixture_root / 'source.img',fixture_root / 'leaf.img'
            target.write_bytes(b'')
            os.symlink(target,link)
            if not link.is_symlink() or link.resolve() != target:
                raise RuntimeError('Prepared symlink did not bind the owned source')
            archive.writestr('prepared-symlink.json',json.dumps(dict(source=str(target),link=str(link),
                source_sha256=sha(target),source_bytes=0,source_population='bounded exact generated source copied by each test',
                created_by='guest Agents coordinator',
                native_consumer='non-elevated AppContainer')).encode())
            env['DISKED_TEST_SYMLINK_ROOT'] = str(fixture_root)
            symlink_preflight = r'''
import json,pathlib,sys
sys.path.insert(0,str(pathlib.Path(sys.argv[1])))
from test_ntfs_file import temporary_directory,size_fixture,prepared_symlink,file_digest,PREPARED_SYMLINK_OBSERVATIONS
with temporary_directory(prefix='symlink-source-preflight-') as directory:
    source=pathlib.Path(directory)/'source.img'
    for iteration in range(2):
        with source.open('wb') as stream:
            size_fixture(stream,40960000)
            stream.seek(4096);stream.write(b'original independent source '+bytes([iteration]))
            if not iteration:
                stream.seek(40959996);stream.write(b'tail')
        before=file_digest(source)
        target,link=prepared_symlink(source)
        assert link.is_symlink() and link.resolve()==target
        assert file_digest(source)==before==file_digest(target)
        assert PREPARED_SYMLINK_OBSERVATIONS[-1]['allocated_bytes']<=16*1024*1024
        assert PREPARED_SYMLINK_OBSERVATIONS[-1]['copied_nonzero_block_bytes']<=131072
assert not source.exists()
assert len(PREPARED_SYMLINK_OBSERVATIONS)==2
print(json.dumps(dict(status='pass',source_removed=True,observations=PREPARED_SYMLINK_OBSERVATIONS)))
'''
            run('fixture-symlink-preflight',[python,'-B','-c',symlink_preflight,SOURCE/'tests/images'],timeout=30)
            run('configure-x64', [cmake, '--preset', 'windows-bootstrap', '-S', SOURCE,
                                 '-DCMAKE_GENERATOR_INSTANCE=C:/BuildTools,version=17.14.37516.0', '-DPython3_EXECUTABLE=' + python,
                                 '-DGIT_EXECUTABLE=C:/Program Files/Git/cmd/git.exe'])
            metadata_bytes = 0
            metadata = sorted((work / 'build/.cmake/api/v1/reply').glob('*.json'))
            if not metadata or len(metadata) > 4096:
                raise RuntimeError('Missing or excessive CMake File API metadata')
            for path in metadata:
                size = path.stat().st_size
                metadata_bytes += size
                if size > 1048576 or metadata_bytes > 8388608:
                    raise RuntimeError('CMake File API retention exceeds declared bound')
                archive.write(path, 'codemodel/' + path.name)
            run('fixture', [python, '-B', SOURCE / 'tools/ntfs-win32-fixture.py', '--root', SOURCE,
                            '--build', work / 'build', '--output', work / 'win32-fixture'])
            fixture = json.loads((work / 'win32-fixture/fixture-inputs.json').read_bytes())
            if len(fixture['tests']) != 18 or len(fixture['standalone_headers']) != 12 or len(fixture['executable_targets']) != 9:
                raise RuntimeError('Fixture dropped required groups/headers/executables')
            archive.writestr('fixture-inputs.json', (work / 'win32-fixture/fixture-inputs.json').read_bytes())
            result['fixture'] = {'tests': fixture['tests'], 'headers': fixture['standalone_headers'],
                                 'executable_targets': fixture['executable_targets']}
            run('configure-win32', [cmake, '-S', work / 'win32-fixture', '-B', work / 'win32-build',
                                   '-G', 'Visual Studio 17 2022', '-A', 'Win32,version=10.0.19041.0',
                                   '-T', 'v143,version=14.44.35207,host=x64', '-DCMAKE_GENERATOR_INSTANCE=C:/BuildTools,version=17.14.37516.0',
                                   '-DCMAKE_SYSTEM_VERSION=10.0.19041.0', '-DPython3_EXECUTABLE=' + python])
            run('build-win32', [cmake, '--build', work / 'win32-build', '--config', 'Release', '--parallel', '1'], timeout=900)
            header_objects = sorted((work / 'win32-build/ntfs_fixture_headers.dir/Release').glob('*.obj'))
            if len(header_objects) != 12:
                raise RuntimeError('Twelve compiled standalone header objects were not observed')
            result['header_artifacts'] = [dict(path=p.relative_to(work).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in header_objects]
            binary_root = Path('C:/BuildTools/VC/Tools/MSVC/14.44.35207/bin/Hostx64/x86')
            for name in fixture['executable_targets']:
                path = work / 'win32-build/Release' / (name + '.exe')
                data = path.read_bytes(); offset = struct.unpack_from('<I', data, 0x3c)[0]
                if data[offset:offset+4] != b'PE\0\0' or struct.unpack_from('<H', data, offset+4)[0] != 0x14c:
                    raise RuntimeError('Wrong executable machine: ' + name)
                result['executables'][name] = {'sha256': sha(path), 'bytes': path.stat().st_size, 'pe_machine': '0x14c'}
            for name in fixture['executable_targets']:
                path = work / 'win32-build/Release' / (name + '.exe')
                _, headers = run('headers-' + name, [binary_root / 'dumpbin.exe', '/nologo', '/headers', path], timeout=60)
                if any(text not in headers for text in (b'Dynamic base',b'NX compatible',b'Control Flow Guard')):
                    raise RuntimeError('Missing required PE security flags: ' + name)
                run('imports-' + name, [binary_root / 'dumpbin.exe', '/nologo', '/imports', path], timeout=60)
                _, dependencies = run('dependencies-' + name, [binary_root / 'dumpbin.exe', '/nologo', '/dependents', path], timeout=60)
                if re.search(rb'(?:MSVCP|VCRUNTIME|UCRTBASE|API-MS-WIN-CRT)[^\s]*\.DLL', dependencies.upper()):
                    raise RuntimeError('Unexpected dynamic CRT dependency: ' + name)
            ordered_tests = ['image.ntfs_file'] + [name for name in fixture['tests'] if name != 'image.ntfs_file']
            if len(ordered_tests) != 18 or set(ordered_tests) != set(fixture['tests']):
                raise RuntimeError('Native group ordering changed the required set')
            for test in ordered_tests:
                stem = 'ntfs-' + test.removeprefix('image.ntfs_').replace('_', '-') + '-cases'
                active_output_stem = stem
                code, _ = run('test-' + test, [ctest, '--test-dir', work / 'win32-build', '-C', 'Release',
                                             '-R', '^'+re.escape(test)+'$', '--output-on-failure', '--output-junit',
                                             work / 'test.xml'], timeout=300, allow_failure=True)
                summary_path = work / 'win32-build' / (stem + '.json')
                summary = json.loads(summary_path.read_bytes()) if summary_path.is_file() else None
                retained_outputs = retain_test_outputs(archive, work / 'win32-build', stem)
                archive.write(work / 'test.xml', 'junit/' + test + '.xml')
                result['tests'].append({'name': test, 'exit_code': code, 'passed': code == 0,
                                        'retained_files': len(retained_outputs),
                                        'retained_bytes': sum(x['bytes'] for x in retained_outputs),
                                        'summary': {key:(len(summary[key]) if isinstance(summary[key],list) else summary[key])
                                                    for key in ('cases','count','methods','calls','failures','errors','unverified')
                                                    if key in summary} if summary else None})
                budget()
                junit = ET.parse(work / 'test.xml').getroot()
                cases = list(junit.iter('testcase'))
                if len(cases) != 1 or any(list(c) for c in cases if any(x.tag in ('failure', 'error', 'skipped') for x in c)):
                    raise RuntimeError('JUnit did not prove exactly one passing selected group: ' + test)
                if code:
                    raise RuntimeError('Native group failed: ' + test)
                if summary and (summary.get('unverified') or summary.get('skipped')):
                    raise RuntimeError('Native group has unverified/skipped checks: ' + test)
                if test in ('image.ntfs_file','image.ntfs_directory_file'):
                    prepared = summary.get('prepared_symlinks',[])
                    if len(prepared)!=1 or any(row['source_sha256']!=row['target_sha256'] or
                        not 0<=row['allocated_bytes']<=16*1024*1024 or
                        not 0<row['copied_nonzero_block_bytes']<=16*1024*1024 for row in prepared):
                        raise RuntimeError('Byte-exact allocated-bounded symlink fixture was not established')
                if test == 'image.ntfs_file':
                    expected_counts = json.loads((ROOT / 'expected.json').read_bytes())['file_method_cases']
                    if not summary or summary['cases'] != sum(expected_counts.values()) or summary.get('case_counts') != expected_counts:
                        raise RuntimeError('Complete original and added file cases did not match their independent method matrix')
                    if len(summary.get('path_binding',[])) != 1:
                        raise RuntimeError('Six binding rows were not evaluated')
                    if len(summary.get('sparse_fixtures',[])) != 2:
                        raise RuntimeError('Both original high-offset sparse fixtures must be observed')
                    raw_calls = summary.get('raw_observations',[])
                    if not raw_calls:
                        raise RuntimeError('Raw file-probe observations were not retained')
                    for call in raw_calls:
                        if call['exit_code'] != 0 or call['timed_out'] or not call['created'] or int(call['created']) <= 0:
                            raise RuntimeError('File-probe process identity/outcome was not established')
                        for item in call['files'].values():
                            if archive.entries.get('cases/'+item['path']) != {'bytes':item['bytes'],'sha256':item['sha256'].removeprefix('sha256:')}:
                                raise RuntimeError('Raw file-probe bytes do not match their observation receipt')
                expected_count = json.loads((ROOT / 'expected.json').read_bytes())['fixed_group_cases'].get(test)
                if expected_count is not None:
                    count = summary.get('count',summary.get('cases')) if summary else None
                    if (len(count) if isinstance(count,list) else count) != expected_count:
                        raise RuntimeError('Original required case inventory changed: ' + test)
                if test in ('image.ntfs_upcase_capture','image.ntfs_name_order'):
                    suffix = 'ntfs-upcase-capture/expected-after-binding-review.json' if test.endswith('upcase_capture') else 'ntfs-name-order/expected-after-fixture-review.json'
                    expected = json.loads((SOURCE / ('.aide/evidence/2026-10-17-'+suffix)).read_bytes())
                    if summary.get('status') != 'pass' or any(summary.get(key) != expected[key] for key in ('recipe_sha256','expected_cases_sha256')):
                        raise RuntimeError('Predeclared pure case identities changed: ' + test)
                for family,methods in (('upcase',{'file':8,'worker':10}),('name_order',{'file':9,'worker':10})):
                    mode = test.removeprefix('image.ntfs_'+family+'_')
                    if mode not in methods or test != 'image.ntfs_'+family+'_'+mode:
                        continue
                    folder = 'ntfs-upcase-command/expected-after-startup-review.json' if family == 'upcase' else 'ntfs-name-order-command/expected-after-binding-review.json'
                    expected = json.loads((SOURCE / ('.aide/evidence/2026-10-17-'+folder)).read_bytes())
                    recipe = 'tests/images/test_ntfs_'+family+'_'+mode+'.py'
                    if summary.get('status') != 'pass' or summary.get('methods') != methods[mode] or summary.get('recipe_sha256') != expected['recipes'][recipe]:
                        raise RuntimeError('Original native method/recipe identity changed: ' + test)
                    for receipt in summary['source_receipts']:
                        if receipt['before_sha256'] != receipt['after_sha256'] or (family == 'name_order' and receipt['before_bytes'] != receipt['after_bytes']):
                            raise RuntimeError('Generated source changed: ' + test)
                    if family == 'name_order' and summary['helper_sha256'] != expected['recipes']['tests/images/ntfs_name_order_native_expectations.py']:
                        raise RuntimeError('Original native expectation helper changed: ' + test)
        else:
            raise RuntimeError('Unknown guest campaign execution kind')
        result['status'] = 'pass'
    except BaseException as error:
        result.update(status='fail', error=str(error), traceback=traceback.format_exc())
        if archive:
            if 'test' in locals() and 'stem' in locals():
                try:
                    retain_test_outputs(archive, work / 'win32-build', stem)
                except BaseException as retention_error:
                    result['failed_test_retention_error'] = str(retention_error)
            for directory in (work / 'build', work / 'win32-build'):
                for name in ('CMakeConfigureLog.yaml', 'CMakeError.log', 'CMakeOutput.log'):
                    path = directory / 'CMakeFiles' / name
                    if path.is_file() and path.stat().st_size <= 1048576:
                        archive.write(path, 'diagnostics/' + directory.name + '-' + name)
    finally:
        try:
            if common_data_grant:
                common_data_access(False)
        except BaseException as error:
            result.update(status='fail', directory_access_retirement_error=str(error))
        try:
            if worker:
                worker.close()
        except BaseException as error:
            result.update(status='fail', worker_retirement_error=str(error))
        try:
            if archive:
                archive.close_verify()
                if archive_path.stat().st_size > 32 * 1024 * 1024:
                    raise RuntimeError('Retained observation budget exceeded; bulk archive discarded')
                shutil.copyfile(archive_path, ROOT / 'retained.tar.xz')
                result['archive_sha256'] = sha(ROOT / 'retained.tar.xz')
                result['archive_bytes'] = (ROOT / 'retained.tar.xz').stat().st_size
                result['archive_entries'] = archive.entries
        except BaseException as error:
            result.update(status='fail', retirement_or_retention_error=str(error))
        data = (json.dumps(result, indent=2)+'\n').encode()
        if len(data) > 1048576:
            raise RuntimeError('Build receipt exceeds declared bound')
        (ROOT / 'proof-result.json').write_bytes(data)
    return 0 if result['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
