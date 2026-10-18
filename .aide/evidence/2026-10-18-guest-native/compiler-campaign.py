"""Reuse the qualified guest bootstrap with a bounded native compiler payload."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PRIOR = ROOT / '.aide/evidence/2026-10-18-guest-capacity'


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise RuntimeError('Qualified bootstrap adaptation point changed: ' + old)
    return source.replace(old, new)


def main():
    work = Path(os.environ['DISKED_WORK_ROOT']).resolve()
    if (HERE / 'compiler-results.json').exists():
        raise RuntimeError('Preserve and review the existing compiler result before another attempt')
    stage = work / 'guest-bootstrap'
    stage.mkdir()
    for name in ('guest-proof.ps1', 'attach-image.py'):
        shutil.copyfile(PRIOR / name, stage / name)
    shutil.copyfile(HERE / 'compiler-driver.py', stage / 'guest-proof.py')
    for name in ('compiler.cpp', 'expected.json'):
        shutil.copyfile(HERE / name, stage / name)
    root_line = "$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\\..\\..'))"
    fixed_root = "$root='" + str(ROOT).replace("'", "''") + "'"
    host = replace_once((PRIOR / 'run-proof.ps1').read_text(), root_line, fixed_root)
    host = replace_once(host, 'org.disked.guest-capacity-campaign/1', 'org.disked.guest-native-campaign/1')
    host = replace_once(host, '    $selected=@(', "    $selected=@(\n        @{host=(Join-Path $PSScriptRoot 'compiler.cpp');relative='compiler.cpp'},")
    # Observe actual host backing growth as well as free space. This shared-file
    # delta is conservative, not attribution to DiskEd or permission to grow it.
    host = replace_once(host, '    foreach($file in $selected)', "    $backing=@(Get-VMHardDiskDrive -VM $vm);if($backing.Count-ne1){throw 'Unexpected VM disk topology.'}\n    $backingPath=$backing[0].Path\n    $backingStart=(Get-Item -LiteralPath $backingPath).Length\n    $result.host_backing_start_bytes=$backingStart\n    foreach($file in $selected)")
    host = replace_once(host, '        Start-Sleep -Seconds 1', "        $growth=(Get-Item -LiteralPath $backingPath).Length-$backingStart\n        if($growth-gt1GB){Stop-Job -Job $job;throw 'Shared VM backing growth exceeded campaign ceiling; owned remote campaign stopped.'}\n        Start-Sleep -Seconds 1")
    host = replace_once(host, '    $result.status=\'pass\'', "    $result.host_backing_end_bytes=(Get-Item -LiteralPath $backingPath).Length\n    $result.status='pass'")
    (stage / 'run-proof.ps1').write_text(host, encoding='utf-8', newline='\n')
    cleanup = replace_once((PRIOR / 'clean-proof.ps1').read_text(), root_line, fixed_root)
    (stage / 'clean-proof.ps1').write_text(cleanup, encoding='utf-8', newline='\n')
    source_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.iterdir()}
    result = subprocess.run(['pwsh', '-NoProfile', '-File', str(stage / 'run-proof.ps1'), '-SizeMiB', '512'],
                            cwd=ROOT, capture_output=True, timeout=300)
    campaign_file = stage / 'proof-512.json'
    if not campaign_file.exists():
        raise RuntimeError('No campaign receipt; guest recovery must be inspected before retrying')
    campaign = json.loads(campaign_file.read_bytes())
    campaign['generated_bootstrap_sha256'] = source_hashes
    campaign['bootstrap_source_revision'] = 'c038fb5069d342052e0d3623473010e1a4df3b5f'
    campaign['source_adaptation'] = 'Qualified fixed-guest setup unchanged; native payload and compiler.cpp source selected. Host root fixed for managed staging; additional 1 GiB shared-backing growth admission.'
    campaign['host_command_exit_code'] = result.returncode
    (HERE / 'compiler-results.json').write_text(json.dumps(campaign, indent=2)+'\n', encoding='utf-8', newline='\n')
    if campaign.get('guest', {}).get('setup', {}).get('image_removed'):
        cleanup_result = subprocess.run(['pwsh', '-NoProfile', '-File', str(stage / 'clean-proof.ps1'), '-SizeMiB', '512'],
                                        cwd=ROOT, capture_output=True, timeout=60)
        if cleanup_result.returncode:
            (HERE / 'compiler-cleanup-error.txt').write_bytes((cleanup_result.stdout + cleanup_result.stderr)[:16384])
            raise RuntimeError('Guest source/report cleanup failed')
        shutil.copyfile(stage / 'cleanups.json', HERE / 'compiler-cleanup.json')
    else:
        raise RuntimeError('Owned image retirement is unverified; inspect guest before retrying')
    print(json.dumps({'status': campaign['status'], 'host_command_exit_code': result.returncode,
                      'image_removed': True, 'source_copy_removed': True}))
    return 0 if result.returncode == 0 and campaign['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
