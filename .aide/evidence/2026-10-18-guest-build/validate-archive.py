"""Exercise streaming observation retention without running native/guest code."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent
definition = importlib.util.spec_from_file_location('build_driver', HERE / 'build-driver.py')
module = importlib.util.module_from_spec(definition)
definition.loader.exec_module(module)
work = Path(os.environ['DISKED_WORK_ROOT'])
source = work / 'case.json'
source.write_bytes(b'{"case":"retained","bytes":[1,2,3]}\n')
archive = module.Observations(work / 'observations.tar.xz')
archive.writestr('compiler.log', b'actual-log\r\n')
archive.write(source, 'case.json')
archive.close_verify()
with tarfile.open(work / 'observations.tar.xz', 'r:xz') as reader:
    assert reader.extractfile('case.json').read() == source.read_bytes()
    assert reader.extractfile('compiler.log').read() == b'actual-log\r\n'
record = {'status': 'pass', 'scope': 'Bounded host retention only',
          'entries': archive.entries, 'archive_bytes': (work / 'observations.tar.xz').stat().st_size,
          'driver_sha256': hashlib.sha256((HERE / 'build-driver.py').read_bytes()).hexdigest()}
(HERE / 'archive-validation.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps({'status': 'pass', 'entries': len(archive.entries)}))
