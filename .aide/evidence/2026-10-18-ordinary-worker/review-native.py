"""Review retained W105 bytes without extracting a build tree or rerunning tests."""
import hashlib
import json
import re
import struct
from pathlib import Path, PureWindowsPath
import subprocess
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
record = dict(status='running', scope=__doc__, owner_accepted=False, release_qualified=False)


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


COOPERATIVE='owned-ui-thread-cooperative-client-tree-transport/1'


def validate_window_capture_receipts(proof, summary, inventory, *, method='owned-window-dc'):
    """Check receipt consistency; this establishes no pixel-origin qualification."""
    require(summary['passed'] is True and not summary['source_dirty'], 'GUI capture summary failed/dirty')
    require(summary['source_revision']==proof['source_revision'], 'GUI capture source revision')
    product=proof['executables']['disked']['sha256'].removeprefix('sha256:')
    require(summary['executable_sha256'].removeprefix('sha256:')==product, 'GUI capture product identity')
    require(proof['owned_window_scope_controls']==dict(outside_job=True,different_image=True,
            image_write_open_refused=True,image_delete_open_refused=True), 'GUI capture scope controls')
    rows=proof['owned_window_captures'];require(6<=len(rows)<=32, 'GUI coordinator capture count')
    identities=set();nonces=set()
    for row in rows:
        require(row['method']==method and row['desktop_acl_validated'] is True, 'GUI coordinator method/ACL')
        require(row['image_sha256']==product, 'GUI coordinator executable differs')
        require(row['image_pin_held'] is True and re.fullmatch(r'[0-9a-f]{32}',row['image_file_id']) and
                re.fullmatch(r'[0-9]{1,20}',row['image_file_volume']), 'GUI coordinator executable not pinned')
        require(re.fullmatch(r'[0-9a-f]{32}',row['id']) and row['id'] not in identities, 'GUI coordinator duplicate/invalid request')
        require(re.fullmatch(r'[0-9a-f]{32}',row['nonce']), 'GUI coordinator nonce')
        require(re.fullmatch(r'DiskEdTest-[0-9a-f]{32}',row['desktop']), 'GUI coordinator desktop')
        require(type(row['pid']) is int and 0<row['pid']<2**32 and type(row['window']) is int and 0<row['window']<2**64, 'GUI coordinator process/window')
        require(all(type(row[k]) is int and 0<row[k]<=4096 for k in ('width','height')) and
                row['width']*row['height']<=4194304 and row['bytes']==row['width']*row['height']*4, 'GUI coordinator dimensions')
        require(re.fullmatch(r'[0-9a-f]{64}',row['sha256']), 'GUI coordinator pixel hash')
        identities.add(row['id']);nonces.add(row['nonce'])
    require(len(nonces)==1, 'GUI coordinator job nonce differs')
    require(len({(row['image_file_volume'],row['image_file_id']) for row in rows})==1, 'GUI coordinator image object differs')
    wanted={mode+'-'+str(index) for mode in ('inventory','review','minimum') for index in range(2)}
    captures=summary['captures']
    require(len(captures)==6 and {row['name'] for row in captures}==wanted, 'GUI capture case inventory')
    unused=list(rows)
    for capture in captures:
        geometry=capture['geometry'];require(geometry['capture_method']==method, 'GUI capture producer method')
        if method==COOPERATIVE:
            supplied=geometry.get('capture_receipt');require(isinstance(supplied,dict) and 'id' in supplied,'GUI case receipt missing')
            matching=next((i for i,row in enumerate(unused) if row['id']==supplied['id']),None)
        else:
            matching=next((i for i,row in enumerate(unused) if row['sha256']==geometry['pixels_sha256'] and
                           (row['width'],row['height'])==(geometry['width'],geometry['height'])),None)
        require(matching is not None, 'GUI PNG metadata lacks a distinct coordinator receipt')
        row=unused.pop(matching)
        require(row['sha256']==geometry['pixels_sha256'] and (row['width'],row['height'])==(geometry['width'],geometry['height']),'GUI case pixel metadata')
        if method==COOPERATIVE:require(all(k in row and row[k]==v for k,v in supplied.items()),'GUI case/coordinator receipt differs')
        filename=PureWindowsPath(capture['path']).name
        require(filename==capture['name']+'.png', 'GUI PNG filename differs from its case')
        name='groups/frontend.gui_capture/'+filename
        require(name in inventory and inventory[name]['sha256']==capture['sha256'].removeprefix('sha256:'), 'GUI PNG missing/changed')
    return dict(captures_with_consistent_receipts=6,coordinator_attempts=len(rows),nonqualifying_attempts=len(unused),
                png_hashes_verified=True,pixel_metadata_bound_to_distinct_coordinator_receipts=True)


