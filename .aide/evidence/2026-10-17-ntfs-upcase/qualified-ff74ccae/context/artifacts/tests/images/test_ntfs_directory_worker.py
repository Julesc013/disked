"""Owned directory workers and independently checked retained-frame relationships."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import unittest

import test_ntfs_worker as worker
import test_ntfs_file as held
from test_ntfs_directory import good as directory_good
from test_ntfs_directory import cases as directory_cases
from ntfs_directory_fixture import DirectoryVolume,ref

SOURCE_RECEIPTS=[]
LAUNCH_RECORDS=[]


class Tests(unittest.TestCase):
    setUp=worker.Tests.setUp
    tearDown=worker.Tests.tearDown
    retired=worker.Tests.retired

    def fixture(self, volume=None):
        volume=volume or DirectoryVolume(offset=173)
        volume,path=held.Tests.fixture(self,volume)
        selection=copy.deepcopy(volume.input['directory'])
        if volume.number!=5:selection.setdefault('reference',str(volume.reference))
        row=dict(path=str(path),offset=volume.input['offset'],length=volume.input['length'],
                 capture_epoch='77',directory=selection)
        return volume,path,row

    def preserve(self,path,row,fault=False):
        before=held.file_digest(path),path.stat().st_size
        out=worker.run(row,fault)
        after=held.file_digest(path),path.stat().st_size
        self.assertEqual(after,before)
        SOURCE_RECEIPTS.append(dict(before_sha256=before[0],after_sha256=after[0],bytes=before[1],
            input_sha256=held.digest(held.canonical(row)),output_sha256=held.digest(held.canonical(out))))
        return out

    def good(self,v,path,row,**extra):
        request=dict(row,**extra)
        out=self.preserve(path,request)
        self.retired(out)
        self.assertTrue(out['has_snapshot'] and out['retained_unchanged'],out)
        result=out['snapshot'];frame=out['frame'];context=out['context']
        directory_good(result['observation'],v)
        self.assertEqual(frame['schema'],'org.disked.ntfs-directory-region-frame/1')
        self.assertEqual(frame['input']['schema'],'org.disked.ntfs-directory-source-request/1')
        self.assertEqual(context['image_profile'],'ordinary-file-ntfs-directory')
        self.assertEqual(context['capture_epoch'],request['capture_epoch'])
        self.assertEqual(context['frame_sha256'],held.digest(held.canonical(frame)))
        executable=worker.PROBE
        # The shared host uses bare code hashes; frame/data digests are tagged.
        self.assertRegex(context['code_sha256'],r'^[0-9a-f]{64}$')
        self.assertEqual(context['code_sha256'],held.file_digest(executable).removeprefix('sha256:'))
        self.assertEqual(frame['process_id'],context['pid'])
        self.assertEqual(frame['process_created'],context['created'])
        self.assertEqual(context['pid'],out['independent_process']['pid'])
        self.assertEqual(context['created'],out['independent_process']['created'])
        self.assertTrue(out['independent_process']['in_job'])
        self.assertEqual([(int(r['offset']),int(r['requested'])) for r in frame['regions']],v.initial_reads*2)
        capture=result['capture']
        self.assertTrue(capture['profile_selection_equal'] and capture['replay_equal'] and capture['observed_stable'])
        automatic30=v.input['minor']=='0' and request.get('profile','auto')=='auto'
        n=len(v.bootstrap_reads) if automatic30 else 0
        self.assertEqual(capture['profile_prefix_validation_attempted'],automatic30)
        self.assertEqual(capture['profile_prefix_validated'],automatic30)
        self.assertEqual(capture['profile_prefix_reused'],str(n))
        self.assertEqual(capture['replay_calls'],str(len(v.initial_reads)*2+n*2))
        self.assertEqual(capture['capture_domain'],held.digest(held.canonical(capture['domain'])))
        self.assertEqual(capture['domain']['directory_reference'],request['directory'].get('reference','0'))
        self.assertFalse(result['authorizes_effects'] or result['product_dispatch_admitted'])
        self.assertLessEqual(len(held.canonical(frame)),8*1024*1024)
        self.assertLessEqual(len(held.canonical(frame['input'])),131072)
        self.assertLessEqual(len(held.canonical(result['capture'])),65536)
        self.assertLessEqual(len(held.canonical(result['observation'])),2*1024*1024)
        if len(LAUNCH_RECORDS)<4:LAUNCH_RECORDS.append(out)
        return out

    def test_owned_profiles_layouts_and_immutable_request(self):
        for minor in (0,1):
            for kind in ('leaf','empty','siblings','deep'):
                v,path,row=self.fixture(DirectoryVolume(kind=kind,minor=minor,offset=173))
                for profile in ('auto','3.'+str(minor)):
                    self.good(v,path,row,profile=profile)
        for options in [dict(minor=0,usa=42,kind='deep'),dict(cluster=512,index=512,size=512),
                        dict(cluster=4096,index=512),dict(number=17,sequence=9)]:
            v,path,row=self.fixture(DirectoryVolume(**options));self.good(v,path,row)
        self.good(v,path,row,mutate_after_prepare=True)

    def test_fragmented_source_bound_extensions_and_large_bitmap(self):
        for minor in (0,1):
            v,path,row=self.fixture(DirectoryVolume(kind='deep',minor=minor,mft_closure=True,
                list_form='nonresident',bitmap_form='nonresident',split_allocation=True,fragmented_allocation=True))
            self.good(v,path,row)
        v=DirectoryVolume(minor=0,bitmap_form='nonresident');v.replace_bitmap(b'\x03'+bytes(65535))
        v,path,row=self.fixture(v);self.good(v,path,row)

    def test_actual_native_offset_above4GiB(self):
        v,path,row=self.fixture(DirectoryVolume(minor=0,offset=(1<<32)+173,list_form='nonresident',
            bitmap_form='nonresident',split_allocation=True,fragmented_allocation=True))
        self.good(v,path,row)

    def test_exact_128_block_graph_and_payload_bound(self):
        selected=next(row for row in directory_cases() if row[0]=='exact-128-node-chain')
        _,v,controls,*_=selected
        v,path,row=self.fixture(v)
        self.good(v,path,row,directory=controls['directory'],limits=controls['limits'])

    def test_parent_source_free_replay_and_inert_construction(self):
        for minor in (0,1):
            v,path,row=self.fixture(DirectoryVolume(kind='deep',minor=minor,mft_closure=True,
                list_form='nonresident',bitmap_form='nonresident'))
            original=self.preserve(path,dict(row,mode='frame'))
            self.assertEqual(original['frame']['result'],original['verified'])
            frame=original['frame'];source=frame['result']['capture']['source_before']
            base=dict(row,expected_source=source)
            path.unlink()
            self.assertTrue(worker.run(dict(base,mode='construction'))['never_launched'])
            self.assertEqual(frame['result'],worker.run(dict(base,mode='verify',replace=frame))['verified'])
            unavailable=worker.run(base);self.retired(unavailable);self.assertFalse(unavailable['has_snapshot'])

    def test_every_new_prefix_receipt_field_is_reconstructed(self):
        for minor in (0,1):
            v,path,row=self.fixture(DirectoryVolume(kind='deep',minor=minor,mft_closure=True,
                list_form='nonresident'))
            original=self.preserve(path,dict(row,mode='frame'))['frame']
            base=dict(row,mode='verify',expected_source=original['result']['capture']['source_before'])
            fields=['profile_probe_response_count','profile_probe_sha256','profile_prefix_validation_attempted',
                'profile_prefix_validated','profile_prefix_boundary','profile_prefix_continued',
                'profile_prefix_validation_calls','profile_prefix_reused','profile_prefix_validation_sha256',
                'profile_probe_foundation_sha256','profile_selected_foundation_sha256','replay_calls','retained_replays']
            for key in fields:
                changed=copy.deepcopy(original);capture=changed['result']['capture'];old=capture[key]
                if isinstance(old,bool):capture[key]=not old
                elif old is None or (isinstance(old,str) and old.startswith('sha256:')):capture[key]='sha256:'+'0'*64
                else:capture[key]=str(int(old)+1)
                self.assertIn('error',self.preserve(path,dict(base,replace=changed)),(minor,key))
            # A child cannot choose a different prefix count and make it true by
            # adjusting the associated counters: the parent derives it by replay.
            changed=copy.deepcopy(original);c=changed['result']['capture'];n=int(c['profile_probe_response_count'])+1
            for key in ['profile_probe_response_count','profile_prefix_validation_calls','profile_prefix_reused']:c[key]=str(n)
            c['replay_calls']=str(len(changed['regions'])+n*2)
            self.assertIn('error',self.preserve(path,dict(base,replace=changed)))

    def test_strict_directory_input_and_frame_relationships(self):
        v,path,row=self.fixture(DirectoryVolume(kind='deep',minor=0))
        frame=self.preserve(path,dict(row,mode='frame'))['frame']
        base=dict(row,mode='verify',expected_source=frame['result']['capture']['source_before'])
        for change in ['schema','source-schema','extra','missing-ref','reference','limit','epoch','process',
                       'domain','profile','parent','claim','directory','bitmap','name','complete','capture-extra']:
            bad=copy.deepcopy(frame);c=bad['result']['capture']
            if change=='schema':bad['schema']='org.disked.ntfs-region-frame/1'
            elif change=='source-schema':bad['input']['schema']='org.disked.ntfs-source-request/1'
            elif change=='extra':bad['unknown']=True
            elif change=='missing-ref':del bad['input']['directory_reference']
            elif change=='reference':bad['input']['directory_reference']=str(ref(5,7))
            elif change=='limit':bad['input']['directory_limits']['blocks']='128'
            elif change=='epoch':bad['capture_epoch']='78'
            elif change=='process':bad['process_created']='1'
            elif change=='domain':c['domain']['directory_reference']='1';c['capture_domain']=held.digest(held.canonical(c['domain']))
            elif change=='profile':c['selected_profile']='3.1'
            elif change=='parent':c['parent_generations'][0]['file_id']='bad'
            elif change=='claim':bad['result']['authorizes_effects']=True
            elif change=='directory':bad['result']['observation']['directory']['reference']=str(ref(5,8))
            elif change=='bitmap':bad['result']['observation']['directory']['bitmap_complete']=False
            elif change=='name':next(e for e in bad['result']['observation']['directory']['entries'] if not e['end_marker'])['name_hex']='ff'
            elif change=='complete':bad['result']['observation']['complete']=False
            else:c['unknown']=True
            self.assertIn('error',self.preserve(path,dict(base,replace=bad)),change)
        for i in range(len(frame['regions'])):
            for change in ('alter','missing','reorder','extra'):
                bad=copy.deepcopy(frame)
                if change=='alter':bad['regions'][i]['bytes']='ff'+bad['regions'][i]['bytes'][2:]
                elif change=='missing':bad['regions'].pop(i)
                elif change=='reorder':
                    if i==0:continue
                    bad['regions'][i-1],bad['regions'][i]=bad['regions'][i],bad['regions'][i-1]
                else:bad['regions'].insert(i,copy.deepcopy(bad['regions'][i]))
                self.assertIn('error',self.preserve(path,dict(base,replace=bad)),(i,change))

    def test_invalid_inputs_and_normal_fault_isolation(self):
        _,path,row=self.fixture(DirectoryVolume(minor=0))
        frame=self.preserve(path,dict(row,mode='frame'))['frame']
        controls=[dict(capture_epoch='0'),dict(invalid_kind=True),dict(bootstrap_directory_controls=True),dict(profile='future'),
                  dict(directory=dict(reference='5')),dict(directory=dict(limits=dict(entries='0'))),
                  dict(directory=dict(limits=dict(blocks='129'))),dict(directory=dict(limits=dict(bitmap_bytes='65537'))),
                  dict(fixture=dict(capture_call='1')),dict(fixture=dict(worker_fault='prefix_changed'))]
        for extra in controls:
            out=self.preserve(path,dict(row,mode='construction',**extra))
            self.assertIn('error',out,extra)
        for key in ('directory_reference','directory_limits'):
            wire=copy.deepcopy(frame['input']);del wire[key]
            self.assertIn('error',self.preserve(path,dict(row,mode='decode_input',replace_input=wire)))
        for extra in [dict(unknown='1'),dict(entries='18446744073709551616'),dict(entries='4097')]:
            wire=copy.deepcopy(frame['input']);wire['directory_limits'].update(extra)
            self.assertIn('error',self.preserve(path,dict(row,mode='decode_input',replace_input=wire)))
        for call in ('0','01','2049','18446744073709551616','-1'):
            self.assertIn('error',self.preserve(path,dict(row,mode='construction',fixture=dict(capture_call=call)),True))

    def test_partial_profiles_budgets_and_native_faults_remain_inspectable(self):
        for minor in (0,1,2):
            v,path,row=self.fixture(DirectoryVolume(minor=minor))
            for extra in [dict(profile='3.'+str(1-minor))] if minor<2 else [{}]:
                out=self.preserve(path,dict(row,**extra));self.retired(out)
                self.assertTrue(out['has_snapshot'],out)
                self.assertFalse(out['snapshot']['observation']['applicable'])
                self.assertEqual(out['snapshot']['observation']['diagnostic'],'ntfs_volume_version')
            for n in (1,len(v.bootstrap_reads)):
                out=self.preserve(path,dict(row,limits=dict(read_requests=str(n))));self.retired(out)
                self.assertTrue(out['has_snapshot'],out)
                self.assertFalse(out['snapshot']['observation']['applicable'])
                self.assertEqual(len(out['frame']['regions']),n)
        v,path,row=self.fixture(DirectoryVolume(minor=0,kind='deep'))
        for fault in ('short','error','changed','metadata','binding'):
            out=self.preserve(path,dict(row,fixture=dict(capture_fault=fault)),True)
            self.retired(out);self.assertTrue(out['has_snapshot'],(fault,out))
            self.assertFalse(out['snapshot']['observation']['applicable'])
        n=len(v.bootstrap_reads)
        for fault in ('short','error'):
            out=self.preserve(path,dict(row,fixture=dict(capture_fault=fault,capture_call=str(n+1))),True)
            self.retired(out);self.assertTrue(out['has_snapshot'],(fault,out))
            self.assertEqual(len(out['frame']['regions']),n+1)
            self.assertFalse(out['snapshot']['observation']['applicable'])
            self.assertTrue(out['snapshot']['capture']['profile_prefix_continued'])
        for at in (1,n+1,n*2+1):
            for fault in ('replay_bytes','replay_offset'):
                out=self.preserve(path,dict(row,fixture=dict(capture_fault=fault,capture_call=str(at))),True)
                self.retired(out);self.assertFalse(out['has_snapshot'],(at,fault,out))
        for selection,code in [(dict(reference=str(ref((1<<48)-1,3))),'ntfs_directory_reference_bounds'),
                               (dict(reference=str(ref(5,9))),'ntfs_directory_record')]:
            out=self.preserve(path,dict(row,directory=selection));self.retired(out)
            self.assertTrue(out['has_snapshot'],out)
            self.assertEqual(out['snapshot']['observation']['diagnostic'],code)
            self.assertFalse(out['snapshot']['observation']['applicable'])
        v=DirectoryVolume(minor=0);boot=v.input['regions'][0];raw=bytearray.fromhex(boot['hex']);raw[68]=0;boot['hex']=raw.hex()
        _,path,row=self.fixture(v);out=self.preserve(path,row);self.retired(out)
        self.assertTrue(out['has_snapshot'],out)
        self.assertEqual(out['snapshot']['observation']['diagnostic'],'ntfs_directory_index_size')
        self.assertFalse(out['snapshot']['capture']['profile_prefix_continued'])

    def test_worker_publication_and_host_corruption(self):
        _,path,row=self.fixture(DirectoryVolume(minor=0))
        for fault in ['payload_changed','result_changed','receipt_changed','process_changed','domain_changed',
                      'row_changed','prefix_changed','profile_hash_changed','claims']:
            out=self.preserve(path,dict(row,fixture=dict(worker_fault=fault)),True)
            self.retired(out);self.assertFalse(out['has_snapshot'],(fault,out))
            self.assertEqual(out['before']['status'],'unknown')
        for fault in ['capture','worker','code','request','scope','host','observer','attempt','pid','created',
                      'shape','status','claims','schema','digest']:
            out=self.preserve(path,dict(row,fixture=dict(reply_fault=fault)),True)
            self.retired(out);self.assertFalse(out['has_snapshot'],(fault,out))
        _,path,row=self.fixture(DirectoryVolume(minor=1))
        for fault in ['prefix_changed','profile_hash_changed']:
            out=self.preserve(path,dict(row,fixture=dict(worker_fault=fault)),True)
            self.retired(out);self.assertFalse(out['has_snapshot'],(fault,out))

    def test_actual_lifecycle_exit_pending_and_finite_retirement(self):
        _,path,row=self.fixture(DirectoryVolume(minor=0))
        for fault in ['before_spawn','after_spawn','after_spawn_alloc']:
            out=self.preserve(path,dict(row,fixture=dict(startup_fault=fault)),True)
            self.assertIn('startup_error',out)
            self.assertEqual(out['never_launched'],fault=='before_spawn')
            if fault!='before_spawn':self.retired(out)
        for fault in ['hang','late']:
            out=self.preserve(path,dict(row,mode='pending',fixture=dict(worker_fault=fault)),True)
            self.retired(out);self.assertFalse(out['has_snapshot'])
            self.assertEqual(out['before']['worker']['observation'],'running')
        out=self.preserve(path,dict(row,fixture=dict(worker_fault='exit')),True)
        self.retired(out);self.assertFalse(out['has_snapshot'])
        out=self.preserve(path,dict(row,cancel=True));self.retired(out);self.assertFalse(out['has_snapshot'])
        out=self.preserve(path,dict(row,fixture=dict(worker_fault='late')),True)
        self.retired(out);self.assertTrue(out['has_snapshot'])
        out=self.preserve(path,dict(row,mode='publication-live',fixture=dict(reply_fault='hold')),True)
        self.retired(out);self.assertFalse(out['has_snapshot'])
        self.assertEqual(out['before']['diagnostic'],'ntfs_worker_exit_pending')
        self.assertIsNone(out['before']['result'])
        for _ in range(3):
            out=self.preserve(path,dict(row,mode='retire-zero',fixture=dict(worker_fault='hang')),True)
            zero=out['zero_retirement']
            self.assertEqual(zero['retired'],zero['worker']['observation']=='exited')
            self.retired(out)

    def test_directory_frame_component_bounds_refuse_unbounded_values(self):
        _,path,row=self.fixture(DirectoryVolume(minor=0))
        original=self.preserve(path,dict(row,mode='frame'))['frame']
        base=dict(row,mode='verify',expected_source=original['result']['capture']['source_before'])
        for part,size in [('observation',2*1024*1024),('capture',65536)]:
            frame=copy.deepcopy(original);frame['result'][part]['overflow']='x'*size
            self.assertIn('error',self.preserve(path,dict(base,replace=frame)),part)
        frame=copy.deepcopy(original);frame['input']['overflow']='x'*131072
        self.assertIn('error',self.preserve(path,dict(base,replace=frame)))
        frame=copy.deepcopy(original);frame['overflow']='x'*(8*1024*1024)
        self.assertIn('error',self.preserve(path,dict(base,replace=frame)))
        frame=copy.deepcopy(original);frame['regions']=[copy.deepcopy(frame['regions'][0]) for _ in range(513)]
        self.assertIn('error',self.preserve(path,dict(base,replace=frame)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe',type=Path,required=True);parser.add_argument('--fault',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    worker.PROBE=args.probe.resolve();worker.FAULT=args.fault.resolve()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    summary=dict(status='pass' if result.wasSuccessful() else 'fail',methods=result.testsRun,cases=len(worker.RECEIPTS),
        failures=len(result.failures),errors=len(result.errors),receipts=worker.RECEIPTS,
        workers=worker.OBSERVATIONS,source_receipts=SOURCE_RECEIPTS,launch_records=LAUNCH_RECORDS,
        unverified=held.UNVERIFIED,full_0_1_0_complete=False,owner_accepted=False)
    args.output.write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__=='__main__':main()
