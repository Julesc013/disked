"""Audit the retained incomplete focused repair attempt; never qualify it."""
import hashlib
import importlib.util
import json
import lzma
from pathlib import Path, PurePosixPath
import tarfile
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
DATA=HERE/'repair-focused'
definition=importlib.util.spec_from_file_location('native_receipts',HERE.parent/'2026-10-18-ordinary-worker/review-native.py')
reader=importlib.util.module_from_spec(definition);definition.loader.exec_module(reader)
check=reader.require
value=reader.load_receipt(DATA,'receipt');proof=value['guest']['proof']
groups={'frontend.fat_tree_sessions','frontend.gui_windows','image.fat_commands','image.fat_retention_commands'}
check(value['status']==proof['status']=='fail','Retained attempt must remain failed')
check(not proof['full_x64_product_suite_run'],'Focused evidence must not claim the complete gate')
check(proof['native_build_passed'] and len(proof['tests'])==4 and {t['name'] for t in proof['tests']}==groups,'Exact focused group set')
check({t['name'] for t in proof['tests'] if not t['passed']}=={'frontend.gui_windows'},'Exact focused failure')
check(all(t['exit_code']==0 for t in proof['tests'] if t['passed']),'Passing group exit status')
check(set(proof['executables'])=={'disked','disked_tree_test','disked_fat_test','fat_tree_extraction_worker_probe'},'Exact focused executable set')
archive=DATA/'retained.tar.xz'
check(archive.stat().st_size<=67108864,'Compressed artifact bound')
with archive.open('rb') as body:check(hashlib.file_digest(body,'sha256').hexdigest()==proof['archive_sha256'],'Archive identity')
selected={};inventory={};names=set();total=0
wanted={'entry-manifest.json'}|{'junit/'+name+'.xml' for name in groups}
with lzma.open(archive,'rb') as raw,tarfile.open(fileobj=raw,mode='r|') as stream:
    for member in stream:
        path=PurePosixPath(member.name)
        check(member.isfile() and not path.is_absolute() and '..' not in path.parts and member.name not in names,'Unique ordinary archive member')
        names.add(member.name);total+=member.size
        check(len(names)<=20001 and 0<=member.size<=67108864 and total<=2147483648,'Expansion bound')
        with stream.extractfile(member) as body:
            if member.name in wanted:
                check(member.size<=8388608,'Selected receipt bound');data=body.read(member.size+1)
                check(len(data)==member.size,'Selected receipt length');selected[member.name]=data
                digest=hashlib.sha256(data).hexdigest()
            else:digest=hashlib.file_digest(body,'sha256').hexdigest()
        if member.name!='entry-manifest.json':inventory[member.name]=dict(bytes=member.size,sha256=digest)
check(set(selected)==wanted,'Every original JUnit receipt present')
check(hashlib.sha256(selected['entry-manifest.json']).hexdigest()==proof['entry_manifest_sha256'],'Closed inventory identity')
check(json.loads(selected['entry-manifest.json'])==inventory,'Every member and hash match the closed inventory')
for test in proof['tests']:
    body=selected['junit/'+test['name']+'.xml']
    check(hashlib.sha256(body).hexdigest()==test['junit_receipt']['sha256'],'JUnit identity')
    check(b'<!DOCTYPE' not in body.upper() and b'<!ENTITY' not in body.upper(),'No XML entities')
    xml=ET.fromstring(body);cases=list(xml.iter('testcase'))
    check(len(cases)==1 and cases[0].get('name')==test['name'],'Exact JUnit case')
    check(not any(n.tag=='skipped' for n in xml.iter()) and xml.get('skipped')=='0','No skipped JUnit evidence')
    if test['name']=='frontend.gui_windows':
        check(xml.get('failures')=='1' and any(n.tag=='failure' for n in xml.iter()),'Failed GUI group retained')
        text=''.join(xml.itertext())
        check('Ran 8 tests' in text and 'FAILED (errors=1)' in text and 'FileNotFoundError' in text and 'test_unavailable_gui_dependency_is_named_and_headless_remains_static' in text,'Missing companion diagnosis')
    else:
        check(xml.get('failures')=='0' and not any(n.tag in ('failure','error') for n in xml.iter()),'Passing original group')
setup=value['guest']['setup'];cleanup=reader.load_receipt(DATA,'cleanup')
live=json.loads((DATA/'cleanup-live.json').read_bytes())
check(setup['image_removed'] and setup['actor_removed'] and setup['actor_profile_absent'],'Owned setup retirement')
check(len(cleanup)==1 and cleanup[0]['image_uuid']==setup['image_uuid'] and cleanup[0]['cleanup']['qualification_removed'],'Owned cleanup receipt')
check(live['actor_sid']==setup['actor_sid'] and not live['owned_processes'] and live['inaccessible_owner_queries']==0,'Fresh actor process observation')
check(all(live[k] for k in ('qualification_absent','scratch_absent','actor_absent','actor_directory_absent','actor_hive_absent','actor_profile_key_absent')),'Fresh retirement')
record=dict(status='verified_failed_attempt',scope='Incomplete focused composition: missing GUI companion executables; not a passing focused/full gate',
    source_revision=proof['source_revision'],groups=sorted(groups),groups_passed=3,
    missing_companions=['disked_provider_guard','disked_gui_unavailable'],gui_methods_passed=7,gui_methods_attempted=8,
    full_x64_gate_qualified=False,archive_sha256=proof['archive_sha256'],archive_bytes=archive.stat().st_size,
    archive_entries=len(names),original_bytes=total,owned_cleanup_verified=True,
    peak_scratch_allocated_bytes=proof['peak_scratch_allocated_bytes'],owner_accepted=False,release_qualified=False)
(DATA/'review.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(record))