def review_window_captures(proof, summary, inventory, *, visual_review=None):
    methods={item['geometry']['capture_method'] for item in summary['captures']}
    if methods!={COOPERATIVE}:
        validate_window_capture_receipts(proof, summary, inventory)
        raise ValueError('owned-window-dc pixel origin invalidated by visual review; consistent receipts do not qualify the capture')
    result=validate_window_capture_receipts(proof,summary,inventory,method=COOPERATIVE)
    rows=proof['owned_window_captures'];require(len(rows)==6,'Cooperative capture count')
    nonces=set();packets={}
    try:
        for row in rows:
            require(row['capture_id']==row['id'] and row['membership_job_query_access']==4 and row['output_section_access']==2 and
                    row['supervisor_handle_exposed'] is False and row['membership_jobs_retired'] is True and row['output_sections_retired'] is True,'Cooperative capability/retirement')
            packet=bytes.fromhex(row['request_hex']);reply=bytes.fromhex(row['reply_header_hex'])
            require(len(packet)==640 and len(reply)==124 and packet[:8]==b'DECAPR1\0' and reply[:8]==b'DECAPS1\0' and
                    hashlib.sha256(packet).hexdigest()==row['request_sha256'],'Cooperative packet identity')
            nonce,=struct.unpack_from('<Q',packet,8);sequence,width,height,units=struct.unpack_from('<IIII',packet,16)
            require(all(type(row[k]) is int for k in ('thread','sequence','receiver_sequence','descendants','gdi_before','gdi_after')) and
                    0<row['thread']<2**32,'Cooperative integer domains')
            require(nonce&0xffffffff and nonce>>32 and 1<=sequence<=8 and sequence==row['sequence']==row['receiver_sequence'] and
                    (width,height)==(row['width'],row['height']) and 0<units<=255,'Cooperative sequence/geometry')
            require(packet[120:120+2*units].decode('utf-16le')=='WinSta0\\'+row['desktop'] and not any(packet[120+2*units:]),'Cooperative desktop')
            require(struct.unpack_from('<QII',packet,32)==(row['window'],row['pid'],row['thread']) and
                    struct.unpack_from('<Q',packet,64)[0]==int(row['image_file_volume']) and packet[72:88].hex()==row['image_file_id'] and
                    packet[88:104].hex()==row['id']==row['case_id'],'Cooperative process/image/case')
            frame=list(struct.unpack_from('<iiii',packet,104))
            require(all(type(v) is int for v in row['frame_bounds']) and frame==row['frame_bounds']==row['window_rect'] and
                    frame[2]>frame[0] and frame[3]>frame[1] and row['client_box']==[0,0,width,height],'Cooperative client/frame coordinates')
            for out,source,length in ((8,8,20),(32,32,16),(48,64,8),(56,72,32),(104,104,16)):
                require(reply[out:out+length]==packet[source:source+length],'Cooperative reply binding')
            descendants,before,after,format_=struct.unpack_from('<IIII',reply,88)
            require(struct.unpack_from('<I',reply,28)[0]==width*height*4==row['bytes'] and struct.unpack_from('<I',reply,120)[0]==4096+row['bytes'] and
                    descendants==row['descendants']<=64 and before==after==row['gdi_before']==row['gdi_after'] and format_==1,'Cooperative reply publication/GDI')
            job,section=struct.unpack_from('<QQ',packet,48);require(job and section,'Cooperative transferred handles')
            nonces.add(nonce);packets[row['id']]=(row,job,section)
        roots=set()
        for mode in ('inventory','review','minimum'):
            pair=[]
            for index in range(2):
                case=next(c for c in summary['captures'] if c['name']==mode+'-'+str(index));geometry=case['geometry']
                row,job,section=packets[geometry['capture_receipt']['id']]
                require(geometry['client_box']==row['client_box'] and geometry['frame_bounds']==row['frame_bounds'] and row['sequence']==index+1,'Cooperative case coordinates/sequence')
                pair.append((row['pid'],row['window'],row['desktop'],job,section))
            require(pair[0][:4]==pair[1][:4] and pair[0][4]!=pair[1][4],'Cooperative repeated-case lifetime')
            roots.add(pair[0][:3])
        require(len(nonces)==1 and len(roots)==3,'Cooperative run/instance identities')
    except (KeyError,TypeError,UnicodeError,struct.error) as error:
        raise ValueError('Malformed cooperative capture receipt') from error
    result.update(method=COOPERATIVE,client_coordinates_verified=True,private_cooperative_receipts_validated=True,actual_images_reviewed=False,text_recognition_qualified=False,accessibility_qualified=False)
    if visual_review is not None:
        require(visual_review['status']=='pass' and visual_review['source_revision']==proof['source_revision'] and
                visual_review['product_sha256'].removeprefix('sha256:')==proof['executables']['disked']['sha256'].removeprefix('sha256:') and
                visual_review['pngs']=={c['name']:c['sha256'] for c in summary['captures']},'Actual image review differs from this build/capture set')
        result['actual_images_reviewed']=True
    return result


