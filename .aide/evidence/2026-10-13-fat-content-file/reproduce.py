"""Reproduce exact held-file FAT content windows and all prior regressions at a clean source."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


def sha(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--existing-clone', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--gcc-executable', type=Path, required=True)
    args = parser.parse_args()
    root = Path.cwd().resolve()
    checkout, output = args.existing_clone.resolve(), args.output.resolve()
    assert re.fullmatch('[0-9a-f]{40}', args.source_revision)
    assert checkout.is_relative_to(root/'.aide-local') and output.is_relative_to(root/'.aide-local')
    assert args.gcc_executable.is_file()
    output.mkdir(); (output/'logs').mkdir()
    commands = []

    def run(name, command, timeout=300):
        command = list(map(str, command)); start = time.monotonic()
        result = subprocess.run(command, cwd=checkout, capture_output=True, timeout=timeout)
        log = output/'logs'/(name+'.log'); log.write_bytes(result.stdout+result.stderr)
        commands.append(dict(name=name, command=command, cwd=str(checkout), exit_code=result.returncode,
                             elapsed_seconds=round(time.monotonic()-start, 3), log='logs/'+log.name))
        save(output/'commands.json', commands)
        print(name+': exit '+str(result.returncode), flush=True)
        assert result.returncode == 0, name
        return result.stdout

    assert Path(run('origin', ['git','remote','get-url','origin']).decode().strip()).resolve() == root
    assert not run('existing-status', ['git','status','--porcelain']).strip()
    run('fetch', ['git','fetch','--no-tags','origin',args.source_revision])
    run('checkout', ['git','checkout','--detach',args.source_revision])
    assert not run('source-status', ['git','status','--porcelain']).strip()
    host = json.loads(run('host', ['powershell','-NoProfile','-Command',
        '$fatIdentity=[System.Security.Principal.WindowsIdentity]::GetCurrent();'
        '$fatPrincipal=[System.Security.Principal.WindowsPrincipal]::new($fatIdentity);'
        '$fatOS=Get-CimInstance Win32_OperatingSystem;'
        '[ordered]@{identity=$fatIdentity.Name;elevated=$fatPrincipal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);'
        'os=$fatOS.Caption;version=$fatOS.Version;architecture=$fatOS.OSArchitecture}|ConvertTo-Json -Compress']))
    assert host['identity']=='BLACKGLASS-WIN1\\Jules' and not host['elevated']
    run('source-map', [sys.executable,'-X','utf8','tools/check-source-map.py'])
    catalog = json.loads((checkout/'tools/build-inputs.json').read_bytes())
    names = set(catalog['files']) | {p.relative_to(checkout).as_posix() for p in (checkout/'source').rglob('*') if p.is_file()} | {
        'AGENTS.md','.clang-format','.editorconfig','docs/source-map.md','docs/code-structure.md',
        'spec/work/units.json','spec/catalog/input-dependencies.json','spec/storage/filesystem-capabilities.md',
        'spec/tools/specctl.py','tools/check-source-map.py','tools/check-build-boundaries.py',
        '.aide/evidence/2026-10-13-fat-content-file/reproduce.py',
        '.aide/evidence/2026-10-13-fat-content-file/audit_retention.py',
        'spec/catalog/fat-content-file-prototype.json','spec/catalog/fat-content-prototype.json','spec/catalog/fat-allocation-window-prototype.json','spec/catalog/fat-command-prototype.json','spec/catalog/fat-worker-prototype.json',
    }
    inputs = {name:sha(checkout/name) for name in sorted(names)}
    save(output/'source-inputs.json', inputs)
    tree = run('source-tree', ['git','ls-tree','-r','-z',args.source_revision]); blobs={}
    for row in tree.split(b'\0'):
        if row:
            header, path = row.split(b'\t',1); name = path.decode()
            if name in inputs: blobs[name] = header.split()[2].decode()
    assert set(blobs)==set(inputs)
    for name, blob in blobs.items():
        data = (checkout/name).read_bytes()
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blob
    save(output/'source-blob-bindings.json', blobs)
    run('cmake-version', ['cmake','--version'])
    run('python-environment', [sys.executable,'-c',
        "import sys,importlib.metadata as m;print(sys.version);print('PyYAML='+m.version('PyYAML'));print('jsonschema='+m.version('jsonschema'))"])
    gcc = args.gcc_executable.resolve()
    assert run('gcc-version', [gcc,'-dumpfullversion']).decode().strip()=='15.2.0'
    run('gcc-description', [gcc,'--version'])
    run('gcc-c90', [gcc,'-std=c90','-pedantic-errors','-Wall','-Wextra','-Werror','-I','source','-fsyntax-only',
                    'source/portable/fat/volume.c','source/portable/fat/allocation.c','source/portable/fat/directory.c','source/portable/fat/auxiliary.c'])
    save(output/'gcc-identity.json', dict(path=str(gcc),sha256=sha(gcc),version='15.2.0',scope='strict-C90 syntax only; no GCC runtime/ABI or historical-host qualification'))
    build = output/'build'
    run('configure', ['cmake','--preset','windows-bootstrap','-B',build,'-DPython3_EXECUTABLE='+sys.executable])
    run('build', ['cmake','--build',build,'--config','Release','--parallel','4'],1200)
    identity = json.loads((build/'generated/build-identity.json').read_bytes())
    assert identity['identity']['source_revision']==args.source_revision and identity['identity']['source_state']=='clean'
    assert identity['inputs']=={name:inputs[name] for name in catalog['files']}
    save(output/'build-identity.json',identity)
    run('boundaries', [sys.executable,'-X','utf8','tools/check-build-boundaries.py','--build',build,'--output',output/'build-boundaries.json'])
    boundaries = json.loads((output/'build-boundaries.json').read_bytes())
    assert boundaries['status']=='PASS' and not boundaries['violations']
    assert {'disked_fat','disked_fat_reader','disked_fat_inspection','disked_fat_worker'} <= set(boundaries['targets']['disked']['build_closure'])
    assert not {'disked_gpt_fixture_execution','disked_gpt_fixture_restoration','disked_gpt_fixture_files','disked_journal_prototype','disked_fat_worker_fault','disked_fat_file_fault'} & set(boundaries['targets']['disked']['build_closure'])
    tests = json.loads(run('test-catalog',['ctest','--test-dir',build,'-C','Release','--show-only=json-v1']))
    save(output/'test-catalog.json',tests)
    assert len(tests['tests'])==103
    assert {'disked_fat_content','disked_fat_content_file'} <= set(boundaries['targets']['disked']['build_closure'])
    run('native-tests',['ctest','--test-dir',build,'-C','Release','--parallel','4','--output-on-failure'],2400)
    shutil.copyfile(build/'Testing/Temporary/LastTest.log', output/'native-details.log')
    held = json.loads((build/'fat-content-file-cases.json').read_bytes())
    assert held['passed'] and held['test_methods']==11 and held['cases']==59
    save(output/'fat-content-file-cases.json',held)
    content = json.loads((build/'fat-content-cases.json').read_bytes())
    assert content['passed'] and content['test_methods']==14 and content['cases']==209
    save(output/'fat-content-cases.json',content)
    retention = json.loads((build/'fat-retention-command-cases.json').read_bytes())
    assert retention['passed'] and retention['cases']==68
    save(output/'fat-retention-command-cases.json',retention)
    store = json.loads(run('fat-retention-store',[build/'Release/fat_retention_probe.exe']))
    assert store['passed'] and store['checks']==91 and store['maximum_chunks']==43 and store['concurrent_reads']==400
    save(output/'fat-retention-store.json',store)
    cases = json.loads((build/'fat-cases.json').read_bytes())
    assert cases['passed'] and cases['tests_run']==19 and cases['cases']==1335
    save(output/'fat-cases.json',cases)
    directory_cases = json.loads((build/'fat-directory-cases.json').read_bytes())
    assert directory_cases['passed'] and directory_cases['tests_run']==19 and directory_cases['cases']==6790
    save(output/'fat-directory-cases.json',directory_cases)
    capture_cases=json.loads((build/'fat-capture-cases.json').read_bytes())
    assert capture_cases['passed'] and capture_cases['tests_run']==20 and capture_cases['cases']==149
    save(output/'fat-capture-cases.json',capture_cases)
    scan_cases=json.loads((build/'fat-allocation-scan-cases.json').read_bytes())
    assert scan_cases['passed'] and scan_cases['tests_run']==13 and scan_cases['cases']==86
    save(output/'fat-allocation-scan-cases.json',scan_cases)
    auxiliary_cases=json.loads((build/'fat-auxiliary-cases.json').read_bytes())
    assert auxiliary_cases['passed'] and auxiliary_cases['tests_run']==14 and auxiliary_cases['cases']==257
    save(output/'fat-auxiliary-cases.json',auxiliary_cases)
    namespace_cases=json.loads((build/'fat-namespace-cases.json').read_bytes())
    assert namespace_cases['passed'] and namespace_cases['tests_run']==14 and namespace_cases['cases']==171
    save(output/'fat-namespace-cases.json',namespace_cases)
    worker_cases=json.loads((build/'fat-worker-cases.json').read_bytes())
    assert worker_cases['passed'] and worker_cases['tests_run']==11 and worker_cases['cases']==109
    save(output/'fat-worker-cases.json',worker_cases)
    command_cases=json.loads((build/'fat-command-cases.json').read_bytes())
    assert command_cases['passed'] and command_cases['cases']==62 and len(command_cases['records'])==62
    save(output/'fat-command-cases.json',command_cases)
    window_cases=json.loads((build/'fat-window-cases.json').read_bytes())
    assert window_cases['passed'] and window_cases['tests_run']==9 and window_cases['cases']==34
    save(output/'fat-window-cases.json',window_cases)
    window_commands=json.loads((build/'fat-window-command-cases.json').read_bytes())
    assert window_commands['passed'] and window_commands['cases']==44 and len(window_commands['records'])==44
    save(output/'fat-window-command-cases.json',window_commands)
    run('tooling',[sys.executable,'-X','utf8','-m','unittest','discover','-s','spec/tools/tests','-v'],600)
    text = (output/'logs/tooling.log').read_text(encoding='utf-8')
    count = int(re.search(r'^Ran (\d+) tests ',text,re.MULTILINE).group(1))
    skipped = int(re.search(r'^OK \(skipped=(\d+)\)$',text,re.MULTILINE).group(1))
    check = json.loads(run('spec-check',[sys.executable,'-X','utf8','spec/tools/specctl.py','check']))
    run('index',[sys.executable,'-X','utf8','spec/tools/specctl.py','index','--check'])
    run('manifest',[sys.executable,'-X','utf8','spec/tools/specctl.py','verify-manifest'])
    run('context',[sys.executable,'-X','utf8','spec/tools/specctl.py','context','--work','DE-W046','--output',output/'context','--byte-budget','2200000'])
    run('verify-context',[sys.executable,'-X','utf8','spec/tools/specctl.py','verify-context',output/'context'])
    launch = json.loads(run('product-launch',[build/'Release/disked.exe','build','inspect','--json']))['result']
    assert launch['source_revision']==args.source_revision and launch['version']=='0.1.0-dev.47'
    dumpbin = Path(identity['compiler_path']).with_name('dumpbin.exe'); artifacts=[]
    for name in ('fat_content_probe','disked','disked_fat_test','fat_retention_probe','fat_probe','fat_directory_probe','fat_capture_probe','fat_capture_fault','fat_worker_probe','fat_worker_fault'):
        path = build/'Release'/(name+'.exe')
        for mode in ('headers','imports','dependents'): run(name+'-'+mode,[dumpbin,'/'+mode,path])
        artifacts.append(dict(kind=name,path=str(path),bytes=path.stat().st_size,sha256=sha(path),source_revision=args.source_revision))
    for name in ('disked_fat_content_file','disked_fat_content','disked_fat_retention','disked_fat_inspection','disked_fat_reader','disked_fat_inspection_headers','disked_fat_reader_headers','disked_fat','disked_fat_headers','disked_fat_capture','disked_fat_file','disked_fat_file_fault','disked_fat_namespace','disked_windows_file_names','disked_fat_snapshot','disked_observation_worker','disked_fat_worker','disked_fat_snapshot_fault','disked_observation_worker_fault','disked_fat_worker_fault'):
        artifact = build/(name+'.dir/Release')/(name+'.lib') if name.endswith('_headers') else build/'Release'/(name+'.lib')
        assert artifact.is_file()
        artifacts.append(dict(kind=name,path=str(artifact),bytes=artifact.stat().st_size,sha256=sha(artifact),source_revision=args.source_revision))
    objects = [dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path))
               for name in ('disked_fat_content_file','disked_fat_content','disked_fat_retention','disked_fat_inspection','disked_fat_reader','disked_json','disked_command','disked_invocation','disked_presentation','disked_fat','disked_region_reader','disked_fat_capture','disked_fat_namespace','disked_windows_file_names','disked_fat_snapshot','disked_observation_worker','disked_fat_worker')
               for path in (build/(name+'_headers.dir/Release')).glob('*.obj')]
    assert len(objects)==20;save(output/'header-objects.json',objects)
    config = output/'build-configuration';config.mkdir()
    for name in ('disked_fat_content_file.vcxproj','disked_fat_content_file_headers.vcxproj','fat_content_probe.vcxproj','disked_fat_content.vcxproj','disked_fat_content_headers.vcxproj','disked_fat_retention.vcxproj','disked_fat_retention_headers.vcxproj','fat_retention_probe.vcxproj','disked_fat_reader.vcxproj','disked_fat_inspection.vcxproj','disked_fat_reader_headers.vcxproj','disked_fat_inspection_headers.vcxproj','disked_fat_test.vcxproj','CMakeCache.txt','disked.vcxproj','disked_fat.vcxproj','disked_fat_headers.vcxproj','fat_probe.vcxproj','fat_directory_probe.vcxproj','fat_capture_probe.vcxproj','fat_capture_fault.vcxproj','disked_fat_capture.vcxproj','disked_fat_file.vcxproj','disked_fat_file_fault.vcxproj','disked_fat_namespace.vcxproj','disked_windows_file_names.vcxproj','disked_fat_namespace_headers.vcxproj','disked_windows_file_names_headers.vcxproj','disked_fat_snapshot.vcxproj','disked_fat_snapshot_headers.vcxproj','disked_observation_worker.vcxproj','disked_observation_worker_headers.vcxproj','disked_fat_worker.vcxproj','disked_fat_worker_headers.vcxproj','disked_fat_snapshot_fault.vcxproj','disked_observation_worker_fault.vcxproj','disked_fat_worker_fault.vcxproj','fat_worker_probe.vcxproj','fat_worker_fault.vcxproj'):
        shutil.copyfile(build/name,config/name)
    shutil.copytree(build/'.cmake/api/v1/reply',output/'cmake-codemodel')
    shutil.copyfile(build/'private-header-usage.json',output/'private-header-usage.json')
    assert not run('final-source-status',['git','status','--porcelain']).strip()
    assert all(sha(checkout/name)==digest for name,digest in inputs.items())
    save(output/'summary.json',dict(source_revision=args.source_revision,source_state='clean',host=host,
        source_input_count=len(inputs),product_input_count=len(catalog['files']),native_test_groups=103,
        fat_content_file_methods=11,fat_content_file_cases=59,fat_content_methods=14,fat_content_cases=209,fat_retention_commands=68,fat_retention_store_checks=91,maximum_retention_chunks=43,fat_window_methods=9,fat_window_cases=34,fat_window_commands=44,fat_command_cases=62,fat_test_methods=19,fat_cases=1335,directory_test_methods=19,directory_cases=6790,capture_test_methods=20,capture_cases=149,scan_test_methods=13,scan_cases=86,auxiliary_test_methods=14,auxiliary_cases=257,namespace_test_methods=14,namespace_cases=171,worker_test_methods=11,worker_cases=109,tooling_count=count,tooling_skipped=skipped,structural=check,
        build_target_count=boundaries['target_count'],quoted_include_edges=boundaries['quoted_include_edges'],
        independent_header_compilations=20,gcc_scope='strict C90 syntax; no GCC runtime qualification',
        artifacts=artifacts,passed=True,physical_device_access=False,product_dispatch_admitted=False,
        filesystem_health_qualified=False,owner_accepted=False,unit_complete=False,release_ready=False))
    print('Exact-source held-file FAT content campaign completed.',flush=True)


if __name__=='__main__': main()
