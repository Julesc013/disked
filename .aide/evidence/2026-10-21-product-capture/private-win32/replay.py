"""Review the bounded private Win32 run; never extract its sparse/raw payloads."""
import ast
import hashlib
import importlib.util
import json
import lzma
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
definition=importlib.util.spec_from_file_location('win32_receipts',ROOT/'.aide/evidence/2026-10-18-ordinary-worker/review-native.py')
reviewer=importlib.util.module_from_spec(definition);definition.loader.exec_module(reviewer)
check=reviewer.require
record=dict(status='running',scope='Private Win32 fixture only;not full Win32 product or historical Windows support',
            owner_accepted=False,release_qualified=False,reader_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
try:
    result=reviewer.load_receipt(HERE,'receipt');proof=result['guest']['proof'];revision=proof['source_revision']
    check(isinstance(revision,str) and re.fullmatch('[0-9a-f]{40}',revision),'Exact revision')
    check(result['status']==proof['status']=='pass' and result['host_exit_code']==0,'Native campaign failed')
    check(result['exact_source']['revision']==revision and not proof['full_x64_product_suite_run'],'Source/scope')
    recipe=subprocess.check_output(['git','show',revision+':tools/ntfs-win32-fixture.py'],cwd=ROOT,timeout=30)
    fixed_bytes=subprocess.check_output(['git','show',revision+':.aide/evidence/2026-10-18-guest-build/expected.json'],cwd=ROOT,timeout=30)
    fixed=json.loads(fixed_bytes)['fixed_group_cases']
    nodes=[n for n in ast.parse(recipe).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='TESTS' for t in n.targets)]
    targets=[n for n in ast.parse(recipe).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PROBES' for t in n.targets)]
    check(len(nodes)==len(targets)==1,'Frozen fixture inventory')
    wanted={'image.ntfs_'+name for name in ast.literal_eval(nodes[0].value)}
    wanted_targets=set(ast.literal_eval(targets[0].value))
    check(len(wanted)==18 and len(proof['tests'])==18 and {t['name'] for t in proof['tests']}==wanted,'Exact18-group set')
    check(all(t['passed'] is True and t['exit_code']==0 for t in proof['tests']),'Native test outcomes')
    check(len(proof['fixture']['tests'])==18 and set(proof['fixture']['tests'])==wanted and len(proof['header_artifacts'])==12 and len(wanted_targets)==9 and set(proof['executables'])==wanted_targets,'Fixture build inventory')
    check(len({h['path'] for h in proof['header_artifacts']})==12 and all(h['bytes']>0 and re.fullmatch('[0-9a-f]{64}',h['sha256']) for h in proof['header_artifacts']),'Distinct standalone header observations')
    check(all(e['pe_machine']=='0x14c' and e['bytes']>0 and re.fullmatch('[0-9a-f]{64}',e['sha256']) for e in proof['executables'].values()),'Win32 executable observations')
    check(proof['source_confinement']==dict(elevated=0,appcontainer=1,source_write_denied=True),'Actual worker confinement')
    for test in proof['tests']:
        summary=test['summary']
        count=summary.get('cases',summary.get('calls'))
        check(type(count) is int and count>0 and all(summary[k]==0 for k in ('failures','errors','unverified') if k in summary),'Native case summary')
        if test['name'] in fixed:check(summary.get('count',summary.get('cases'))==fixed[test['name']],'Frozen case inventory')
        methods={'image.ntfs_name_order_file':9,'image.ntfs_name_order_worker':10,'image.ntfs_upcase_file':8,'image.ntfs_upcase_worker':10}
        if test['name'] in methods:check(summary['methods']==methods[test['name']],'Frozen method inventory')
    archive=HERE/'retained.tar.xz';check(archive.stat().st_size==proof['archive_bytes']<=33554432,'Compressed archive bound')
    with archive.open('rb') as stream:check(hashlib.file_digest(stream,'sha256').hexdigest()==proof['archive_sha256'],'Archive identity')
    found={};seen=set();total=0;selected={'junit/image.ntfs_worker.xml','fixture-symlink-preflight.log'}
    with lzma.open(archive,'rb') as decoded,tarfile.open(fileobj=decoded,mode='r|') as stream:
        for entry in stream:
            path=PurePosixPath(entry.name)
            check(entry.isfile() and not path.is_absolute() and '..' not in path.parts and entry.name not in seen,'Archive member')
            check(len(seen)<20000 and 0<=entry.size<=67108864,'Archive member bound')
            expected=proof['archive_entries'][entry.name];check(entry.size==expected['bytes'],'Entry size')
            with stream.extractfile(entry) as body:
                if entry.name in selected:
                    check(entry.size<=1048576,'Selected observation bound');found[entry.name]=body.read();digest=hashlib.sha256(found[entry.name]).hexdigest()
                else:digest=hashlib.file_digest(body,'sha256').hexdigest()
            check(digest==expected['sha256'],'Entry hash: '+entry.name)
            seen.add(entry.name);total+=entry.size;check(total<=1073741824,'Aggregate replay bound')
    check(seen==set(proof['archive_entries']) and set(found)==selected,'Closed raw observation inventory')
    check(b'test_named_lease_acl_keeps_record_acl_and_actual_package_identity' in found['junit/image.ntfs_worker.xml'],'Actual lease ACL regression')
    check(b'40960000' in found['fixture-symlink-preflight.log'],'Sparse/symlink preflight')
    cleanup=reviewer.load_receipt(HERE,'cleanup');setup=result['guest']['setup']
    check(setup['image_removed'] is True and len(cleanup)==1 and cleanup[0]['image_uuid']==setup['image_uuid'],'Owned media identity/retirement')
    check(cleanup[0]['cleanup']['image_already_removed'] and cleanup[0]['cleanup']['qualification_removed'] and not cleanup[0]['cleanup']['unrelated_processes_killed'],'Owned cleanup')
    check(proof['peak_scratch_allocated_bytes']<=536870912,'Scratch allocation budget')
    record.update(status='pass',source_revision=revision,private_win32_groups=18,standalone_headers=12,executable_observations=9,
                  fixture_recipe_sha256=hashlib.sha256(recipe).hexdigest(),expectations_sha256=hashlib.sha256(fixed_bytes).hexdigest(),verified_archive_entries=len(seen),original_entry_bytes=total,
                  archive_bytes=archive.stat().st_size,archive_sha256=proof['archive_sha256'],
                  peak_scratch_allocated_bytes=proof['peak_scratch_allocated_bytes'],owned_cleanup_verified=True)
except BaseException as error:
    record.update(status='fail',error=repr(error));raise
finally:
    (HERE/'review.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(record))
