"""Bounded exact-source guest configure/build/test campaign; no host native tests."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PRIOR = ROOT / '.aide/evidence/2026-10-18-guest-capacity'


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Bootstrap adaptation point changed: ' + old)
    return text.replace(old, new)


def main():
    work = Path(os.environ['DISKED_WORK_ROOT']).resolve()
    prepare_only = sys.argv[1:] == ['--prepare-only']
    if sys.argv[1:] and not prepare_only:
        raise ValueError('Unknown campaign option')
    if (HERE / 'result.json').exists():
        raise ValueError('Retain/review the existing result before another campaign')
    definition = importlib.util.spec_from_file_location('snapshot', ROOT / 'tools/source-snapshot.py')
    snapshot = importlib.util.module_from_spec(definition)
    definition.loader.exec_module(snapshot)
    if prepare_only:
        export = work / 'source-export'
        export.mkdir()
        (export / 'source.pack').write_bytes(b'not-an-executable-qualification-pack')
        (export / 'source.json').write_text('{}\n')
        source = None
    else:
        revision = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
        # The product snapshot is immutable Git data; the coordinator may retain
        # observations alongside it without falsely calling its checkout clean.
        source = snapshot.export(ROOT, snapshot.selected_inputs(ROOT, 'DE-W105', revision=revision),
                                 work / 'source-export', work, revision=revision)
    stage = work / 'guest-bootstrap'
    stage.mkdir()
    shutil.copyfile(work / 'source-export/source.pack', stage / 'source.pack')
    shutil.copyfile(work / 'source-export/source.json', stage / 'source.json')
    shutil.copyfile(ROOT / 'tools/source-snapshot.py', stage / 'source-snapshot.py')
    for name in ('guest-source.py', 'expected.json'):
        shutil.copyfile(HERE / name, stage / name)
    shutil.copyfile(HERE / 'build-driver.py', stage / 'guest-proof.py')
    shutil.copyfile(PRIOR / 'attach-image.py', stage / 'attach-image.py')
    guest = (PRIOR / 'guest-proof.ps1').read_text()
    old = "        $log=@(& $python -B (Join-Path $root 'tools\\workspace.py') run -- $python -B (Join-Path $root 'guest-proof.py') 2>&1)"
    guest = replace_once(guest, old,
        "        $log=@(& $python -B (Join-Path $root 'source\\tools\\workspace.py') run -- $python -B (Join-Path $root 'guest-proof.py') 2>&1)")
    guest = replace_once(guest, "    $nativePreference=$ErrorActionPreference\n    try{\n        $ErrorActionPreference='Continue'\n        $workersStarted=$true",
        "    $workersStarted=$true\n    & $python -B (Join-Path $root 'guest-source.py') prepare\n    $sourceCode=$LASTEXITCODE\n    $workersStopped=$true\n    if($sourceCode-ne0){throw 'Source preparation failed.'}\n    $nativePreference=$ErrorActionPreference\n    try{\n        $ErrorActionPreference='Continue'\n        $workersStarted=$true\n        $workersStopped=$false")
    guest = replace_once(guest, "    $result.finished_at=[DateTime]::UtcNow.ToString('o')",
        "    if(Test-Path -LiteralPath (Join-Path $root 'source-owner.json')){\n        try{\n            Assert-WorkersStopped $workersStarted $workersStopped\n            & $python -B (Join-Path $root 'guest-source.py') retire\n            if($LASTEXITCODE-ne0){throw 'Owned source retirement failed.'}\n        }catch{$result.status='fail';$result.source_cleanup_error=$_.Exception.Message}\n    }\n    $result.finished_at=[DateTime]::UtcNow.ToString('o')")
    (stage / 'guest-proof.ps1').write_text(guest, encoding='utf-8', newline='\n')
    root_line = "$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\\..\\..'))"
    fixed_root = "$root='" + str(ROOT).replace("'", "''") + "'"
    host = replace_once((PRIOR / 'run-proof.ps1').read_text(), root_line, fixed_root)
    host = replace_once(host, 'org.disked.guest-capacity-campaign/1', 'org.disked.guest-product-campaign/1')
    host = replace_once(host, 'setup=$setup;proof=$proof;',
        "setup=$setup;proof=$proof;source_prepared=$(if(Test-Path -LiteralPath \"$root\\source-prepared.json\"){Get-Content -LiteralPath \"$root\\source-prepared.json\" -Raw|ConvertFrom-Json});source_retired=$(if(Test-Path -LiteralPath \"$root\\source-retired.json\"){Get-Content -LiteralPath \"$root\\source-retired.json\" -Raw|ConvertFrom-Json});")
    rows = '\n'.join("        @{host=(Join-Path $PSScriptRoot '"+name+"');relative='"+name+"'},"
                     for name in ('source.pack', 'source.json', 'source-snapshot.py', 'guest-source.py'))
    host = replace_once(host, '    $selected=@(', '    $selected=@(\n' + rows)
    host = replace_once(host, '    foreach($file in $selected)',
        "    $backing=@(Get-VMHardDiskDrive -VM $vm);if($backing.Count-ne1){throw 'Unexpected VM disk topology.'}\n    $backingPath=$backing[0].Path\n    $backingStart=(Get-Item -LiteralPath $backingPath).Length\n    $result.host_backing_start_bytes=$backingStart\n    foreach($file in $selected)")
    host = replace_once(host, '        Start-Sleep -Seconds 1',
        "        if(((Get-Item -LiteralPath $backingPath).Length-$backingStart)-gt1GB){Stop-Job -Job $job;throw 'Shared VM backing growth exceeded campaign ceiling.'}\n        Start-Sleep -Seconds 1")
    host = replace_once(host, "    if($result.guest.setup.status-ne'pass'",
        "    $retained=Invoke-Command -Session $session -ScriptBlock { $p='C:\\ProgramData\\DiskEd\\qualification\\retained.zip';if(Test-Path -LiteralPath $p){$f=Get-Item -LiteralPath $p;if($f.Length-gt32MB-or($f.Attributes-band[IO.FileAttributes]::ReparsePoint)){throw 'Invalid retained archive.'};$true}else{$false}}\n    if($retained){Copy-Item -FromSession $session -LiteralPath 'C:\\ProgramData\\DiskEd\\qualification\\retained.zip' -Destination (Join-Path $PSScriptRoot 'retained.zip')}\n    $result.host_backing_end_bytes=(Get-Item -LiteralPath $backingPath).Length\n    if($result.guest.setup.status-ne'pass'")
    host = host.replace('retained.zip', 'retained.tar.xz')
    (stage / 'run-proof.ps1').write_text(host, encoding='utf-8', newline='\n')
    cleanup = replace_once((PRIOR / 'clean-proof.ps1').read_text(), root_line, fixed_root)
    cleanup = replace_once(cleanup, '$paths=@($Expected', "$extra=@(\"$root\\source-owner.json\",\"$root\\source-prepared.json\",\"$root\\source-retired.json\",\"$root\\scoped-directory-access.json\",\"$root\\retained.zip\")\n        $paths=$extra+@($Expected")
    cleanup = cleanup.replace('retained.zip', 'retained.tar.xz')
    cleanup = replace_once(cleanup, '$items.Count-gt32', '$items.Count-gt40')
    (stage / 'clean-proof.ps1').write_text(cleanup, encoding='utf-8', newline='\n')
    bindings = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.iterdir()}
    # Parse generated scripts using the guest's actual language version, without
    # executing either script or changing the host/guest execution policy.
    parser = "$errors=$null;$tokens=$null;foreach($file in Get-ChildItem -LiteralPath $args[0] -Filter '*.ps1'){$null=[Management.Automation.Language.Parser]::ParseFile($file.FullName,[ref]$tokens,[ref]$errors);if($errors.Count){throw ($errors|Out-String)}}"
    checked = subprocess.run([str(Path(os.environ['WINDIR']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'),
                              '-NoProfile', '-Command', '& {'+parser+'} ' + "'" + str(stage).replace("'", "''") + "'"],
                             capture_output=True, timeout=30)
    if checked.returncode:
        raise RuntimeError('Generated PowerShell syntax failed: ' + checked.stderr.decode(errors='replace'))
    if prepare_only:
        (HERE / 'preparation.json').write_text(json.dumps({'status': 'pass', 'scope': 'Adaptation and Windows PowerShell 5.1 parse only; no guest or native execution',
                                                          'source_sha256': bindings}, indent=2)+'\n', encoding='utf-8', newline='\n')
        print(json.dumps({'status': 'pass', 'native_execution': False}))
        return 0
    outcome = subprocess.run(['pwsh', '-NoProfile', '-File', str(stage / 'run-proof.ps1'), '-SizeMiB', '512'],
                             cwd=ROOT, capture_output=True, timeout=9000)
    report = stage / 'proof-512.json'
    if not report.exists():
        raise RuntimeError('No campaign receipt; inspect guest before attempting another run')
    result = json.loads(report.read_bytes())
    result['template_native_product_tests_run'] = result.get('native_product_tests_run', False)
    commands = (result.get('guest', {}).get('proof') or {}).get('commands', [])
    result['native_product_tests_run'] = any(c['label'].startswith('test-') for c in commands)
    result['native_product_build_run'] = any(c['label'] == 'build-win32' for c in commands)
    result['exact_source'] = {key: source[key] for key in ('revision', 'content_bytes', 'pack_bytes', 'pack_sha256', 'git_objects')}
    result['generated_input_sha256'] = bindings
    result['host_exit_code'] = outcome.returncode
    result['host_error_tail'] = outcome.stderr[-8192:].decode(errors='replace')
    (HERE / 'result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    retained = stage / 'retained.tar.xz'
    if retained.exists():
        expected = result.get('guest', {}).get('proof', {}).get('archive_sha256')
        if hashlib.sha256(retained.read_bytes()).hexdigest() != expected:
            raise RuntimeError('Retained observations hash mismatch')
        shutil.copyfile(retained, HERE / 'observations.tar.xz')
    if result.get('guest', {}).get('setup', {}).get('image_removed'):
        retired = subprocess.run(['pwsh', '-NoProfile', '-File', str(stage / 'clean-proof.ps1'), '-SizeMiB', '512'],
                                 cwd=ROOT, capture_output=True, timeout=60)
        if retired.returncode:
            (HERE / 'cleanup-error.txt').write_bytes((retired.stdout+retired.stderr)[-16384:])
            raise RuntimeError('Guest source/report cleanup requires review')
        shutil.copyfile(stage / 'cleanups.json', HERE / 'cleanup.json')
    else:
        raise RuntimeError('Image/worker retirement is unverified; inspect the owned guest state')
    print(json.dumps({'status': result['status'], 'source_revision': source['revision'], 'image_removed': True}))
    return 0 if outcome.returncode == 0 and result['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
