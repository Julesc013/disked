"""Independent raw correspondence, owned process identities and source-free frames."""
import argparse
import copy
import json
import subprocess
import time
from pathlib import Path
import unittest

import test_ntfs_worker as worker
import test_ntfs_file as held
import test_ntfs_directory_file as directory_file
from test_ntfs_membership_file import foundation
from test_ntfs_membership import complete as membership_complete
from ntfs_membership_fixture import MembershipVolume, filename, ref
from test_ntfs_capture import bytes_at

SOURCE_RECEIPTS=[]
RECEIPTS=[]
UNEXPECTED=[]
LAUNCH_RECORDS=[]


def run(row, fault=False):
    command=[str(worker.FAULT if fault else worker.PROBE)]
    data=held.canonical(row)+b'\n';started=time.monotonic()
    p=subprocess.run(command,input=data,capture_output=True,timeout=35)
    record=dict(command=command,input_sha256=held.digest(data),output_sha256=held.digest(p.stdout),
                stderr_sha256=held.digest(p.stderr),elapsed_seconds=time.monotonic()-started,
                exit_code=p.returncode,fault=fault)
    RECEIPTS.append(record)
    if p.returncode or p.stderr:
        UNEXPECTED.append(dict(record=record,request=row,stdout_hex=p.stdout.hex(),stderr_hex=p.stderr.hex()))
    assert p.returncode==0 and not p.stderr,(record,p.stderr[:3000])
    return json.loads(p.stdout)


