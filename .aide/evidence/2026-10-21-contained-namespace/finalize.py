"""Check the final handoff and source-sync metadata without rerunning native code."""
import argparse
import hashlib
import json
import lzma
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--phase',choices=('before-sync','after-sync'),required=True)
phase=parser.parse_args().phase
work=Path(os.environ['DISKED_WORK_ROOT'])
env=dict(os.environ,PYTHONPATH=str(work/'dependencies'),PYTHONDONTWRITEBYTECODE='1')
record=dict(status='running',phase=phase,scope='Final metadata/handoff checks only;not a new native build',commands=[])
source='c0eab59bb47b1cc4931afb4042a68bb3343afd28'
handoff=ROOT/'.aide/handoffs/DE-W030-qualification-repair-2026-10-21.json'

def run(arguments):
    value=subprocess.run([sys.executable,'-B',*map(str,arguments)],cwd=ROOT,env=env,capture_output=True,timeout=180)
    if len(value.stdout)+len(value.stderr)>131072:raise ValueError('Final check output bound')
    record['commands'].append(dict(arguments=value.args,exit_code=value.returncode,
        stdout=value.stdout.decode(errors='replace'),stderr=value.stderr.decode(errors='replace')))
    if value.returncode:raise RuntimeError('Final metadata check failed: '+str(arguments))

try:
    full=json.loads(lzma.decompress((HERE/'validation.json.xz').read_bytes()))
    assert full['status']=='pass' and full['native_gate_passed'] and full['tested_inputs_unchanged']
    native_scopes=['source/','tests/','tools/','CMakeLists.txt','CMakePresets.json','cmake/']
    delta=subprocess.check_output(['git','diff','--name-only',source,'--',*native_scopes],cwd=ROOT,text=True).splitlines()
    if delta:raise ValueError('Native implementation/test/build inputs changed: '+repr(delta))
    record.update(native_tested_source=source,native_code_and_tests_unchanged=True,
        full_host_validation_sha256=hashlib.sha256((HERE/'validation.json.xz').read_bytes()).hexdigest())
    run(['-m','pip','install','--disable-pip-version-check','--no-cache-dir','--no-compile','--no-deps','--only-binary=:all:',
         '--target',env['PYTHONPATH'],'PyYAML==6.0.3'])
    for arguments in [['spec/tools/specctl.py','index'],['spec/tools/specctl.py','manifest'],
        ['spec/tools/specctl.py','check'],['tools/check-source-map.py'],['spec/tools/specctl.py','verify-manifest']]:run(arguments)
    value=json.loads(handoff.read_bytes())
    value['spec_manifest_digest']='sha256:'+hashlib.sha256((ROOT/'spec/manifest.json').read_bytes()).hexdigest()
    value['blockers']=[s for s in value['blockers'] if not s.startswith('No current native/')]
    handoff.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
    import jsonschema
    jsonschema.Draft202012Validator(json.loads((ROOT/'spec/schemas/handoff.schema.json').read_bytes())).validate(value)
    for artifact in value['artifacts']:
        path=(ROOT/artifact['path']).resolve()
        if not path.is_relative_to(ROOT) or artifact['sha256']!='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError('Handoff artifact differs: '+artifact['path'])
    record.update(handoff_schema_valid=True,handoff_artifacts_verified=len(value['artifacts']),
        handoff_sha256=hashlib.sha256(handoff.read_bytes()).hexdigest())
    run(['spec/tools/specctl.py','context','--work','DE-W030','--output',work/'context',
         '--byte-budget','2097152','--artifact-byte-budget','27262976'])
    run(['spec/tools/specctl.py','verify-context',work/'context'])
    record['metadata_delta_from_full_validation']=[p for p,digest in full['tested_inputs'].items()
        if not (ROOT/p).is_file() or hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=digest]
    record['status']='pass'
except BaseException:
    record['status']='fail'
    raise
finally:
    body=(json.dumps(record,indent=2)+'\n').encode()
    if len(body)>262144:raise ValueError('Finalization receipt bound')
    name='finalization-before-sync.json.xz' if phase=='before-sync' else 'finalization.json.xz'
    (HERE/name).write_bytes(lzma.compress(body,filters=[dict(id=lzma.FILTER_LZMA2,dict_size=1048576,preset=6)]))
