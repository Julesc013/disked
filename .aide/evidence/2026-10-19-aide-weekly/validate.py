"""Passive queue-schema check; never imports or executes upstream implementation."""
import hashlib
import json
import lzma
import os
from pathlib import Path
import subprocess
import sys
import jsonschema

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
work=Path(os.environ['DISKED_WORK_ROOT'])
deps=work/'dependencies'
env=dict(os.environ,PYTHONPATH=str(deps)+os.pathsep+str(ROOT/'spec/tools/tests'),PYTHONDONTWRITEBYTECODE='1')
record=dict(status='running',scope='Passive schema/source validation only; no upstream execution,install,live consumer or native qualification',commands=[])

def run(command):
    result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=300)
    assert len(result.stdout)+len(result.stderr)<=131072
    record['commands'].append(dict(arguments=list(map(str,command)),exit_code=result.returncode,
        stdout=result.stdout.decode(errors='replace'),stderr=result.stderr.decode(errors='replace')))
    assert result.returncode==0

try:
    run([sys.executable,'-B','-m','pip','install','--disable-pip-version-check','--no-cache-dir','--no-deps','--only-binary=:all:','--target',str(deps),'PyYAML==6.0.3'])
    observed=json.loads((HERE/'source-review.json').read_bytes())
    data=(HERE/'selected-source.json.xz').read_bytes()
    assert hashlib.sha256(data).hexdigest()==observed['archive']['sha256']
    raw=lzma.decompress(data);assert hashlib.sha256(raw).hexdigest()==observed['archive']['uncompressed_sha256']
    source=json.loads(raw)['selected_source'];schema=source['.aide/protocol/aide-workunit.schema.json'].encode()
    assert hashlib.sha256(schema).hexdigest()=='de82b312e2859191d8dac4153f25ae29237d1e4065a5d4a9837ea52d95dab964'
    validator=jsonschema.Draft202012Validator(json.loads(schema));validator.check_schema(validator.schema)
    run([sys.executable,'-B','spec/tools/specctl.py','aide-export','--output',str(work/'exports')])
    units=json.loads((ROOT/'spec/work/units.json').read_bytes())['units'];expected={w['id'] for w in units}
    files=sorted((work/'exports').glob('*.json'));assert len(files)==len(expected)==98
    rows=[]
    for path in files:
        data=path.read_bytes();value=json.loads(data);validator.validate(value)
        assert value['kind']=='WorkUnit' and value['metadata']['id']==path.stem
        assert value['spec']['authorizes_implementation'] is False
        assert value['status']['phase']=='planned' and value['status']['result']=='NOT_RUN' and value['status']['validated'] is False
        rows.append(dict(id=path.stem,sha256=hashlib.sha256(data).hexdigest()))
    assert {r['id'] for r in rows}==expected
    record.update(records=rows,validated_workunits=len(rows),aide_revision=observed['revision'],aide_tree=observed['tree'],schema_sha256=hashlib.sha256(schema).hexdigest())
    if '--passive-only' not in sys.argv:
        for command in ([sys.executable,'-B','spec/tools/specctl.py','index'],
                        [sys.executable,'-B','spec/tools/specctl.py','check'],
                        [sys.executable,'-B','-m','unittest','test_specctl.BundleTests',
                         'test_specctl.TemporaryBundleTests.test_aide_exports_all_planned_non_authorizing',
                         'test_specctl.TemporaryBundleTests.test_aide_export_refuses_overwrite','-v'],
                        [sys.executable,'-B','spec/tools/specctl.py','manifest'],
                        [sys.executable,'-B','spec/tools/specctl.py','verify-manifest']):run(command)
    record['status']='pass'
finally:
    (HERE/'validation.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
