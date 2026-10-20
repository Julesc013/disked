"""Verify the focused product archive in memory; never extract build/test trees."""
import hashlib
import json
import lzma
from pathlib import Path,PurePosixPath
import struct
import tarfile

HERE=Path(__file__).resolve().parent
def check(value,why):
    if not value:raise ValueError(why)
def sha(value):return hashlib.sha256(value).hexdigest()
def receipt(name):
    packed=(HERE/name).read_bytes();check(len(packed)<=1048576,'receipt compressed bound')
    decoder=lzma.LZMADecompressor(memlimit=8388608);body=decoder.decompress(packed,max_length=8388609)
    check(decoder.eof and not decoder.unused_data and len(body)<=8388608,'receipt body bound')
    return json.loads(body)

result=receipt('receipt.json.xz');proof=result['guest']['proof'];expected=json.loads((HERE/'expected.json').read_bytes())
check(result['status']==proof['status']=='pass','campaign failed')
check(proof['native_build_passed'] and proof['registered_native_groups']==180 and not proof['full_x64_product_suite_run'],'focused build inventory')
check({r['name'] for r in proof['tests']}=={'disked.acceptance','frontend.gui_capture'} and all(r['passed'] for r in proof['tests']),'focused group inventory')
check(all(proof[k] for k in ('all_owned_processes_retired','crypto_device_retired','null_device_retired','fixture_dacl_coordinator_retired')),'guest retirement')
setup=result['guest']['setup'];check(all(setup[k] for k in ('image_removed','actor_removed','actor_profile_absent')),'guest owned cleanup')
check(proof['owned_window_scope_controls']==dict(outside_job=True,different_image=True,image_write_open_refused=True,image_delete_open_refused=True),'scope controls')
archive=HERE/'retained.tar.xz';check(archive.stat().st_size<=33554432 and sha(archive.read_bytes())==proof['archive_sha256'],'archive hash/bound')
files={};total=0
with tarfile.open(archive,'r:xz') as stream:
    for member in stream:
        path=PurePosixPath(member.name)
        check(member.isfile() and not path.is_absolute() and '..' not in path.parts and member.name not in files and len(files)<20001 and member.size<=16777216,'archive member')
        total+=member.size;check(total<=67108864,'archive total bound')
        body=stream.extractfile(member).read(member.size+1);check(len(body)==member.size,'archive truncated');files[member.name]=body
manifest=json.loads(files['entry-manifest.json']);check(set(files)==set(manifest)|{'entry-manifest.json'} and len(files)==proof['archive_entries'],'closed archive inventory')
check(sha(files['entry-manifest.json'])==proof['entry_manifest_sha256'],'entry manifest hash')
for name,row in manifest.items():check(row==dict(bytes=len(files[name]),sha256=sha(files[name])),'entry bytes/hash: '+name)
summary=json.loads(files['groups/frontend.gui_capture/gui-capture-cases.json'])
check(summary['passed'] and not summary['source_dirty'] and summary['source_revision']==proof['source_revision'],'source/case summary')
product=proof['executables']['disked']['sha256'].removeprefix('sha256:');check(summary['executable_sha256'].removeprefix('sha256:')==product,'product image')
captures=summary['captures'];rows=proof['owned_window_captures']
check(len(captures)==len(rows)==6 and {r['name'] for r in captures}==set(expected['cases']),'six case set')
by_id={r['id']:r for r in rows};check(len(by_id)==6,'distinct requests')
for case in captures:
    geometry=case['geometry'];record=geometry['capture_receipt'];row=by_id[record['id']]
    check(all(row[k]==v for k,v in record.items()),'case/retired receipt binding')
    check(row['method']==geometry['capture_method']==expected['method'] and row['capture_id']==row['id'],'capture method/case')
    check(row['membership_jobs_retired'] and row['output_sections_retired'] and not row['supervisor_handle_exposed'] and row['membership_job_query_access']==4 and row['output_section_access']==2,'capability retirement')
    check(row['image_pin_held'] and row['desktop_acl_validated'] and row['image_sha256']==product,'image/desktop scope')
    request=bytes.fromhex(row['request_hex']);check(len(request)==640 and sha(request)==row['request_sha256'],'request packet hash')
    check(request[88:104].hex()==row['id'] and request[72:88].hex()==row['image_file_id'] and struct.unpack_from('<Q',request,64)[0]==int(row['image_file_volume']),'packet object identities')
    check(struct.unpack_from('<QII',request,32)==(row['window'],row['pid'],row['thread']) and list(struct.unpack_from('<iiii',request,104))==row['frame_bounds'],'packet process/frame')
    check(row['client_box']==geometry['client_box']==[0,0,row['width'],row['height']] and row['frame_bounds']==geometry['frame_bounds'] and row['sha256']==geometry['pixels_sha256'],'client coordinates/hash')
    body=files['groups/frontend.gui_capture/'+case['name']+'.png'];check(sha(body)==case['sha256'].removeprefix('sha256:') and body[:8]==b'\x89PNG\r\n\x1a\n','PNG bytes')
    check(struct.unpack('>II',body[16:24])==(row['width'],row['height']),'PNG geometry')
report=dict(status='pass',source_revision=proof['source_revision'],native_groups=2,registered_native_groups=180,full_native_suite=False,product_sha256=product,captures=6,archive_bytes=archive.stat().st_size,archive_entries=len(files),archive_content_bytes=total,pngs={r['name']:r['sha256'] for r in captures},visual_review='separate actual image inspection required',owner_accepted=False,release_qualified=False)
(HERE/'replay.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(report))
