"""Bounded coordinator tests and retained evidence review; no product execution."""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
assert Path(os.environ['DISKED_WORK_ROOT']).is_dir()
paths=['tests/support/tempdir.py','tests/tools/test_fixture_temp.py',
       'tests/frontend/test_image_commands.py','tests/frontend/test_gpt_repair_command.py',
       'tests/images/test_parent_pins.py','tests/images/test_fat_allocation_window.py',
       'tests/images/test_ntfs_file.py','tests/images/test_ntfs_directory_file.py',
       'tests/images/test_fat_capture.py','tests/images/test_fat_allocation_scan.py',
       'tests/images/test_fat_auxiliary.py','tests/images/test_fat_namespace.py',
       'tests/images/test_fat_content_file.py','tests/images/test_fat_extraction.py',
       '.aide/evidence/2026-10-18-guest-build/build-driver.py',
       '.aide/evidence/2026-10-18-guest-build/review-failed-group.py']
record=dict(status='running',scope='Host coordinator unit tests, static fixture syntax, source inventory and stream verification of retained guest evidence. No product executable, media, guest setup or elevation.',
    source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
    input_hashes={p:'sha256:'+hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},commands=[])
commands=[([sys.executable,'-B','-m','unittest','discover','-s','tests/tools','-v'],180),
          ([sys.executable,'-B',str(HERE/'validate-retention.py')],60),
          ([sys.executable,'-B',str(HERE/'review-failed-group.py'),
            '--receipt','nineteenth-lease-repair.json',
            '--archive','nineteenth-lease-repair-observations.tar.xz',
            '--output','nineteenth-directory-review.json'],180),
          ([sys.executable,'-B','tools/check-source-map.py'],30)]
try:
    for p in paths:
        ast.parse((ROOT/p).read_text(encoding='utf-8'),filename=p)
    for command,deadline in commands:
        start=time.monotonic()
        result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=deadline)
        assert len(result.stdout)+len(result.stderr)<=262144
        record['commands'].append(dict(arguments=command,exit_code=result.returncode,
            seconds=time.monotonic()-start,stdout=result.stdout.decode(errors='replace'),
            stderr=result.stderr.decode(errors='replace')))
        if result.returncode:
            raise RuntimeError('Fixture preparation check failed')
    record['status']='pass'
except BaseException as error:
    record.update(status='fail',error=str(error))
    raise
finally:
    (HERE/'fixture-preparation-validation.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
