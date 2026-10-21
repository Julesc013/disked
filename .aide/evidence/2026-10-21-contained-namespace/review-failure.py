"""Verify the failed full run's closed evidence; never qualify its native gate."""
import hashlib
import importlib.util
import json
import lzma
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
DATA=HERE/'full-native'
spec=importlib.util.spec_from_file_location('receipts',HERE.parent/'2026-10-18-ordinary-worker/review-native.py')
reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
check=reader.require
result=reader.load_receipt(DATA,'receipt');proof=result['guest']['proof']
revision=proof['source_revision']
expected=json.loads(subprocess.check_output(['git','show',revision+':.aide/evidence/2026-10-18-ordinary-worker/native-x64-expectations.json'],cwd=ROOT))
failed={'frontend.fat_tree_sessions','frontend.gui_windows','image.fat_commands','image.fat_retention_commands'}
check(result['status']==proof['status']=='fail' and not proof['full_x64_product_suite_run'],'Failed native status')
tests=proof['tests'];check(len(tests)==180 and {t['name'] for t in tests}==set(expected['groups']),'Complete attempted group set')
check({t['name'] for t in tests if not t['passed']}==failed==set(proof['failed_native_groups']),'Exact failed groups')
check(proof['native_build_passed'] and len(proof['standalone_headers'])==69 and len(proof['executables'])==14,'Build/header/executable inventory')
archive=DATA/'retained.tar.xz';check(archive.stat().st_size<=67108864,'Compressed archive bound')
with archive.open('rb') as f:check(hashlib.file_digest(f,'sha256').hexdigest()==proof['archive_sha256'],'Archive hash')
wanted={'entry-manifest.json'}|{'junit/'+name+'.xml' for name in failed}
names=set();inventory={};selected={};total=0
with lzma.open(archive,'rb') as raw,tarfile.open(fileobj=raw,mode='r|') as stream:
    for member in stream:
        path=PurePosixPath(member.name)
        check(member.isfile() and not path.is_absolute() and '..' not in path.parts and member.name not in names,'Ordinary unique archive member')
        names.add(member.name);total+=member.size
        check(len(names)<=20001 and 0<=member.size<=67108864 and total<=2147483648,'Expansion bound')
        with stream.extractfile(member) as body:
            if member.name in wanted:
                check(member.size<=8388608,'Selected member bound');data=body.read(member.size+1);check(len(data)==member.size,'Selected length')
                selected[member.name]=data;digest=hashlib.sha256(data).hexdigest()
            else:digest=hashlib.file_digest(body,'sha256').hexdigest()
        if member.name!='entry-manifest.json':inventory[member.name]=dict(bytes=member.size,sha256=digest)
check(set(selected)==wanted,'Failure receipts present')
check(hashlib.sha256(selected['entry-manifest.json']).hexdigest()==proof['entry_manifest_sha256'],'Manifest identity')
check(json.loads(selected['entry-manifest.json'])==inventory,'Closed manifest and every member hash')
failures=[]
for name in sorted(failed):
    body=selected['junit/'+name+'.xml'];test=next(t for t in tests if t['name']==name)
    check(hashlib.sha256(body).hexdigest()==test['junit_receipt']['sha256'],'JUnit binding')
    xml=ET.fromstring(body);check(xml.get('failures')=='1' and xml.get('skipped')=='0','Actual failed group')
    failures.append(dict(group=name,diagnostic=''.join(xml.itertext()).strip()[-10000:]))
setup=result['guest']['setup'];cleanup=reader.load_receipt(DATA,'cleanup');live=json.loads((DATA/'cleanup-live.json').read_bytes())
check(setup['image_removed'] and setup['actor_removed'] and setup['actor_profile_absent'],'Setup retirement')
check(len(cleanup)==1 and cleanup[0]['image_uuid']==setup['image_uuid'] and cleanup[0]['cleanup']['qualification_removed'],'Cleanup ownership')
check(not live['owned_processes'] and live['inaccessible_owner_queries']==0 and live['actor_sid']==setup['actor_sid'],'Fresh process observation')
check(all(live[k] for k in ('qualification_absent','scratch_absent','actor_absent','actor_directory_absent','actor_hive_absent','actor_profile_key_absent')),'Fresh owned retirement')
record=dict(status='verified_failed_attempt',native_gate_passed=False,source_revision=revision,groups_attempted=180,groups_passed=176,
    failures=failures,standalone_headers=69,executable_observations=14,archive_bytes=archive.stat().st_size,
    archive_entries=len(names),original_bytes=total,archive_sha256=proof['archive_sha256'],
    peak_scratch_allocated_bytes=proof['peak_scratch_allocated_bytes'],host_workspace_peak_bytes=87702468,
    owned_cleanup_verified=True,owner_accepted=False,public_provider_admitted=False,release_qualified=False)
(DATA/'failure-review.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:v for k,v in record.items() if k!='failures'}))
