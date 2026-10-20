"""Bounded host replay of actual owned-client control evidence; no native run."""
import copy
import hashlib
import importlib.util
import io
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import struct
import sys
import tarfile
import zlib

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
if '--tree' in sys.argv:HERE=HERE.parent/'2026-10-21-cooperative-tree'
TRANSPORT='--transport' in sys.argv
if TRANSPORT:HERE=Path(__file__).resolve().parent.parent/'2026-10-21-capture-transport'


def check(value,reason):
    if not value:raise ValueError(reason)


def sha(body):return hashlib.sha256(body).hexdigest()


def stored_stdout(item,files):
    body=files[item['stdout']['path']];encoding=item.get('stdout_encoding','raw')
    check(encoding in ('raw','xz'),'stdout_encoding')
    if encoding=='xz':
        check(len(body)<=262144,'stdout_compressed_bound')
        decoder=lzma.LZMADecompressor(format=lzma.FORMAT_XZ,memlimit=8388608)
        body=decoder.decompress(body,max_length=262145)
        check(decoder.eof and not decoder.unused_data and len(body)<=262144,'stdout_decoded_bound')
    return body


def decode(path,limit):
    packed=path.read_bytes();check(len(packed)<=1048576,'compressed_bound')
    decoder=lzma.LZMADecompressor(format=lzma.FORMAT_XZ,memlimit=8*1024*1024)
    raw=decoder.decompress(packed,max_length=limit+1)
    check(len(raw)<=limit and decoder.eof and not decoder.unused_data,'decompression_bound')
    return raw


