import hashlib
import json
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET

root = Path.cwd()
campaign = root / '.aide-local/exfat-tree-file-exact-39d514f1'
out = root / '.aide-local/native-delay-retest-39d514f1'
out.mkdir(exist_ok=False)
build = campaign / 'build'
source = campaign / 'source'
summary = json.loads((campaign / 'observation-summary.json').read_bytes())
failed = summary['native_failed']
assert len(failed) == 8
command = ['ctest', '--test-dir', str(build), '-C', 'Release', '--output-on-failure',
    '-R', '^(' + '|'.join(failed).replace('.', '\\.') + ')$', '--output-junit', str(out / 'native-junit.xml')]
started = time.monotonic()
with (out / 'native.log').open('wb') as log:
    p = subprocess.run(command, cwd=source, stdout=log, stderr=subprocess.STDOUT)
(out / 'commands.json').write_bytes(json.dumps(dict(command=command, cwd=str(source), exit_code=p.returncode,
    elapsed_seconds=round(time.monotonic() - started, 3), deadlines_changed=False), indent=2).encode() + b'\n')
cases = list(ET.parse(out / 'native-junit.xml').getroot().iter('testcase'))
assert len(cases) == 8
failures = [c.attrib['name'] for c in cases if c.find('failure') is not None or c.find('error') is not None]
inputs = json.loads((campaign / 'source-inputs.json').read_bytes())
assert all('sha256:' + hashlib.sha256((source / path).read_bytes()).hexdigest() == digest
    for path, digest in inputs.items())
status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=source)
assert not status.strip()
(out / 'summary.json').write_bytes(json.dumps(dict(status='pass' if not failures else 'fail',
    source_revision=summary['source_revision'], groups=8, failed=failures,
    inputs_unchanged=True, full_native_qualified=False, original_campaign_failed=True,
    original_cause_established=False, qualification=False, owner_accepted=False), indent=2).encode() + b'\n')
print('Original-artifact focused retest: exit ' + str(p.returncode), flush=True)