def main():
    result = json.loads((HERE / 'result.json').read_bytes())
    proof = result['guest']['proof']
    revision = proof['source_revision']
    record['source_revision'] = revision
    def git_bytes(path):
        return subprocess.check_output(['git', 'show', revision + ':' + path], cwd=ROOT, timeout=30)
    fixed = json.loads(git_bytes('.aide/evidence/2026-10-18-guest-build/expected.json'))
    current = json.loads(git_bytes('.aide/evidence/2026-10-18-ordinary-worker/native-x64-expectations.json'))
    needed = {'groups/' + group + '/' + group.replace('image.', '').replace('_', '-') + '-cases.json'
              for group in fixed['fixed_group_cases']}
    needed.update('groups/'+name+'/'+wanted['summary'] for name,wanted in current['invocation_method_coverage'].items())
    needed.add('groups/frontend.gui_capture/gui-capture-cases.json')
    for group, stem in [('portable.ntfs_upcase', 'ntfs-upcase'),
                        ('image.ntfs_upcase_commands', 'ntfs-upcase-command'),
                        ('image.ntfs_name_order_commands', 'ntfs-name-order-command'),
                        *[('image.ntfs_' + family + '_' + mode, 'ntfs-' + family.replace('_', '-') + '-' + mode)
                          for family in ('name_order', 'upcase') for mode in ('file', 'worker')]]:
        needed.add('groups/' + group + '/' + stem + '-cases.json')
    require(result['status'] == proof['status'] == 'pass', 'Campaign did not pass')
    require(proof['full_x64_product_suite_run'], 'Full native gate did not pass')
    require(len(proof['tests']) == len(current['groups']) == 180 and all(t['passed'] for t in proof['tests']), 'Incomplete group inventory')
    require(sorted(t['name'] for t in proof['tests']) == current['groups'], 'Native group membership differs from frozen inputs')
    for name, wanted in current['invocation_method_coverage'].items():
        row=next(t for t in proof['tests'] if t['name']==name);observed=row['invocation_methods']
        require(observed['methods']==wanted['methods'] and observed['tests_run']==len(wanted['methods']) and observed['skipped']==0 and observed['passed'], 'Invocation method coverage')
        require(row['execution_profile']==('appcontainer' if wanted['partition']=='shells' else 'ordinary'), 'Invocation execution profile')
    require(len(proof['standalone_headers']) == current['standalone_headers'] == 69 and len(proof['executables']) == 14, 'Build inventory')
    require(all(proof[key] for key in ('all_owned_processes_retired', 'crypto_device_retired', 'null_device_retired')), 'Retirement')
    require(proof['native_token_identity']['integrity_sid'] == 'S-1-16-8192', 'Native integrity')
    handoff = {Path(row['path']).stem: row for row in proof['artifact_handoff']}
    for name, artifact in proof['executables'].items():
        row = handoff[name]
        require(row['sha256'] == artifact['sha256'] and row['bytes_unchanged'] and row['dacl_owner_group_unchanged'], 'Artifact handoff identity')
        require(row['after_label'] == 'S:AI(ML;;NW;;;ME)', 'Artifact handoff label')
    setup = result['guest']['setup']
    require(setup['image_removed'] and setup['actor_removed'] and setup['actor_profile_absent'], 'Guest cleanup')
    cleanup = json.loads((HERE / 'cleanup.json').read_bytes())
    require(len(cleanup) == 1 and cleanup[0]['image_uuid'] == setup['image_uuid'], 'Cleanup identity')
    require(cleanup[0]['cleanup']['qualification_removed'] and cleanup[0]['cleanup']['image_already_removed'], 'Owned output cleanup')
    archive = HERE / 'retained.tar.xz'
    require(hashlib.sha256(archive.read_bytes()).hexdigest() == proof['archive_sha256'], 'Archive hash')
    names, summaries, inventory = set(), {}, {}
    manifest = None
    raw_bytes = 0
    # LZMAFile bounds decompressor output; tarfile's streaming decompressor can
    # repeatedly copy a huge zero-filled buffer for these compact evidence files.
    with tarfile.open(archive, 'r:xz') as stream:
        for member in stream:
            require(member.isfile() and member.name not in names, 'Non-file/duplicate archive member')
            require(not member.name.startswith('/') and '..' not in Path(member.name).parts, 'Archive path')
            names.add(member.name)
            require(len(names) <= 20001 and member.size <= 64 * 1024 * 1024, 'Archive inventory bounds')
            selected = member.name in needed or member.name == 'entry-manifest.json'
            require(not selected or member.size <= 16 * 1024 * 1024, 'Selected summary memory bound')
            handle = stream.extractfile(member)
            value = bytearray() if selected else None
            sha = hashlib.sha256()
            size = 0
            while block := handle.read(1024 * 1024):
                sha.update(block)
                size += len(block)
                raw_bytes += len(block)
                require(raw_bytes <= 2 * 1024 * 1024 * 1024, 'Review decompression bound')
                if selected:
                    value.extend(block)
            require(size == member.size, 'Truncated member')
            if member.name == 'entry-manifest.json':
                require(sha.hexdigest() == proof['entry_manifest_sha256'], 'Entry-manifest identity')
                manifest = json.loads(value)
            else:
                inventory[member.name] = dict(bytes=size, sha256=sha.hexdigest())
                if selected:
                    summaries[member.name] = json.loads(value)
    require(manifest == inventory, 'Exact archive membership/hashes')
    visual=json.loads((HERE/'visual-review.json').read_bytes()) if (HERE/'visual-review.json').exists() else None
    record['gui_capture']=review_window_captures(proof,summaries['groups/frontend.gui_capture/gui-capture-cases.json'],inventory,visual_review=visual)
    require(record['gui_capture']['actual_images_reviewed'],'Actual retained GUI images still require review')
    for name,wanted in current['invocation_method_coverage'].items():
        observed=next(t['invocation_methods'] for t in proof['tests'] if t['name']==name)
        require(summaries['groups/'+name+'/'+wanted['summary']]==observed, 'Raw invocation summary differs from campaign receipt')
    record.update(archive_entries=len(names), uncompressed_bytes=raw_bytes, archive_sha256=proof['archive_sha256'])

    def expected(folder, name):
        return json.loads(git_bytes('.aide/evidence/2026-10-17-' + folder + '/' + name))

    def report(group, stem):
        key = 'groups/' + group + '/' + stem + '-cases.json'
        require(key in summaries, 'Missing detailed report: ' + key)
        value = summaries[key]
        require(value.get('status', 'pass') == 'pass' and not value.get('unverified'), 'Detailed failure: ' + key)
        require(not value.get('failures') and not value.get('errors'), 'Detailed errors: ' + key)
        for receipt in value.get('source_receipts', []):
            require(receipt['before_sha256'] == receipt['after_sha256'], 'Source changed: ' + key)
            if 'before_bytes' in receipt:
                require(receipt['before_bytes'] == receipt['after_bytes'], 'Source length changed: ' + key)
        return value

    def raw_receipts(group, value):
        require(len(value['receipts']) == value['calls'], 'Raw call inventory: ' + group)
        for call in value['receipts']:
            require(not call['timed_out'] and call['exit_code'] == call.get('expected_exit_code', 0), 'Raw call outcome')
            require(call['process_id'] > 0 and call['process_created'] > 0, 'Raw process identity')
            for kind in ('input', 'output', 'stderr'):
                name = Path(call['raw_' + kind]).name
                keys = [key for key in ('cases/' + name, 'groups/' + group + '/' + name) if key in inventory]
                require(len(keys) == 1, 'Missing/ambiguous raw call: ' + name)
                require(inventory[keys[0]]['sha256'] == call[kind + '_sha256'].removeprefix('sha256:'), 'Raw call hash')

    record['fixed_group_cases'] = {}
    for group, count in fixed['fixed_group_cases'].items():
        stem = group.replace('image.', '').replace('_', '-')
        value = report(group, stem)
        actual = value.get('count', value.get('cases'))
        require((len(actual) if isinstance(actual, list) else actual) == count, 'Fixed case count: ' + group)
        record['fixed_group_cases'][group] = count
    held = report('image.ntfs_file', 'ntfs-file')
    require(held['case_counts'] == fixed['file_method_cases'], 'Original file method matrix')
    require(len(held['path_binding']) == 1 and len(held['sparse_fixtures']) == 2, 'Binding/high-offset inventory')
    binding = held['path_binding'][0]
    require(binding['expected'] == [True, True, True, False, False, False], 'Binding row expectations')
    require(binding['source_before'] == binding['source_after'], 'Binding source changed')
    for group in ('image.ntfs_file', 'image.ntfs_directory_file'):
        value = report(group, group.replace('image.', '').replace('_', '-'))
        symlinks = value['prepared_symlinks']
        require(len(symlinks) == 1, 'Prepared symlink inventory')
        for row in symlinks:
            require(row['source_sha256'] == row['target_sha256'], 'Symlink fixture bytes')
            require(0 <= row['allocated_bytes'] <= 16777216 and 0 < row['copied_nonzero_block_bytes'] <= 16777216, 'Symlink fixture allocation')

    order = report('image.ntfs_name_order', 'ntfs-name-order')
    oracle = expected('ntfs-name-order', 'expected-after-fixture-review.json')
    require(order['count'] == oracle['count'] == 172, 'Pure name-order count')
    require(all(order[k] == oracle[k] for k in ('recipe_sha256', 'expected_cases_sha256')), 'Pure name-order identities')
    require(len(order['cases']) == 172 and all(c['passed'] for c in order['cases']), 'Pure name-order cases')
    record['name_order_cases'] = 172
    old = expected('ntfs-name-order-command', 'expected-after-binding-review.json')
    record['native_name_order'] = {}
    for mode, methods, calls in [('file', 9, 330), ('worker', 10, 363)]:
        group = 'image.ntfs_name_order_' + mode
        value = report(group, 'ntfs-name-order-' + mode)
        require(value['methods'] == methods and value['calls'] == calls, 'Name-order native inventory')
        recipe = 'tests/images/test_ntfs_name_order_' + mode + '.py'
        require(value['recipe_sha256'] == digest(git_bytes(recipe)), 'Current native recipe identity')
        require(value['helper_sha256'] == old['recipes']['tests/images/ntfs_name_order_native_expectations.py'], 'Independent native helper')
        require(value['source_receipts'], 'Missing native source receipts')
        raw_receipts(group, value)
        record['native_name_order'][mode] = dict(methods=methods, calls=calls, recipe_sha256=value['recipe_sha256'])
    public = report('image.ntfs_name_order_commands', 'ntfs-name-order-command')
    require(public['passed'] and public['families'] == old['families'] and public['layouts_tested'] == old['layouts'], 'Public fixed layouts/families')
    require(public['recipe_sha256'] == digest(git_bytes('tests/frontend/test_ntfs_name_order_commands.py')), 'Current command recipe')
    require(public['helper_sha256'] == old['recipes']['tests/frontend/ntfs_name_order_command_expectations.py'], 'Independent command helper')
    require(public['source_receipts'], 'Missing public source receipts')
    raw_receipts('image.ntfs_name_order_commands', public)
    record['public_name_order'] = dict(layouts=len(public['layouts_tested']), families=len(public['families']), calls=public['calls'])

    upcase = report('portable.ntfs_upcase', 'ntfs-upcase')
    old_upcase = expected('ntfs-upcase', 'expected-before-implementation.json')
    require(upcase['tables'] == old_upcase['tables'] and upcase['mapping_units'] == 327680, 'Uppercase table corpus')
    require(upcase['recipe_sha256'] == old_upcase['recipe_sha256'] and upcase['comparison_cases'] == old_upcase['comparison_cases'], 'Uppercase corpus identities')
    capture = report('image.ntfs_upcase_capture', 'ntfs-upcase-capture')
    capture_expected = expected('ntfs-upcase-capture', 'expected-after-binding-review.json')
    require(all(capture[k] == capture_expected[k] for k in ('recipe_sha256', 'expected_cases_sha256')), 'Table capture identities')
    require(len(capture['cases']) == 158 and all(c['passed'] for c in capture['cases']), 'Table capture cases')
    for mode, methods in [('file', 8), ('worker', 10)]:
        value = report('image.ntfs_upcase_' + mode, 'ntfs-upcase-' + mode)
        require(value['methods'] == methods and value['source_receipts'], 'Table native methods/receipts')
        require(value['recipe_sha256'] == digest(git_bytes('tests/images/test_ntfs_upcase_' + mode + '.py')), 'Current table native recipe')
    commands = report('image.ntfs_upcase_commands', 'ntfs-upcase-command')
    require(commands['passed'] and commands['cases'] == 119, 'Table public cases')
    require(commands['recipe_sha256'] == digest(git_bytes('tests/frontend/test_ntfs_upcase_commands.py')), 'Current table command recipe')
    record['upcase'] = dict(mapping_units=327680, capture_cases=158, public_cases=119)
    record['status'] = 'pass'


if __name__=='__main__':
    try:
        main()
    except BaseException as error:
        record.update(status='fail', error=repr(error))
        raise
    finally:
        (HERE / 'native-detail-review.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8', newline='\n')