def recipe(challenge,phase):
    # Reconstruct directly from the frozen recipe, not the renderer or its
    # capture primitive. No expected output is derived from observed pixels.
    colors=[hashlib.sha256(b'DiskEd pixel-origin/1\0'+challenge+bytes([phase,tile])).digest()[:3] for tile in range(16)]
    return b''.join(b''.join(colors[(y//24)*4+x//60] for x in range(240)) for y in range(96))


def png_rgb(body):
    check(body[:8]==b'\x89PNG\r\n\x1a\n' and len(body)<=4096,'png_signature')
    pos=8;chunks=[];data=b''
    while pos<len(body):
        size=struct.unpack_from('>I',body,pos)[0];check(size<=4096 and pos+12+size<=len(body),'png_bound')
        kind=body[pos+4:pos+8];payload=body[pos+8:pos+8+size]
        check(zlib.crc32(kind+payload)==struct.unpack_from('>I',body,pos+8+size)[0],'png_crc')
        chunks.append(kind)
        if kind==b'IHDR':check(payload==struct.pack('>IIBBBBB',240,96,8,2,0,0,0),'png_geometry')
        elif kind==b'IDAT':data+=payload
        else:check(kind==b'IEND' and size==0,'png_chunk')
        pos+=12+size
    check(chunks==[b'IHDR',b'IDAT',b'IEND'],'png_chunk_set')
    decoder=zlib.decompressobj();raw=decoder.decompress(data,69217)
    check(len(raw)==69216 and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,'png_pixels')
    check(all(raw[y*721]==0 for y in range(96)),'png_filter')
    return b''.join(raw[y*721+1:(y+1)*721] for y in range(96))


def audit(files,receipt,expected,verifier):
    proof=receipt['guest']['proof'];report=proof['cooperative_capture'];calls=proof['port_observations']
    inventory=report['archive']['entries']
    check(set(files)=={v['path'] for v in inventory} and len(files)==len(inventory),'archive_entry_set')
    for row in inventory:
        body=files[row['path']];check(len(body)==row['bytes'] and sha(body)==row['sha256'],'entry_hash')
    check(json.loads(files['control.json'])=={k:v for k,v in report.items() if k!='archive'},'report_binding')
    check(receipt['status']=='pass' and receipt['host_exit_code']==0 and proof['status']=='pass' and report['status']=='pass','outcome')
    check(not receipt['host_test_media_mounted'] and not receipt['native_product_tests_run'] and not report['product_capture_admitted'],'scope')
    check(proof['all_owned_processes_retired'] and proof['crypto_device_retired'] and proof['source_unchanged'] and
          report['source_unchanged'] and proof['stdio_residuals']==0,'retirement')
    count=11+len(expected['control_modes'])+(3 if 'tree_requirements' in expected else 0)+(1 if 'capture_transport' in expected else 0)
    check(len(calls)==count and len(proof['controls'])==8 and report['port_observations']==calls,'execution_set')
    for call in calls:
        check(call['terminal'] and call['temporary_files_removed'] and call['job_retirement']['active_processes']==0,'call_retirement')
    for job in proof['job_limits']:
        check(job==dict(flags='0x2208',job_commit_bytes=268435456,process_limit=8),'job_limits')
    primitive=proof['primitive_proof'];payload=primitive['payload']
    check(primitive['status']=='pass' and primitive['cap_mib']==32 and primitive['all_owned_processes_retired'] and
          primitive['held_files_released'] and primitive['outside_sentinel_preserved'] and primitive['source_preserved'],'primitive_proof')
    check(payload['allocation_error']==112 and payload['failed_write_bytes']==0 and
          payload['space_before']==payload['space_after_removal'] and not payload['canary_inherited'] and
          all(v['denied'] for v in payload['outside']) and payload['descendant']['outside']['denied'],'capacity_and_confinement')
    check(len(report['query_jobs'])==2*len(expected['control_modes']),'membership_job_set')
    for i,job in enumerate(report['query_jobs']):
        check(job['anonymous'] and job['actor_access']=='JOB_OBJECT_QUERY only' and
              job['job_commit_bytes']==268435456 and job['process_limit']==8,'query_job')
        if i%2:check(job['retirement']['active_processes']==0,'wrong_job_retirement')
        elif i==6:check(job['supervisor_handle_closed_without_termination'] is True,'handle_loss_retirement')
        else:check(job['supervisor_retirement']['active_processes']==0,'supervisor_retirement')
    challenge=bytes.fromhex(report['challenge']);wanted=[recipe(challenge,p) for p in (0,1)]
    check(len(challenge)==16 and [sha(v) for v in wanted]==report['expected_rgb_sha256'],'fixed_expectations')
    check([v['mode'] for v in report['modes']]==expected['control_modes'],'mode_set')
    if 'tree_requirements' in expected:
        lazy=report['lazy_import_control'];check(lazy['status']=='pass' and lazy['user32_gdi32_static_imports'] is False,'lazy_result')
        check([v['label'] for v in lazy['commands']]==['compile','imports','run'],'lazy_calls')
        for item in lazy['commands']:
            call=calls[item['call_index']-1];check(call['outcome']==item['outcome']=='exited' and call['exit_code']==item['exit_code']==0,'lazy_execution')
            for name in ('stdout','stderr'):check(sha(files[item['raw'][name]['path']])==call['stream_sha256'][name],'lazy_stream_binding')
            if item['label']=='imports':check(b'user32.dll' not in files[item['raw']['stdout']['path']].lower() and b'gdi32.dll' not in files[item['raw']['stdout']['path']].lower(),'lazy_imports')
            if item['label']=='run':check(files[item['raw']['stdout']['path']]==b'capture-lazy-startup-ok\r\n' and not files[item['raw']['stderr']['path']],'lazy_no_gui_initialization')
    if 'capture_transport' in expected:
        item=report['product_gui_compile'];call=calls[item['call_index']-1]
        check(item['outcome']==call['outcome']=='exited' and item['exit_code']==call['exit_code']==0 and '/c' in call['argv'],'product_gui_compile')
        for name in ('stdout','stderr'):check(sha(files[item['raw'][name]['path']])==call['stream_sha256'][name],'gui_compile_stream')
    for item in report['modes']:
        mode=item['mode'];call=calls[item['call_index']-1];request=files[item['request']['path']];value=json.loads(request)
        check(item['outcome']==call['outcome'] and item['exit_code']==call['exit_code'] and
              item['elapsed_seconds']==call['elapsed_seconds'],'mode_call')
        check(sha(request)==call['stdin_sha256'] and len(request)==call['stdin_bytes'] and
              value['challenge']==report['challenge'] and value['nonce']==report['nonce'] and
              value['volume']==report['image_file_identity']['volume'] and value['file_id']==report['image_file_identity']['identity'],'request_binding')
        check(set(value)=={'challenge','nonce','volume','file_id','desktop','job_handle','wrong_job_handle'} and
              value['job_handle'].isdecimal() and value['wrong_job_handle'].isdecimal() and value['job_handle']!=value['wrong_job_handle'],'job_transport')
        check(item['transfer']==dict(process_id=call['process_id'],access=4,inheritable=False,count=2,supervisor_exposed=False) and
              call['launch']['pre_resume_hook_completed'] and call['launch']['allowed_inherited_handles']==3,'capability_handoff')
        check(item['owned_job_handles_closed'] is True and call['timeout']==3 and call['output_limit']==262144,'mode_bounds')
        stderr=files[item['stderr']['path']];check(sha(stderr)==call['stream_sha256']['stderr'],'stderr_binding')
        if mode in ('normal','blank_oracle_rejection','tree','background'):
            raw=stored_stdout(item,files);check(sha(raw)==call['stream_sha256']['stdout'] and len(raw)==call['produced_bytes']['stdout'],'stdout_binding')
            frame,pixels=verifier.parse_frame(raw,process_id=call['process_id'],nonce=int(report['nonce']),actor_sid=primitive['actor']['sid'],tree=mode in ('tree','background'))
            check(frame==item['frame'] and not stderr and item['pixels_retained'],'frame_binding')
            if mode in ('normal','tree','background'):
                observed=verifier.verify_pixels(pixels,wanted)
                check([sha(v) for v in observed]==item['rgb_sha256'] and item['stale_phase_rejected'],'pixel_binding')
                for phase in (0,1):check(png_rgb(files[(mode+'-' if mode in ('tree','background') else '')+'phase-'+str(phase)+'.png'])==observed[phase],'png_raw_binding')
                try:verifier.verify_pixels([pixels[0],pixels[0]],wanted)
                except ValueError as error:check(str(error)=='pixel_origin','stale_rejection_reason')
                else:raise ValueError('stale_accepted')
            else:
                check(all(v==bytes(92160) for v in pixels) and item['blank_surface_rejected'],'blank_binding')
                try:verifier.verify_pixels(pixels,wanted)
                except ValueError as error:check(str(error)=='pixel_origin','blank_rejection_reason')
                else:raise ValueError('blank_accepted')
        elif mode in ('receiver','receiver_hang'):
            protocol_spec=importlib.util.spec_from_file_location('replay_capture_wire',ROOT/'tests/support/capture_transport.py')
            protocol=importlib.util.module_from_spec(protocol_spec);protocol_spec.loader.exec_module(protocol)
            ipc=item['transport'];ready=ipc['ready'];facts=expected['capture_transport'];raw=files[item['stdout']['path']]
            check(sha(raw)==call['stream_sha256']['stdout'] and len(raw)==call['produced_bytes']['stdout'],'receiver_stdout')
            lines=[json.loads(line) for line in raw.splitlines()];check(len(lines)==2 and lines[0]==ready,'receiver_lines')
            check(ready['schema']=='org.disked.capture-receiver-ready/1' and ready['pid']==str(call['process_id']) and
                  ready['nonce']==report['nonce'] and int(ready['thread'])==ipc['actual_thread_id'] and ipc['actual_process_id']==call['process_id'],'receiver_identity')
            check(ready['guards']==[dict(name=name,refused=True,output_unchanged=True,render_called=False,borrowed_handles_open=True) for name in facts['guard_cases']],'receiver_guards')
            check(ipc['status']=='pass' and ipc['desktop_acl_validated'] and ipc['image_path_matched'] and ipc['job_membership_verified'] and
                  ipc['actual_user_sid']==primitive['actor']['sid'] and ipc['local_views_and_handles_retired_after_quiescence'],'receiver_admission')
            check(not stderr and len(ipc['requests'])==(2 if mode=='receiver' else 1),'receiver_request_set')
            ids=[]
            for i,delivery in enumerate(ipc['requests']):
                packet=bytes.fromhex(delivery['request_hex']);check(len(packet)==640 and sha(packet)==delivery['request_sha256'],'wire_request')
                check(delivery['sequence']==i+1 and delivery['section_access']==2 and delivery['inheritable'] is False,'wire_capability')
                ids.append(packet[88:104])
                check(struct.unpack_from('<Q',packet,8)[0]==int(report['nonce']) and struct.unpack_from('<I',packet,16)[0]==i+1 and
                      struct.unpack_from('<Q',packet,32)[0]==int(ready['window']) and struct.unpack_from('<II',packet,40)==(call['process_id'],ipc['actual_thread_id']) and
                      struct.unpack_from('<Q',packet,48)[0]==int(value['job_handle']) and packet[72:88].hex()==value['file_id'],'wire_scope')
                if mode=='receiver':
                    check(delivery['send_completed'] and delivery['reply_result']==1,'receiver_ack')
                    frame=item['transport_frames'][i];metadata,pixels=protocol.decode_reply(files[frame['raw']['path']],packet)
                    check(metadata==frame['metadata'] and metadata['descendants']==2,'receiver_frame_binding')
                    rgb=bytearray(69120);rgb[0::3]=pixels[2::4];rgb[1::3]=pixels[1::4];rgb[2::3]=pixels[0::4]
                    check(bytes(rgb)==wanted[i] and png_rgb(files['receiver-phase-'+str(i)+'.png'])==bytes(rgb),'receiver_pixel_origin')
                else:check(not delivery['send_completed'] and delivery['reply_result']==0 and ipc['sender_timeout_without_publication'],'receiver_timeout')
            check(len(set(ids))==len(ids) and all(any(v) for v in ids),'receiver_case_ids')
            if mode=='receiver':
                check(call['outcome']=='exited' and call['exit_code']==0 and item['pixels_retained'] and lines[1]==dict(schema='org.disked.capture-receiver-done/1',pid=str(call['process_id']),sequence='2',attempts='2'),'receiver_completion')
            else:check(call['outcome']=='timeout' and call['elapsed_seconds']>=3 and not item['pixels_retained'] and
                       lines[1]==dict(schema='org.disked.cooperative-capture-ready/1',pid=str(call['process_id']),nonce=report['nonce'],holding_job_query=True),'receiver_unresolved_retirement')
        elif mode in ('hung_paint_timeout','controller_handle_loss'):
            ready=item['ready'];check(ready==dict(schema='org.disked.cooperative-capture-ready/1',pid=str(call['process_id']),nonce=report['nonce'],holding_job_query=True),'ready_binding')
            check(not stderr and not item['pixels_retained'],'hung_no_pixels')
            if mode=='hung_paint_timeout':check(call['outcome']=='timeout' and call['elapsed_seconds']>=3,'paint_deadline')
            else:check(call['outcome']=='exited' and call['elapsed_seconds']<3 and item['controller_handle_loss']==dict(ready=ready),'guard_handle_loss')
        else:check(call['outcome']=='exited' and call['exit_code']==2 and call['produced_bytes']['stdout']==0 and stderr==b'invalid_control_mode\r\n','invalid_mode')
    return dict(modes=len(expected['control_modes']),negative_controls=11,tree_negative_controls=4 if 'tree_requirements' in expected else 0,
                raw_io_controls=8,native_calls=len(calls),archive_entries=len(files),uncompressed_bytes=sum(map(len,files.values())),rgb_pixels_per_phase=23040)


def main():
    check(bool(os.environ.get('DISKED_WORK_ROOT')),'managed_runner_required')
    receipt=json.loads(decode(HERE/'result.json.xz',1048576));proof=receipt['guest']['proof'];report=proof['cooperative_capture']
    archive=HERE/'observations.tar.xz';check(sha(archive.read_bytes())==report['archive']['sha256']==proof['archive_sha256'],'archive_hash')
    files={}
    with tarfile.open(fileobj=io.BytesIO(decode(archive,2097152)),mode='r:') as stream:
        for member in stream:
            path=PurePosixPath(member.name)
            check(len(files)<64 and member.isfile() and member.size<=262144 and len(path.parts)==1 and not path.is_absolute() and member.name not in files,'archive_member')
            files[member.name]=stream.extractfile(member).read(262145)
    spec=importlib.util.spec_from_file_location('cooperative_frame_replay',ROOT/'tests/support/cooperative_capture.py')
    verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier)
    expected=json.loads((HERE/'expected.json').read_bytes())
    if TRANSPORT:
        transport=expected;expected=json.loads((HERE.parent/'2026-10-21-cooperative-tree/expected.json').read_bytes());expected['capture_transport']=transport;expected['control_modes']+=['receiver','receiver_hang']
    summary=audit(files,receipt,expected,verifier)
    rejected=[]
    for name in ('altered_raw','missing_frame','false_report'):
        altered=dict(files);other=copy.deepcopy(receipt)
        if name=='altered_raw':altered['normal.stdout']=altered['normal.stdout'][:-1]+bytes([altered['normal.stdout'][-1]^1])
        elif name=='missing_frame':del altered['normal.stdout']
        else:
            control=json.loads(altered['control.json']);control['modes'][0]['transfer']['access']=8
            other['guest']['proof']['cooperative_capture']['modes'][0]['transfer']['access']=8
            altered['control.json']=(json.dumps(control,indent=2)+'\n').encode()
            for row in other['guest']['proof']['cooperative_capture']['archive']['entries']:
                if row['path']=='control.json':row.update(bytes=len(altered['control.json']),sha256=sha(altered['control.json']))
        try:audit(altered,other,expected,verifier)
        except ValueError:rejected.append(name)
        else:raise ValueError('corruption_accepted:'+name)
    setup=receipt['guest']['setup'];cleanup=json.loads((HERE/'cleanup.json').read_bytes())
    check(all(setup[key] for key in ('image_removed','actor_removed','actor_profile_absent','backing_acl_unchanged')) and
          cleanup[0]['cleanup']['qualification_removed'] and cleanup[0]['cleanup']['image_already_removed'] and
          not cleanup[0]['cleanup']['unrelated_processes_killed'],'owned_cleanup')
    reviewed=dict(status='pass',scope=__doc__,summary=summary,negative_replays=rejected,
        archive_sha256=sha(archive.read_bytes()),archive_bytes=archive.stat().st_size,receipt_sha256=sha((HERE/'result.json.xz').read_bytes()),
        compiler_sha256=proof['compiler_sha256'],linker_sha256=proof['linker_sha256'],owned_cleanup_verified=True,
        host_backing_logical_length_delta_bytes=receipt['host_backing_end_bytes']-receipt['host_backing_start_bytes'],allocated_backing_delta='not_measured',
        guest_free_c_bytes=receipt['guest']['free_c_bytes'],product_capture_admitted=False,full_native_qualification=False)
    if '--no-write' not in sys.argv:(HERE/'replay.json').write_text(json.dumps(reviewed,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(reviewed))


if __name__=='__main__':main()
