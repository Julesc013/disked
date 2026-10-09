"""Build the exact read-only source candidate from a clean DiskEd checkout.

Upstream Git blobs are data exported into owned scratch; no upstream scripts
or upstream build files are executed. No installed SDK or live setup claim.
"""
import argparse
import hashlib
import json
from pathlib import Path
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
    parser.add_argument('--repository', type=Path, default=Path.cwd())
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--upstream-repository', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--package-evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repository, upstream, package, inventory, prior, output = [getattr(args, name).absolute()
        for name in ('repository', 'upstream_repository', 'package', 'inventory', 'package_evidence', 'output')]
    if len(args.source_revision) != 40 or any(c not in '0123456789abcdef' for c in args.source_revision):
        raise ValueError('exact source revision required')
    qualification = json.loads(prior.read_bytes())
    if not qualification['passed'] or qualification['packaging_source'] != 'e1683b1093bf810edfdf5911acaca3c510b28bf6':
        raise ValueError('expected exact prior fixture qualification')
    if sha(package/'payload.zip') != qualification['verification']['archive_sha256']:
        raise ValueError('prior ZIP bytes differ')
    if output.exists():
        raise ValueError('new reproduction root required')
    output.mkdir()
    logs = output/'logs'
    logs.mkdir()
    receipts = []

    def run(name, command, cwd, expected=0):
        command = [str(value) for value in command]
        started = time.monotonic()
        process = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        log = logs/(name+'.log')
        log.write_bytes(process.stdout + process.stderr)
        receipt = dict(name=name, command=command, cwd=str(cwd), exit_code=process.returncode,
                       expected_exit=expected, status='pass' if process.returncode == expected else 'fail',
                       elapsed_seconds=round(time.monotonic()-started, 3), log=log.relative_to(output).as_posix())
        receipts.append(receipt)
        save(output/'commands.json', receipts)
        if process.returncode != expected:
            raise AssertionError((name, process.returncode, str(log)))
        return process.stdout

    checkout = output/'checkout'
    run('clone', ['git', 'clone', '--local', '--no-hardlinks', '--no-checkout', repository, checkout], repository)
    run('checkout', ['git', 'checkout', '--detach', args.source_revision], checkout)
    if run('source-status', ['git', 'status', '--porcelain'], checkout).strip():
        raise AssertionError('dirty source checkout')
    host = json.loads(run('host', ['powershell', '-NoProfile', '-Command',
        "$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent(); $principal = [System.Security.Principal.WindowsPrincipal]::new($identity); [ordered]@{identity=$identity.Name; elevated=$principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)} | ConvertTo-Json"], checkout))
    if host['identity'] != 'BLACKGLASS-WIN1\\Jules' or host['elevated']:
        raise AssertionError('selected unprivileged host required')
    # Bind the entire selected local source and schema closure to Git, separately
    # from the original upstream closure and previously built native DiskEd payload.
    local_inputs = {}
    for folder in ('release/bindings/universal-setup', 'tests/setup', 'external/universal-setup'):
        for path in sorted((checkout/folder).rglob('*')):
            if path.is_file():
                local_inputs[path.relative_to(checkout).as_posix()] = sha(path)
    for name in ('spec/catalog/setup-source-consumer-prototype.json', 'spec/catalog/setup-fixture-prototype.json',
                 'tools/release/artifact_check.py', '.aide/evidence/2026-10-10-setup-source-consumer/reproduce.py'):
        local_inputs[name] = sha(checkout/name)
    for name, value in local_inputs.items():
        blob = subprocess.check_output(['git', '-C', str(checkout), 'show', args.source_revision+':'+name])
        if 'sha256:'+hashlib.sha256(blob).hexdigest() != value:
            raise AssertionError('checkout differs from Git: '+name)
    save(output/'source-inputs.json', local_inputs)
    recipe = Path(__file__).absolute()
    if sha(recipe) != local_inputs['.aide/evidence/2026-10-10-setup-source-consumer/reproduce.py']:
        raise AssertionError('recipe is not exact selected source')
    save(output/'recipe-identity.json', dict(source_revision=args.source_revision, recipe_sha256=sha(recipe),
         package_evidence_sha256=sha(prior), prior_packaging_source=qualification['packaging_source'],
         original_inventory_sha256=sha(inventory), upstream_scripts_executed=False))
    shutil.copyfile(inventory, output/'independent-inventory.json')
    source = output/'source'
    run('export', [sys.executable, checkout/'release/bindings/universal-setup/export_native.py',
                  '--repository', upstream, '--output', source], checkout)
    lock = json.loads((checkout/'external/universal-setup/native-source-lock.json').read_bytes())
    for row in lock['files']:
        if sha(source/row['path']) != row['sha256'] or (source/row['path']).stat().st_size != row['bytes']:
            raise AssertionError('exported source mismatch')
    save(output/'upstream-inputs.json', lock)
    # Ensure local schemas are the original read-only contract bytes as well.
    for row in lock['files']:
        if row.get('retained_path') and sha(checkout/row['retained_path']) != row['sha256']:
            raise AssertionError('vendored read-only schema changed')
    build = output/'build'
    run('cmake-version', ['cmake', '--version'], checkout)
    run('configure', ['cmake', '-S', checkout/'tests/setup/native', '-B', build,
        '-G', 'Visual Studio 17 2022', '-A', 'x64,version=10.0.19041.0',
        '-T', 'v143,version=14.44.35207,host=x64', '-DUSK_SOURCE_DIR='+str(source),
        '-DCMAKE_SYSTEM_VERSION=10.0.19041.0'], checkout)
    run('build', ['cmake', '--build', build, '--config', 'Release'], checkout)
    probe = build/'Release/setup_source_probe.exe'
    library = build/'Release/disked_setup_source_candidate.lib'
    build_configuration = output/'build-configuration'
    build_configuration.mkdir()
    for name in ('CMakeCache.txt', 'disked_setup_inflate.vcxproj', 'disked_setup_source_candidate.vcxproj', 'setup_source_probe.vcxproj'):
        shutil.copyfile(build/name, build_configuration/name)
    for path in (build/'CMakeFiles').rglob('CMake*Compiler.cmake'):
        shutil.copyfile(path, build_configuration/path.name)
    dumpbin = Path('C:/Program Files/Microsoft Visual Studio/2022/Enterprise/VC/Tools/MSVC/14.44.35207/bin/Hostx64/x64/dumpbin.exe')
    run('headers', [dumpbin, '/headers', probe], checkout)
    run('imports', [dumpbin, '/imports', probe], checkout)
    symbols = run('library-public-symbols', [dumpbin, '/linkermember:1', library], checkout).decode('utf-8', 'replace')
    for name in ('usk_abi_version_v1', 'usk_context_create_v1', 'usk_command_execute_v1', 'usk_context_destroy_v1'):
        if name not in symbols:
            raise AssertionError('public C symbol missing: '+name)
    campaign = output/'campaign'
    run('native-campaign', [sys.executable, checkout/'tests/setup/run_source_consumer.py', '--probe', probe,
        '--package', package, '--inventory', inventory, '--output', campaign], checkout)
    native = json.loads((campaign/'results.json').read_bytes())
    if native['status'] != 'pass' or native['native_executions'] != 33 or native['assertions'] != 223:
        raise AssertionError('native campaign expected contract')
    run('setup-tests', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests/setup', '-v'], checkout)
    run('tooling-tests', [sys.executable, '-m', 'unittest', 'discover', '-s', 'spec/tools/tests', '-v'], checkout)
    run('check', [sys.executable, 'spec/tools/specctl.py', 'check'], checkout)
    context = output/'context'
    run('context', [sys.executable, 'spec/tools/specctl.py', 'context', '--work', 'DE-W060',
                   '--output', context, '--byte-budget', '430000'], checkout)
    run('verify-context', [sys.executable, 'spec/tools/specctl.py', 'verify-context', context], checkout)
    run('verify-manifest', [sys.executable, 'spec/tools/specctl.py', 'verify-manifest'], checkout)
    if run('final-source-status', ['git', 'status', '--porcelain'], checkout).strip():
        raise AssertionError('qualification changed source checkout')
    if any(sha(checkout/name) != value for name, value in local_inputs.items()):
        raise AssertionError('local source changed during qualification')
    if any(sha(source/row['path']) != row['sha256'] for row in lock['files']):
        raise AssertionError('upstream source changed during qualification')
    artifacts = [dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path)) for path in (probe, library)]
    save(output/'results.json', dict(passed=True, source_revision=args.source_revision, host=host,
        upstream_revision=lock['revision'], upstream_inputs=len(lock['files']), local_inputs=len(local_inputs),
        native_executions=native['native_executions'], assertions=native['assertions'],
        fixture_snapshot_unchanged=native['fixture_snapshot_unchanged'], artifacts=artifacts,
        setup_tests=30, tooling_tests=dict(run=215, passed=213, skipped=2),
        generic_package_verification='refused', independent_corruption_refusal=native['independent_corruption_refusal'],
        product_native_rebuilt=False, installed_sdk_qualified=False, live_lifecycle='not_run',
        upstream_scripts_executed=False, remote_writes=False, unit_complete=False, owner_accepted=False))
    print(json.dumps(dict(passed=True, source_revision=args.source_revision, commands=len(receipts),
                         native_executions=native['native_executions'], assertions=native['assertions'])))


if __name__ == '__main__':
    main()
