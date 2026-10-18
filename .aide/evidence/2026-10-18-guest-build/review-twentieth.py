"""Verify the retained private Win32 checkpoint without extracting its payloads."""
import hashlib
import json
import lzma
import os
from pathlib import Path
import sys
import tarfile
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
def retain_error(kind, error, trace):
    (HERE/'twentieth-review-error.txt').write_text(''.join(traceback.format_exception(kind, error, trace)), encoding='utf-8', newline='\n')
sys.excepthook = retain_error
assert Path(os.environ['DISKED_WORK_ROOT']).is_dir()
names = [('result.json', 'twentieth-sparse-copy.json'),
         ('observations.tar.xz', 'twentieth-sparse-copy-observations.tar.xz'),
         ('cleanup.json', 'twentieth-sparse-copy-cleanup.json'),
         ('context.json', 'context-c667318e.json')]
for old, new in names:
    assert (HERE/old).is_file() != (HERE/new).is_file(), (old, new)
receipt_path = HERE/next(n for n in names[0] if (HERE/n).is_file())
archive_path = HERE/next(n for n in names[1] if (HERE/n).is_file())
cleanup_path = HERE/next(n for n in names[2] if (HERE/n).is_file())
receipt = json.loads(receipt_path.read_bytes())
proof = receipt['guest']['proof']
assert receipt['status'] == proof['status'] == 'pass'
assert receipt['exact_source']['revision'] == 'c667318e258db237b56f103343360d1457dcb2c7'
assert len(proof['tests']) == 18 and all(t['passed'] and t['exit_code'] == 0 for t in proof['tests'])
assert len(proof['header_artifacts']) == 12 and len(proof['executables']) == 9
assert not proof['full_x64_product_suite_run']
assert archive_path.stat().st_size == proof['archive_bytes'] <= 32*1024*1024
with archive_path.open('rb') as stream:
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == proof['archive_sha256']
wanted = {'junit/image.ntfs_worker.xml', 'fixture-symlink-preflight.log'}
found, seen, total = {}, set(), 0
with lzma.open(archive_path, 'rb') as decoded:
    with tarfile.open(fileobj=decoded, mode='r|') as archive:
        for entry in archive:
            assert entry.isfile() and entry.name not in seen
            expected = proof['archive_entries'][entry.name]
            assert entry.size == expected['bytes']
            with archive.extractfile(entry) as stream:
                if entry.name in wanted:
                    assert entry.size <= 1048576
                    found[entry.name] = stream.read()
                    digest = hashlib.sha256(found[entry.name]).hexdigest()
                else:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            assert digest == expected['sha256'], entry.name
            seen.add(entry.name)
            total += entry.size
assert seen == set(proof['archive_entries']) and set(found) == wanted
assert b'test_named_lease_acl_keeps_record_acl_and_actual_package_identity' in found['junit/image.ntfs_worker.xml']
assert b'40960000' in found['fixture-symlink-preflight.log']
cleanup = json.loads(cleanup_path.read_bytes())
assert len(cleanup) == 1
assert cleanup[0]['cleanup']['image_already_removed']
assert cleanup[0]['cleanup']['qualification_removed']
assert not cleanup[0]['cleanup']['unrelated_processes_killed']
for old, new in names:
    if (HERE/old).exists():
        (HERE/old).rename(HERE/new)
review = dict(status='pass', source_revision=proof['source_revision'],
    private_win32_groups=18, standalone_headers=12, executable_observations=9,
    verified_archive_entries=len(seen), original_entry_bytes=total,
    compressed_bytes=proof['archive_bytes'], archive_sha256=proof['archive_sha256'],
    peak_scratch_allocated_bytes=proof['peak_scratch_allocated_bytes'],
    lease_acl_method_observed=True, sparse_symlink_preflight_observed=True,
    owned_cleanup_verified=True, full_x64_product_suite_run=False,
    main_promoted=False, owner_accepted=False)
(HERE/'twentieth-review.json').write_text(json.dumps(review, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps(review))