class Tests(unittest.TestCase):
    setUp=worker.Tests.setUp
    tearDown=worker.Tests.tearDown
    retired=worker.Tests.retired

    def fixture(self, volume=None):
        volume,path=held.Tests.fixture(self,volume or MembershipVolume())
        return volume,path,dict(path=str(path),offset=volume.input['offset'],length=volume.input['length'],
            capture_epoch='77',directory=copy.deepcopy(volume.input['directory']),
            membership=copy.deepcopy(volume.input['membership']))

    def preserve(self,path,row,fault=False):
        before=held.file_digest(path),path.stat().st_size
        value=run(row,fault)
        after=held.file_digest(path),path.stat().st_size
        self.assertEqual(before,after)
        SOURCE_RECEIPTS.append(dict(before_sha256=before[0],after_sha256=after[0],bytes=before[1],
            input_sha256=held.digest(held.canonical(row)),output_sha256=held.digest(held.canonical(value))))
        return value

    def good(self,volume,path,row,mismatch=False,**extra):
        selected=dict(row,**extra);value=self.preserve(path,selected)
        if not value.get('has_snapshot'):
            UNEXPECTED.append(dict(request=selected,worker_output=value))
        self.assertTrue(value.get('has_snapshot'),value)
        self.retired(value);self.assertTrue(value['retained_unchanged'])
        result=value['snapshot'];capture=result['capture'];frame=value['frame'];context=value['context']
        membership_complete(result['observation'],volume)
        self.assertEqual(result['observation']['applicable'],not mismatch)
        self.assertEqual(result['observation']['diagnostic'],'ntfs_membership_name_mismatch' if mismatch else '')
        self.assertNotIn('binding_diagnostic',result['observation'])
        self.assertEqual(capture['observed_stable'],not mismatch)
        self.assertTrue(all(capture[n] for n in ('metadata_complete','metadata_equal','binding_checks_ok',
                                                'replay_equal','profile_selection_equal')))
        self.assertEqual(frame['schema'],'org.disked.ntfs-membership-region-frame/1')
        self.assertEqual(frame['input']['schema'],'org.disked.ntfs-membership-source-request/1')
        self.assertEqual(result['schema'],'org.disked.ntfs-membership-file-capture/1')
        self.assertEqual(frame['input']['target_limit'],selected['membership'].get('targets','64'))
        self.assertEqual(capture['domain']['target_limit'],frame['input']['target_limit'])
        self.assertEqual(capture['domain']['provider'],'ntfs-membership-file-prototype')
        self.assertEqual(capture['capture_domain'],held.digest(held.canonical(capture['domain'])))
        self.assertEqual(context['image_profile'],'ordinary-file-ntfs-membership')
        self.assertEqual(context['capture_epoch'],selected['capture_epoch'])
        self.assertEqual(context['code_sha256'],held.file_digest(worker.PROBE).removeprefix('sha256:'))
        self.assertEqual(context['frame_sha256'],held.digest(held.canonical(frame)))
        for frame_key,context_key in [('process_id','pid'),('process_created','created')]:
            self.assertEqual(frame[frame_key],context[context_key])
            self.assertEqual(context[context_key],value['independent_process'][context_key])
        self.assertTrue(value['independent_process']['in_job'])
        self.assertEqual([(int(r['offset']),int(r['requested'])) for r in frame['regions']],volume.initial_reads*2)
        for region,(at,size) in zip(frame['regions'],volume.initial_reads*2):
            self.assertEqual(bytes.fromhex(region['bytes']),bytes_at(volume.input,at,size))
            self.assertTrue(region['seek_attempted'] and region['read_attempted'])
        automatic30=volume.input['minor']=='0' and selected.get('profile','auto')=='auto'
        prefix=len(volume.bootstrap_reads) if automatic30 else 0
        for key in ('profile_prefix_validation_attempted','profile_prefix_validated',
                    'profile_prefix_boundary','profile_prefix_continued'):
            self.assertEqual(capture[key],automatic30)
        self.assertEqual(capture['profile_prefix_reused'],str(prefix))
        self.assertEqual(capture['profile_prefix_validation_calls'],str(prefix))
        self.assertEqual(capture['replay_calls'],str(len(frame['regions'])+2*prefix))
        self.assertFalse(result['authorizes_effects'] or result['product_dispatch_admitted'])
        self.assertFalse(capture['atomic_snapshot'])
        for part,cap in [(frame,8*1024*1024),(frame['input'],131072),(capture,65536),
                         (result['observation'],2*1024*1024)]:
            self.assertLessEqual(len(held.canonical(part)),cap)
        if len(LAUNCH_RECORDS)<4:LAUNCH_RECORDS.append(value)
        return value

    def test_owned_profiles_graphs_extensions_names_and_control_copy(self):
        for minor in (0,1):
            for kind in ('empty','leaf','single','siblings','deep','preallocated'):
                v,path,row=self.fixture(MembershipVolume(minor=minor,kind=kind))
                for profile in ('auto','3.'+str(minor)):self.good(v,path,row,profile=profile)
            for form in ('resident','nonresident'):
                v,path,row=self.fixture(MembershipVolume(minor=minor,list_form=form,
                    directory_list_form='nonresident',mft_closure=True,bitmap_form='nonresident',
                    fragmented_allocation=True,split_allocation=True))
                self.good(v,path,row)
            v,path,row=self.fixture(MembershipVolume(minor=minor,usa=42,number=17,sequence=65535))
            self.good(v,path,row,mutate_after_prepare=True)
        for raw in (b'\0\0',b'\x1b\0[\0m\0',b'\0\xd8\xff\xdc',b'\xff\xff'*255):
            v,path,row=self.fixture(MembershipVolume(kind='single',size=4096,name=raw))
            self.good(v,path,row)
        v,path,row=self.fixture(MembershipVolume())
        for cap in (1,64,256):self.good(v,path,row,membership=dict(targets=str(cap)))

    def test_original_instances_and_complete_mismatch_are_retained(self):
        for mode in ('identical','empty','parent','namespace','name'):
            v=MembershipVolume();values=copy.deepcopy(v.target_recipes[ref(14,9)]['values'])
            if mode=='identical':values += [values[0],values[0]]
            elif mode=='empty':values=[]
            else:values=[filename(b'X\0' if mode=='name' else raw[66:66+raw[64]*2],
                parent=ref(5,4) if mode=='parent' else v.reference,
                namespace=2 if mode=='namespace' else raw[65])[0] for raw in values]
            v.replace_target(values=values);v,path,row=self.fixture(v)
            self.good(v,path,row,mismatch=mode!='identical')

    def test_actual_native_offset_above4GiB(self):
        v,path,row=self.fixture(MembershipVolume(minor=0,offset=(1<<32)+173,list_form='nonresident'))
        self.good(v,path,row)

    def test_probe_prefix_and_foundations_match_independent_pure_reports(self):
        for minor in (0,1):
            v,path,row=self.fixture(MembershipVolume(minor=minor,list_form='nonresident'))
            for cap in (64,256):
                v.input['membership']['targets']=str(cap)
                out=self.good(v,path,row,membership=dict(targets=str(cap)))
                value=dict(result=out['snapshot']);capture=out['snapshot']['capture']
                probe=directory_file.pure_report(v,value,1)
                self.assertEqual(capture['profile_probe_sha256'],held.digest(held.canonical(probe)))
                self.assertEqual(out['snapshot']['observation'],directory_file.pure_report(v,value,minor))
                if minor==0:
                    prefix=directory_file.pure_report(v,value,0,
                        dict(fault=dict(mode='throw',call=str(len(v.bootstrap_reads)+1))))
                    self.assertEqual(capture['profile_prefix_validation_sha256'],held.digest(held.canonical(prefix)))
                    self.assertEqual(capture['profile_probe_foundation_sha256'],held.digest(held.canonical(foundation(probe))))
                    self.assertEqual(capture['profile_selected_foundation_sha256'],held.digest(held.canonical(foundation(prefix))))

    def test_source_free_parent_reconstruction_and_inert_preparation(self):
        for minor in (0,1):
            v,path,row=self.fixture(MembershipVolume(minor=minor,list_form='nonresident'))
            original=self.preserve(path,dict(row,mode='frame'))
            self.assertEqual(original['frame']['result'],original['verified'])
            frame=original['frame'];base=dict(row,expected_source=frame['result']['capture']['source_before'])
            path.unlink()
            self.assertTrue(run(dict(base,mode='construction'))['never_launched'])
            self.assertEqual(frame['result'],run(dict(base,mode='verify',replace=frame))['verified'])
            unavailable=run(base);self.retired(unavailable);self.assertFalse(unavailable['has_snapshot'])

    def test_strict_new_wire_fields_and_old_kind_isolation(self):
        v,path,row=self.fixture(MembershipVolume())
        original=self.preserve(path,dict(row,mode='frame'))['frame']
        for cap in ('0','257','4294967297','18446744073709551615','01','-1'):
            self.assertIn('error',self.preserve(path,dict(row,mode='construction',membership=dict(targets=cap))))
        wire=copy.deepcopy(original['input'])
        for change in ('missing','number','extra','old-schema'):
            value=copy.deepcopy(wire)
            if change=='missing':del value['target_limit']
            elif change=='number':value['target_limit']=64
            elif change=='extra':value['unknown']=True
            else:value['schema']='org.disked.ntfs-directory-source-request/1'
            self.assertIn('error',self.preserve(path,dict(row,mode='decode_input',replace_input=value)),change)
        for directory in (False,True):
            old=copy.deepcopy(row);del old['membership']
            if not directory:del old['directory']
            encoded=self.preserve(path,dict(old,mode='decode_input'))['input']
            self.assertNotIn('target_limit',encoded)
            for cap in ('0','1','256'):
                self.assertIn('error',self.preserve(path,dict(old,mode='construction',nonmember_target_limit=cap)))
            encoded['target_limit']='64'
            self.assertIn('error',self.preserve(path,dict(old,mode='decode_input',replace_input=encoded)))
        for fixture in (dict(capture_call='1'),dict(worker_fault='claims'),dict(capture_fault='error')):
            self.assertIn('error',self.preserve(path,dict(row,mode='construction',fixture=fixture)))

    def test_every_prefix_receipt_and_target_control_is_reconstructed(self):
        for minor in (0,1):
            v,path,row=self.fixture(MembershipVolume(minor=minor,list_form='nonresident'))
            frame=self.preserve(path,dict(row,mode='frame'))['frame']
            base=dict(row,mode='verify',expected_source=frame['result']['capture']['source_before'])
            fields=['profile_probe_response_count','profile_probe_sha256','profile_prefix_validation_attempted',
                'profile_prefix_validated','profile_prefix_boundary','profile_prefix_continued',
                'profile_prefix_validation_calls','profile_prefix_reused','profile_prefix_validation_sha256',
                'profile_probe_foundation_sha256','profile_selected_foundation_sha256','replay_calls','retained_replays']
            for key in fields:
                bad=copy.deepcopy(frame);c=bad['result']['capture'];old=c[key]
                c[key]=not old if isinstance(old,bool) else 'sha256:'+'0'*64 if old is None or old.startswith('sha256:') else str(int(old)+1)
                self.assertIn('error',self.preserve(path,dict(base,replace=bad)),(minor,key))
            for change in ('schema','source-schema','capture-schema','input-cap','domain-cap','coherent-cap',
                           'requested-cap','matches','name','claims','process','epoch'):
                bad=copy.deepcopy(frame);c=bad['result']['capture'];obs=bad['result']['observation']
                if change=='schema':bad['schema']='org.disked.ntfs-directory-region-frame/1'
                elif change=='source-schema':bad['input']['schema']='org.disked.ntfs-directory-source-request/1'
                elif change=='capture-schema':bad['result']['schema']='org.disked.ntfs-directory-file-capture/1'
                elif change=='input-cap':bad['input']['target_limit']='1'
                elif change in ('domain-cap','coherent-cap'):
                    c['domain']['target_limit']='1';c['capture_domain']=held.digest(held.canonical(c['domain']))
                    if change=='coherent-cap':obs['requested_target_limit']='1'
                elif change=='requested-cap':obs['requested_target_limit']='1'
                elif change=='matches':obs['membership']['edges'][0]['matching_instances']='999'
                elif change=='name':
                    name=obs['membership']['targets'][0]['inventory']['names'][0]
                    name['name_hex']='5800';name['name_sha256']=held.digest(b'X\0')
                elif change=='claims':obs['membership']['namespace_verified']=True
                elif change=='process':bad['process_id']='1'
                else:bad['capture_epoch']='1'
                self.assertIn('error',self.preserve(path,dict(base,replace=bad)),(minor,change))
            bad=copy.deepcopy(frame);c=bad['result']['capture'];n=int(c['profile_probe_response_count'])+1
            for key in ('profile_probe_response_count','profile_prefix_validation_calls','profile_prefix_reused'):c[key]=str(n)
            c['replay_calls']=str(len(frame['regions'])+2*n)
            self.assertIn('error',self.preserve(path,dict(base,replace=bad)))

    def test_each_native_response_provenance_and_order_is_bound(self):
        v,path,row=self.fixture(MembershipVolume(minor=0,list_form='nonresident'))
        original=self.preserve(path,dict(row,mode='frame'))['frame']
        base=dict(row,mode='verify',expected_source=original['result']['capture']['source_before'])
        for i in range(len(original['regions'])):
            for mode in ('alter','missing','extra','reorder','attempt'):
                if mode=='reorder' and i==0:continue
                bad=copy.deepcopy(original)
                if mode=='alter':bad['regions'][i]['bytes']='ff'+bad['regions'][i]['bytes'][2:]
                elif mode=='missing':bad['regions'].pop(i)
                elif mode=='extra':bad['regions'].insert(i,copy.deepcopy(bad['regions'][i]))
                elif mode=='attempt':bad['regions'][i]['read_attempted']=False
                else:bad['regions'][i-1],bad['regions'][i]=bad['regions'][i],bad['regions'][i-1]
                self.assertIn('error',self.preserve(path,dict(base,replace=bad)),(i,mode))

    def test_partial_source_faults_stay_inspectable_without_applicability(self):
        for minor in (0,1):
            v,path,row=self.fixture(MembershipVolume(minor=minor,list_form='nonresident'))
            for at in (1,len(v.bootstrap_reads)+1,len(v.initial_reads)*2):
                for fault in ('short','error','metadata','binding'):
                    out=self.preserve(path,dict(row,fixture=dict(capture_fault=fault,capture_call=str(at))),True)
                    self.retired(out)
                    if fault=='binding' and at==1:
                        self.assertFalse(out['has_snapshot'])
                        continue
                    self.assertTrue(out['has_snapshot'],(minor,at,fault,out))
                    self.assertFalse(out['snapshot']['observation']['applicable'])
            for n in (1,len(v.initial_reads)-1):
                out=self.preserve(path,dict(row,limits=dict(read_requests=str(n))));self.retired(out)
                self.assertTrue(out['has_snapshot']);self.assertFalse(out['snapshot']['observation']['applicable'])
        v=MembershipVolume();v.mutate_record(14,16,b'\x08\0');v,path,row=self.fixture(v)
        out=self.preserve(path,row);self.retired(out);self.assertTrue(out['has_snapshot'])
        self.assertEqual(out['snapshot']['observation']['diagnostic'],'ntfs_membership_target_record')

    def test_worker_forgery_and_replay_faults_never_admit_snapshot(self):
        v,path,row=self.fixture(MembershipVolume(minor=0,list_form='nonresident'))
        for fault in ('payload_changed','result_changed','receipt_changed','process_changed','domain_changed',
                      'row_changed','prefix_changed','profile_hash_changed','membership_changed','target_changed','claims'):
            out=self.preserve(path,dict(row,fixture=dict(worker_fault=fault)),True)
            self.retired(out);self.assertFalse(out['has_snapshot'],(fault,out))
        for fault in ('capture','worker','code','request','scope','host','observer','attempt','pid','created',
                      'shape','status','claims','schema','digest'):
            out=self.preserve(path,dict(row,fixture=dict(reply_fault=fault)),True)
            self.retired(out);self.assertFalse(out['has_snapshot'],(fault,out))
        for at in (1,len(v.bootstrap_reads)+1,len(v.bootstrap_reads)*2+1):
            for fault in ('replay_bytes','replay_offset'):
                out=self.preserve(path,dict(row,fixture=dict(capture_fault=fault,capture_call=str(at))),True)
                self.retired(out);self.assertFalse(out['has_snapshot'],(at,fault,out))

    def test_actual_worker_lifecycle_and_snapshot_exit_boundary(self):
        _,path,row=self.fixture(MembershipVolume(minor=0))
        for fault in ('before_spawn','after_spawn','after_spawn_alloc'):
            out=self.preserve(path,dict(row,fixture=dict(startup_fault=fault)),True)
            self.assertIn('startup_error',out);self.assertEqual(out['never_launched'],fault=='before_spawn')
            if fault!='before_spawn':self.retired(out)
        for fault in ('hang','late'):
            out=self.preserve(path,dict(row,mode='pending',fixture=dict(worker_fault=fault)),True)
            self.retired(out);self.assertFalse(out['has_snapshot'])
        for extra in (dict(cancel=True),dict(fixture=dict(worker_fault='exit'))):
            out=self.preserve(path,dict(row,**extra),bool(extra.get('fixture')))
            self.retired(out);self.assertFalse(out['has_snapshot'])
        out=self.preserve(path,dict(row,mode='publication-live',fixture=dict(reply_fault='hold')),True)
        self.retired(out);self.assertFalse(out['has_snapshot'])
        self.assertEqual(out['before']['diagnostic'],'ntfs_worker_exit_pending')
        for _ in range(3):
            out=self.preserve(path,dict(row,mode='retire-zero',fixture=dict(worker_fault='hang')),True)
            self.assertEqual(out['zero_retirement']['retired'],out['zero_retirement']['worker']['observation']=='exited')
            self.retired(out)

    def test_new_frame_component_bounds(self):
        _,path,row=self.fixture(MembershipVolume())
        original=self.preserve(path,dict(row,mode='frame'))['frame']
        base=dict(row,mode='verify',expected_source=original['result']['capture']['source_before'])
        for part,size in [('observation',2*1024*1024),('capture',65536)]:
            frame=copy.deepcopy(original);frame['result'][part]['overflow']='x'*size
            self.assertIn('error',self.preserve(path,dict(base,replace=frame)))
        frame=copy.deepcopy(original);frame['input']['overflow']='x'*131072
        self.assertIn('error',self.preserve(path,dict(base,replace=frame)))
        frame=copy.deepcopy(original);frame['regions']=[copy.deepcopy(frame['regions'][0]) for _ in range(513)]
        self.assertIn('error',self.preserve(path,dict(base,replace=frame)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('probe','fault','pure','output'):parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();worker.PROBE=args.probe.resolve();worker.FAULT=args.fault.resolve()
    directory_file.PURE=args.pure.resolve()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    summary=dict(status='pass' if result.wasSuccessful() else 'fail',methods=result.testsRun,cases=len(RECEIPTS),
        failures=len(result.failures),errors=len(result.errors),receipts=RECEIPTS,source_receipts=SOURCE_RECEIPTS,
        launch_records=LAUNCH_RECORDS,unexpected_outputs=UNEXPECTED,pure_receipts=directory_file.PURE_RECEIPTS,
        owner_accepted=False,full_0_1_0_complete=False)
    args.output.write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__=='__main__':main()
