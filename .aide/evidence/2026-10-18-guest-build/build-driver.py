"""Same-source guest CMake/Win32 qualification under the capped native worker."""
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


class Observations:
    def __init__(self, path):
        self.path, self.entries = path, {}
        self.stream = lzma.LZMAFile(path, 'xb', preset=9 | lzma.PRESET_EXTREME)
        self.tar = tarfile.open(fileobj=self.stream, mode='w|')

    def writestr(self, name, data):
        info = tarfile.TarInfo(name)
        info.size = len(data)
        self.tar.addfile(info, io.BytesIO(data))
        self.entries[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

    def write(self, path, name):
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
        with tarfile.open(self.path, 'r|xz') as archive:
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
                   MSBUILDDISABLENODEREUSE='1', CMAKE_BUILD_PARALLEL_LEVEL='1')
        cmake = 'C:/Program Files/CMake/bin/cmake.exe'
        ctest = 'C:/Program Files/CMake/bin/ctest.exe'
        python = sys.executable

        def budget():
            s.check(SOURCE)
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
                    budget()
                    if (work / 'worker.log').stat().st_size > 524288:
                        raise s.StorageLimit('Native command log exceeds bounded retention')
                    if time.monotonic() > deadline:
                        raise TimeoutError('Native phase deadline reached: ' + label)
                    time.sleep(.1)
                code = child.wait()
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
                    log.unlink()

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
            # SetFileSecurity deliberately updates this directory only. The
            # generic Set-Acl path can walk existing children on a volume root.
            # These temporary non-inheriting rules must never do that.
            api = "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;public static class DiskEdDirectoryAcl{[DllImport(\"advapi32.dll\",CharSet=CharSet.Unicode,SetLastError=true)]public static extern bool SetFileSecurity(string path,uint info,byte[] descriptor);}';"
            literal_paths = ','.join("'"+p.replace("'", "''")+"'" for p in paths)
            script = "$ErrorActionPreference='Stop';"+api+"$sid=[Security.Principal.SecurityIdentifier]::new('"+sid+"');$rule=[Security.AccessControl.FileSystemAccessRule]::new($sid,[Security.AccessControl.FileSystemRights]::ReadAndExecute,[Security.AccessControl.InheritanceFlags]::None,[Security.AccessControl.PropagationFlags]::None,[Security.AccessControl.AccessControlType]::Allow);foreach($path in @("+literal_paths+")){$path=[IO.Path]::GetFullPath($path);$acl=Get-Acl -LiteralPath $path;"
            script += ('$acl.AddAccessRule($rule);' if add else 'if(-not @($acl.Access|Where-Object{$_.IdentityReference.Value-eq$sid.Value}).Count){continue};$acl.RemoveAccessRuleSpecific($rule);')
            script += 'if(-not[DiskEdDirectoryAcl]::SetFileSecurity($path,4,$acl.GetSecurityDescriptorBinaryForm())){throw [ComponentModel.Win32Exception]::new([Runtime.InteropServices.Marshal]::GetLastWin32Error())}}'
            import subprocess
            # Partial admission must also be retired by finally/recovery.
            if add:
                common_data_grant = True
            changed = subprocess.run([str(Path(os.environ['WINDIR']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'),
                                      '-NoProfile', '-Command', script], capture_output=True, timeout=30)
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
        binary_root = Path('C:/BuildTools/VC/Tools/MSVC/14.44.35207/bin/Hostx64/x86')
        for name in fixture['executable_targets']:
            path = work / 'win32-build/Release' / (name + '.exe')
            data = path.read_bytes(); offset = struct.unpack_from('<I', data, 0x3c)[0]
            if data[offset:offset+4] != b'PE\0\0' or struct.unpack_from('<H', data, offset+4)[0] != 0x14c:
                raise RuntimeError('Wrong executable machine: ' + name)
            result['executables'][name] = {'sha256': sha(path), 'bytes': path.stat().st_size, 'pe_machine': '0x14c'}
            run('imports-' + name, [binary_root / 'dumpbin.exe', '/nologo', '/dependents', path], timeout=60)
        for test in fixture['tests']:
            code, _ = run('test-' + test, [ctest, '--test-dir', work / 'win32-build', '-C', 'Release',
                                         '-R', '^'+re.escape(test)+'$', '--output-on-failure', '--output-junit',
                                         work / 'test.xml'], timeout=300, allow_failure=True)
            junit = ET.parse(work / 'test.xml').getroot()
            cases = list(junit.iter('testcase'))
            if len(cases) != 1 or any(list(c) for c in cases if any(x.tag in ('failure', 'error', 'skipped') for x in c)):
                raise RuntimeError('JUnit did not prove exactly one passing selected group: ' + test)
            for path in (work / 'win32-build').glob('ntfs-*-cases.json'):
                archive.write(path, 'cases/' + path.name)
                path.unlink()
                budget()
            result['tests'].append({'name': test, 'exit_code': code, 'passed': code == 0})
            if code:
                raise RuntimeError('Native group failed: ' + test)
        result['status'] = 'pass'
    except BaseException as error:
        result.update(status='fail', error=str(error), traceback=traceback.format_exc())
        if archive:
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
