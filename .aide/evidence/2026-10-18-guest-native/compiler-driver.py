"""Guest-only native compiler/SDK/launch probe inside the proven bounded worker."""
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parent


def load(name, path):
    definition = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(definition)
    definition.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if os.name != 'nt' or ROOT != Path('C:/ProgramData/DiskEd/qualification') or not __debug__:
        raise RuntimeError('Verified guest qualification root and active assertions required')
    q = load('q', ROOT / 'tools/qualify-storage.py')
    expected = q.small_json(ROOT / 'expected.json')
    state = q.small_json(ROOT / 'scratch/state.json')
    control = Path(os.environ['DISKED_WORK_ROOT'])
    result = {'schema': 'org.disked.guest-compiler-qualification/1', 'status': 'running',
              'native_product_tests_run': False, 'native_compiler_tests_run': True,
              'source_cpp_sha256': sha(ROOT / 'compiler.cpp'), 'architectures': {},
              'capacity': q.capped_volume(Path(state['drive']), 512 * 1024 * 1024)}
    work_root = Path(state['work'])
    outside = control / 'compiler-outside'
    outside.mkdir()
    (outside / 'sentinel').write_bytes(b'unchanged')
    try:
        for index, (architecture, bits) in enumerate(expected['architectures'].items()):
            work = work_root / architecture
            work.mkdir()
            (work / 'owner.json').write_text(json.dumps({'root': str(ROOT)}))
            worker = job = child = None
            observations = result['architectures'][architecture] = {'status': 'running', 'commands': []}
            try:
                worker = q.W.Worker(work, control=control, private_station=True,
                                    profile_name=state['profile_names'][index])
                if worker.restricting_sid != state['profile_sids'][index]:
                    raise RuntimeError('Compiler worker identity differs from its device admission')
                job = q.S.WindowsJob()
                (work / 'compiler.cpp').write_bytes((ROOT / 'compiler.cpp').read_bytes())
                vc = Path('C:/BuildTools/VC/Tools/MSVC') / expected['toolset']
                sdk = Path('C:/Program Files (x86)/Windows Kits/10')
                binary = vc / 'bin/Hostx64' / architecture
                env = dict(os.environ, DISKED_WORK_ROOT=str(work), TMP=str(work), TEMP=str(work), TMPDIR=str(work),
                           PATH=str(binary) + os.pathsep + os.environ['PATH'],
                           INCLUDE=os.pathsep.join(str(p) for p in [vc / 'include', *[sdk / 'Include' / expected['sdk'] / d for d in ('ucrt', 'shared', 'um')]]),
                           LIB=os.pathsep.join(str(p) for p in [vc / 'lib' / architecture, *[sdk / 'Lib' / expected['sdk'] / d / architecture for d in ('ucrt', 'um')]]))

                def run(label, command):
                    nonlocal child
                    start = time.monotonic()
                    child = worker.launch(list(map(str, command)), env, job)
                    pid = child.pid
                    try:
                        deadline = start + 120
                        while child.poll() is None:
                            q.S.check(ROOT)
                            if time.monotonic() >= deadline:
                                raise TimeoutError('Finite compiler probe deadline reached')
                            time.sleep(.05)
                        code = child.wait()
                    finally:
                        if child.poll() is None:
                            job.close()
                            child.wait()
                        child.close()
                        child = None
                    log = work / 'worker.log'
                    if log.stat().st_size > 65536:
                        raise RuntimeError('Compiler probe output exceeds its bound')
                    output = log.read_bytes().decode(errors='replace')
                    log.rename(work / (label + '.log'))
                    observations['commands'].append({'label': label, 'arguments': list(map(str, command)),
                                                     'pid': pid, 'exit_code': code, 'seconds': time.monotonic() - start,
                                                     'output': output})
                    if code:
                        raise RuntimeError(label + ' failed with ' + hex(code) + ': ' + output)
                    return output

                executable = work / ('compiler-' + architecture + '.exe')
                # Observe the native API path rather than assuming Python's
                # tempfile choice is also the Win32/compiler choice.
                environment_probe = r'''
import ctypes,json,os,pathlib,tempfile
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.GetTempPathW.argtypes=[ctypes.c_ulong,ctypes.c_wchar_p]
buffer=ctypes.create_unicode_buffer(32768)
length=k.GetTempPathW(len(buffer),buffer)
if not 0<length<len(buffer): raise ctypes.WinError(ctypes.get_last_error())
path=pathlib.Path(buffer.value)
result=dict(native_temp=str(path),python_temp=tempfile.gettempdir(),exists=path.is_dir(),environment={key:os.environ.get(key) for key in ('TMP','TEMP','LOCALAPPDATA','USERPROFILE')})
print(json.dumps(result),flush=True)
'''
                environment_output = run('environment', [sys.executable, '-B', '-c', environment_probe])
                observations['temporary_paths'] = json.loads(environment_output.splitlines()[-1])
                temporary = observations['temporary_paths']
                if not temporary['exists'] or not Path(temporary['native_temp']).resolve().is_relative_to(work):
                    raise RuntimeError('Native compiler temporary path is missing or outside its capped workspace')
                compile_command = [binary / 'cl.exe', '/Bv', '/nologo', '/std:c++14', '/W4', '/WX', '/MT', '/O2',
                                   '/EHsc', '/GS', '/sdl', '/guard:cf', '/permissive-', '/utf-8',
                                   '/D_WIN32_WINNT=0x0A00', '/Fo' + str(work / 'compiler.obj'),
                                   '/Fe' + str(executable), work / 'compiler.cpp', 'advapi32.lib',
                                   '/link', '/DYNAMICBASE', '/NXCOMPAT', '/guard:cf']
                compiler_output = run('compile', compile_command)
                if '19.44.35228' not in compiler_output:
                    raise RuntimeError('Compiler launch did not report its pinned version')
                observations['compiler_sha256'] = sha(binary / 'cl.exe')
                observations['artifact_sha256'] = sha(executable)
                data = executable.read_bytes()
                pe = struct.unpack_from('<I', data, 0x3c)[0]
                machine = struct.unpack_from('<H', data, pe + 4)[0]
                if data[pe:pe+4] != b'PE\0\0' or machine != {'x64': 0x8664, 'x86': 0x14c}[architecture]:
                    raise RuntimeError('Produced executable has the wrong PE machine identity')
                observations['pe_machine'] = hex(machine)
                output = run('launch', [executable, outside / architecture])
                launch = json.loads(output)
                if launch['pointer_bits'] != bits or launch['msc_full_ver'] != expected['msc_full_ver']:
                    raise RuntimeError('Native compiler/architecture identity mismatch')
                if launch['appcontainer'] != 1 or launch['elevated'] != 0 or launch['outside_error'] != 5:
                    raise RuntimeError('Native executable lacks required confinement')
                if launch['volume_bytes'] > 512 * 1024 * 1024:
                    raise RuntimeError('Native executable did not run on the capped volume')
                if sha(executable) != observations['artifact_sha256']:
                    raise RuntimeError('Executable bytes changed during launch')
                imports = run('imports', [binary / 'dumpbin.exe', '/nologo', '/dependents', executable])
                if any(name in imports.lower() for name in ('vcruntime140.dll', 'msvcp140.dll', 'ucrtbase.dll')):
                    raise RuntimeError('Static-runtime probe imported a dynamic CRT')
                observations.update(status='pass', launch=launch, output_files=len(list(work.rglob('*'))))
            finally:
                if job:
                    job.close()
                if child:
                    child.wait()
                    child.close()
                if worker:
                    worker.close()
        if sorted(p.name for p in outside.iterdir()) != ['sentinel'] or (outside / 'sentinel').read_bytes() != b'unchanged':
            raise RuntimeError('Compiler campaign changed its outside directory')
        result['outside_unchanged'] = True
        result['profiles_retired'] = q.W.profiles(control) == {}
        if not result['profiles_retired']:
            raise RuntimeError('Compiler profile mappings remain')
        result['status'] = 'pass'
    except BaseException as error:
        result.update(status='fail', error=str(error), traceback=traceback.format_exc())
        for observation in result['architectures'].values():
            if observation['status'] == 'running':
                observation['status'] = 'fail'
    finally:
        # This controller-owned tiny result is the only output retained outside
        # the capped worker. Build objects/executables die with the image.
        data = (json.dumps(result, indent=2)+'\n').encode()
        if len(data) > 262144:
            raise RuntimeError('Compiler receipt exceeds retention bound')
        (ROOT / 'proof-result.json').write_bytes(data)
    return 0 if result['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
