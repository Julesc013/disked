"""Run the bounded disposable-profile proof; no MMC observation is claimed."""
import importlib.util
import json
import lzma
import os
from pathlib import Path
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OLD = HERE.parent.parent/'2026-10-18-ordinary-worker'
HERE = HERE/'profile'
HERE.mkdir(exist_ok=True)
work = Path(os.environ['DISKED_WORK_ROOT'])
prepare = sys.argv[1:] == ['--prepare-only']
if sys.argv[1:] not in ([], ['--prepare-only']): raise ValueError('Only execution or preparation')
if (HERE/'receipt.json.xz').exists() and not prepare: raise ValueError('Retain/review previous attempt')
if any((OLD/name).exists() for name in ('result.json', 'cleanup.json', 'runner-error.txt', 'retained.tar.xz')):
    raise ValueError('Previous raw campaign outputs must be retained first')
record = dict(status='running', source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(), commands=[])
prepared_before = (OLD/'prepared.json').read_bytes() if (OLD/'prepared.json').exists() else None

def call(args, env=None):
    value = subprocess.run(list(map(str,args)), cwd=ROOT, env=env, capture_output=True, timeout=180)
    assert len(value.stdout)+len(value.stderr) <= 65536
    record['commands'].append(dict(argv=value.args, exit_code=value.returncode,
        stdout=value.stdout.decode(errors='replace'), stderr=value.stderr.decode(errors='replace')))
    if value.returncode: raise RuntimeError('Command failed: '+str(value.args))

def packed(name, body):
    assert len(body) <= 8388608
    data = lzma.compress(body, filters=[dict(id=lzma.FILTER_LZMA2, dict_size=1048576, preset=6)])
    assert lzma.decompress(data) == body
    (HERE/name).write_bytes(data)

try:
    if not prepare:
        call(['pwsh','-NoProfile','-File','tools/clean-scratch.ps1','-Delete','-WorkersStopped'])
        call([sys.executable,'-B','-m','pip','install','--disable-pip-version-check','--no-cache-dir','--no-compile',
            '--no-deps','--only-binary=:all:','--target',work/'dependencies','PyYAML==6.0.3'])
        env = dict(os.environ, PYTHONPATH=str(work/'dependencies'), PYTHONDONTWRITEBYTECODE='1')
        call([sys.executable,'-B','tools/workspace.py','check','--planned-bytes','29360128'])
        call([sys.executable,'-B','spec/tools/specctl.py','context','--work','DE-W107','--output',
            '.aide-local/context/current','--byte-budget','2097152','--artifact-byte-budget','25165824'], env)
        call([sys.executable,'-B','spec/tools/specctl.py','verify-context','.aide-local/context/current'], env)
    spec = importlib.util.spec_from_file_location('bounded_control_campaign', OLD/'campaign.py')
    campaign = importlib.util.module_from_spec(spec); spec.loader.exec_module(campaign)
    sys.argv = [str(OLD/'campaign.py'), '--windows-ui-profile', *(['--prepare-only'] if prepare else [])]
    code = campaign.main()
    if code: raise RuntimeError('Guest coordinator control did not pass')
    record['status'] = 'pass'
except BaseException:
    record['status'] = 'fail'
    record['error'] = traceback.format_exc()[-16384:]
    raise
finally:
    try:
        for source, target in [('prepared.json','prepared.json.xz'), ('result.json','receipt.json.xz'),
                               ('cleanup.json','cleanup.json.xz'), ('runner-error.txt','runner-error.txt.xz')]:
            path = OLD/source
            if path.exists():
                packed(target,path.read_bytes())
                if source == 'prepared.json' and prepared_before is not None: path.write_bytes(prepared_before)
                else: path.unlink()
        archive = OLD/'retained.tar.xz'
        if archive.exists():
            if (HERE/archive.name).exists(): raise ValueError('Preserve retained archive')
            archive.replace(HERE/archive.name)
        if not prepare:
            call(['pwsh','-NoProfile','-File','tools/clean-scratch.ps1','-Delete','-WorkersStopped'])
    finally:
        packed('preparation.json.xz' if prepare else 'launch.json.xz', (json.dumps(record,indent=2)+'\n').encode())
