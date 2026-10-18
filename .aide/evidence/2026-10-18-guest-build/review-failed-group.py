"""Read one retained failed group's diagnostics without extracting bulk output."""
import argparse
import hashlib
import json
import lzma
import os
from pathlib import Path
import tarfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
assert Path(os.environ['DISKED_WORK_ROOT']).is_dir()
parser=argparse.ArgumentParser()
parser.add_argument('--receipt',required=True)
parser.add_argument('--archive',required=True)
parser.add_argument('--output',required=True)
args=parser.parse_args()
for value in vars(args).values():
    assert Path(value).name==value
receipt = json.loads((HERE/args.receipt).read_bytes())
proof = receipt['guest']['proof']
archive_path = HERE/args.archive
assert archive_path.stat().st_size <= 32*1024*1024
with archive_path.open('rb') as compressed:
    assert hashlib.file_digest(compressed, 'sha256').hexdigest() == proof['archive_sha256']
group = 'image.ntfs_directory_file'
wanted = {'test-'+group+'.log', 'junit/'+group+'.xml', 'cases/ntfs-directory-file-cases.json'}
found = {}
seen=set()
with lzma.open(archive_path, 'rb') as decoded:
    with tarfile.open(fileobj=decoded, mode='r|') as archive:
        for entry in archive:
            assert entry.name not in seen and entry.isfile()
            expected = proof['archive_entries'][entry.name]
            assert entry.size==expected['bytes']
            with archive.extractfile(entry) as stream:
                if entry.name in wanted:
                    assert entry.size<=1048576
                    data=stream.read()
                    digest=hashlib.sha256(data).hexdigest()
                    found[entry.name]=data
                else:
                    digest=hashlib.file_digest(stream,'sha256').hexdigest()
            assert digest==expected['sha256']
            seen.add(entry.name)
assert seen==set(proof['archive_entries'])
assert set(found) == wanted
lines = found['test-'+group+'.log'].decode('utf-8', errors='replace').splitlines()
start = next(i for i, line in enumerate(lines) if line.startswith(('FAIL:', 'ERROR:')))
excerpt = '\n'.join(line[:2000] for line in lines[start:start+21])
assert len(excerpt.encode()) <= 32768
cases = json.loads(found['cases/ntfs-directory-file-cases.json'])
junit = ET.fromstring(found['junit/'+group+'.xml'])
result = dict(status='failure_reviewed', source_revision=receipt['exact_source']['revision'],
    group=group, archive_sha256=proof['archive_sha256'], excerpt=excerpt,
    method_count=cases['methods'], calls=len(cases['cases']) if isinstance(cases['cases'], list) else cases['cases'],
    failures=cases.get('failures'), errors=cases.get('errors'),
    junit_failure_count=len(junit.findall('.//failure')), verified_archive_entries=len(seen),
    full_native_suite_passed=False)
(HERE/args.output).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(result))
