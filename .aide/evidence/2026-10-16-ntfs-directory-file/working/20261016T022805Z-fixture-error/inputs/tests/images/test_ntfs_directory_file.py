"""Actual generated ordinary files, directory oracles and retained-prefix faults."""
import argparse
import copy
import json
import os
from pathlib import Path
import struct
import unittest

import test_ntfs_file as held
from test_ntfs_capture import bytes_at
from test_ntfs_directory import good as directory_good
from ntfs_directory_fixture import DirectoryVolume, record, resident, ref


class Tests(unittest.TestCase):
    setUp = held.Tests.setUp
    tearDown = held.Tests.tearDown
    fixture = held.Tests.fixture
    preserve = held.Tests.preserve

    def row(self, v, path, **extra):
        selection = copy.deepcopy(v.input['directory'])
        if v.number != 5:
            selection.setdefault('reference', str(v.reference))
        return dict(path=str(path), offset=v.input['offset'], length=v.input['length'],
                    directory=extra.pop('directory', selection), **extra)

    def good(self, v, path, extra=None, fault=False):
        value = held.Tests.good(self, v, path, extra, fault)
        result = value['result']; capture = result['capture']; obs = result['observation']
        self.assertEqual(result['schema'], 'org.disked.ntfs-directory-file-capture/1')
        directory_good(obs, v)
        domain = capture['domain']
        self.assertEqual(domain['provider'], 'ntfs-directory-file-prototype')
        selected = (extra or {}).get('directory', v.input['directory'])
        wanted = selected.get('reference', str(v.reference) if v.number != 5 else '0')
        self.assertEqual(domain['directory_reference'], wanted)
        defaults = dict(entries='4096', blocks='64', bitmap_bytes='65536')
        defaults.update(selected.get('limits', {}))
        self.assertEqual(domain['directory_limits'], defaults)
        automatic30 = v.input['minor'] == '0' and (extra or {}).get('profile','auto') == 'auto'
        self.assertEqual(capture['profile_prefix_validation_attempted'], automatic30)
        self.assertEqual(capture['profile_prefix_validated'], automatic30)
        self.assertEqual(capture['profile_prefix_boundary'], automatic30)
        self.assertEqual(capture['profile_prefix_continued'], automatic30)
        n = len(v.bootstrap_reads) if automatic30 else 0
        self.assertEqual(capture['profile_prefix_validation_calls'], str(n))
        self.assertEqual(capture['profile_prefix_reused'], str(n))
        self.assertEqual(capture['profile_probe_response_count'], str(n if automatic30 else len(v.initial_reads)*2))
        expected_replay = len(v.initial_reads)*2 + n*2
        self.assertEqual(capture['replay_calls'], str(expected_replay))
        if automatic30:
            self.assertEqual(capture['profile_probe_foundation_sha256'], capture['profile_selected_foundation_sha256'])
            self.assertRegex(capture['profile_prefix_validation_sha256'], r'^sha256:[0-9a-f]{64}$')
        else:
            self.assertIsNone(capture['profile_prefix_validation_sha256'])
        return value

    def batches(self, path, rows, fault=True):
        out = []
        for i in range(0, len(rows), 6):
            out += self.preserve(path, rows[i:i+6], fault)
        return out

    def test_actual_profiles_layouts_and_exact_native_trace(self):
        for minor in (0,1):
            for kind in ('leaf','empty','single','siblings','deep','preallocated'):
                v,path = self.fixture(DirectoryVolume(kind=kind, minor=minor, offset=173))
                for profile in ('auto','3.'+str(minor)):
                    value = self.good(v,path,dict(profile=profile,release_check=True))
                    self.assertTrue(all(r['opened'] for r in value['released_access']))
        for options in [dict(cluster=512,index=512,size=512),dict(cluster=4096,index=512),
                        dict(cluster=512,index=8192,size=4096),dict(size=2048),
                        dict(minor=0,usa=42,kind='deep'),dict(number=17,sequence=9),
                        dict(namespace=3,name=b'\x1b\0\0\xd8\xff\xdc')]:
            v,path = self.fixture(DirectoryVolume(**options));self.good(v,path)

    def test_source_bound_extensions_fragmentation_and_bitmaps(self):
        for minor in (0,1):
            for form in ('resident','nonresident'):
                v,path = self.fixture(DirectoryVolume(kind='deep',minor=minor,offset=173,
                    list_form=form,bitmap_form=form,fragmented_allocation=True,split_allocation=True))
                self.good(v,path)
            v,path = self.fixture(DirectoryVolume(kind='deep',minor=minor,mft_closure=True,
                list_form='nonresident',bitmap_form='nonresident',fragmented_allocation=True,split_allocation=True))
            self.good(v,path)
        v=DirectoryVolume(minor=0,bitmap_form='nonresident');v.replace_bitmap(b'\x03'+bytes(65535))
        v,path=self.fixture(v);self.good(v,path)

    def test_actual_native_offset_over4GiB(self):
        v,path=self.fixture(DirectoryVolume(minor=0,offset=(1<<32)+173,
            bitmap_form='nonresident',fragmented_allocation=True))
        self.good(v,path)

    def test_each_live_read_failure_and_changed_reread(self):
        for minor in (0,1):
            v,path=self.fixture(DirectoryVolume(kind='deep',minor=minor,list_form='nonresident',
                bitmap_form='nonresident',fragmented_allocation=True,split_allocation=True))
            count=len(v.initial_reads)*2
            rows=[];wanted=[]
            for call in range(1,count+1):
                for mode in ('short','error','partial_error','throw','read_throw'):
                    rows.append(self.row(v,path,mode=mode,call=str(call)))
                    wanted.append((call,'ntfs_read_length' if mode=='short' else 'ntfs_reader_failure'))
                if call>len(v.initial_reads):
                    rows.append(self.row(v,path,mode='changed',call=str(call)))
                    wanted.append((call,'ntfs_source_changed'))
            for (call,diagnostic),value in zip(wanted,self.batches(path,rows)):
                obs=value['result']['observation'];capture=value['result']['capture']
                self.assertEqual(obs['diagnostic'],diagnostic,(minor,call,value))
                self.assertFalse(obs['applicable'] or capture['observed_stable'])
                self.assertTrue(capture['replay_equal'])
                self.assertEqual(len(value['regions']),call)

    def test_prefix_validation_and_resume_faults_forbid_native_suffix(self):
        v,path=self.fixture(DirectoryVolume(minor=0,mft_closure=True,list_form='nonresident'))
        prefix=len(v.bootstrap_reads)
        rows=[self.row(v,path,mode=mode,call=str(call))
              for call in range(1,prefix*2+1)
              for mode in ('replay_bytes','replay_offset','replay_provenance','replay_throw')]
        for value in self.batches(path,rows):
            capture=value['result']['capture'];obs=value['result']['observation']
            self.assertFalse(capture['profile_selection_equal'] or capture['observed_stable'] or obs['applicable'])
            self.assertEqual(len(value['regions']),prefix)
            self.assertEqual(obs['binding_diagnostic'],'ntfs_file_profile_disagreement')
            self.assertIsNone(capture['selected_profile'])

    def test_each_final_replay_fault_cannot_authorize_collection(self):
        for minor in (0,1):
            v,path=self.fixture(DirectoryVolume(kind='deep',minor=minor))
            count=len(v.initial_reads)*2
            prefix=len(v.bootstrap_reads)*2 if minor==0 else 0
            rows=[self.row(v,path,mode=mode,call=str(prefix+call))
                  for call in range(1,count+1)
                  for mode in ('replay_bytes','replay_offset','replay_provenance','replay_throw')]
            for value in self.batches(path,rows):
                capture=value['result']['capture'];obs=value['result']['observation']
                self.assertFalse(capture['replay_equal'] or capture['observed_stable'] or obs['applicable'])
                self.assertEqual(len(value['regions']),count)
                self.assertTrue(capture['profile_selection_equal'])

    def test_exact_budgets_and_pre_directory_refusal_do_not_retry(self):
        for minor in (0,1):
            v,path=self.fixture(DirectoryVolume(kind='deep',minor=minor,list_form='nonresident',bitmap_form='nonresident'))
            n=len(v.initial_reads);size=sum(length for _,length in v.initial_reads)
            self.good(v,path,dict(limits=dict(read_requests=str(n*2),read_bytes=str(size*2),retained_bytes=str(size)),
                directory=dict(limits=dict(entries=str(len(v.expected_rows)),blocks=str(len(v.blocks)),bitmap_bytes=str(len(v.bitmap_value))))))
            prefix=len(v.bootstrap_reads);prefix_bytes=sum(length for _,length in v.bootstrap_reads)
            rows=[self.row(v,path,limits=dict(read_requests=str(prefix))),
                  self.row(v,path,limits=dict(read_bytes=str(prefix_bytes))),
                  self.row(v,path,directory=dict(reference=str(ref((1<<48)-1,3))))]
            for diagnostic,value in zip(['ntfs_read_budget','ntfs_read_budget','ntfs_directory_reference_bounds'],self.batches(path,rows,False)):
                self.assertEqual(value['result']['observation']['diagnostic'],diagnostic)
                self.assertEqual(len(value['regions']),prefix)
                capture=value['result']['capture']
                self.assertTrue(capture['replay_equal'])
                self.assertFalse(capture['observed_stable'] or capture['profile_prefix_continued'])
                if minor==0:self.assertTrue(capture['profile_prefix_validated'])
        v=DirectoryVolume(minor=0);boot=v.input['regions'][0];raw=bytearray.fromhex(boot['hex']);raw[68]=0;boot['hex']=raw.hex()
        v,path=self.fixture(v);value=self.preserve(path,[self.row(v,path)])[0]
        self.assertEqual(value['result']['observation']['diagnostic'],'ntfs_directory_index_size')
        self.assertEqual(len(value['regions']),len(v.bootstrap_reads))
        self.assertTrue(value['result']['capture']['profile_prefix_validated'])
        self.assertFalse(value['result']['capture']['profile_prefix_continued'])

    def test_explicit_mismatch_unknown_profiles_and_invalid_controls(self):
        for minor in (0,1):
            v,path=self.fixture(DirectoryVolume(minor=minor))
            value=self.preserve(path,[self.row(v,path,profile='3.'+str(1-minor))])[0]
            self.assertEqual(value['result']['observation']['diagnostic'],'ntfs_volume_version')
            self.assertEqual(len(value['regions']),len(v.bootstrap_reads))
            self.assertTrue(value['result']['capture']['replay_equal'])
            self.assertFalse(value['result']['capture']['profile_prefix_validation_attempted'])
        v=DirectoryVolume();at,size=v.bootstrap_reads[-1]
        info=resident(b'\0'*8+b'\x03\x02\0\0',kind=0x70)
        raw=record([info],number=3,size=v.size)
        v.input['regions'].append(dict(offset=str(at),hex=bytes(raw).hex()))
        v,path=self.fixture(v);value=self.preserve(path,[self.row(v,path)])[0]
        self.assertEqual(value['result']['observation']['diagnostic'],'ntfs_volume_version')
        self.assertIsNone(value['result']['capture']['selected_profile'])
        self.assertEqual(len(value['regions']),len(v.bootstrap_reads))
        bad=[(dict(profile='unknown'),'ntfs_file_profile'),(dict(directory=dict(reference='5')),'ntfs_directory_reference'),
             (dict(directory=dict(limits=dict(entries='0'))),'ntfs_directory_limits'),
             (dict(directory=dict(limits=dict(blocks='129'))),'ntfs_directory_limits'),
             (dict(directory=dict(limits=dict(bitmap_bytes='65537'))),'ntfs_directory_limits'),
             (dict(limits=dict(read_requests='0')),'ntfs_capture_limits'),
             (dict(offset=str(1<<63)),'ntfs_file_seek_range')]
        rows=[self.row(v,self.root/'missing.img',**controls) for controls,_ in bad]
        for (_,code),value in zip(bad,self.batches(path,rows,False)):
            self.assertEqual(value['refusal'],code)
            self.assertEqual(value['read_calls'],'0')

    def test_binding_metadata_cancellation_and_frozen_controls(self):
        v,path=self.fixture(DirectoryVolume(minor=0))
        value=self.good(v,path,dict(mode='mutate_request'),True)
        before=value['result']['capture']['source_before']
        self.good(v,path,dict(expected_source=before,mode='mutate_request'),True)
        rows=[self.row(v,path,mode=mode,call='1',release_check=True)
              for mode in ('metadata','metadata_throw','cancel','cancel_once','cancel_throw','binding','binding_throw')]
        for value in self.batches(path,rows):
            if 'result' in value:
                self.assertFalse(value['result']['observation']['applicable'] or value['result']['capture']['observed_stable'])
            else:self.assertIn('refusal',value)
            self.assertTrue(all(r['opened'] for r in value['released_access']))
        full=len(v.initial_reads)*2
        for mode in ('cancel','cancel_once','binding','binding_throw'):
            # First live suffix request after the cached3.0 prefix; no stop callback in pure passes.
            at=2+len(v.bootstrap_reads)*2
            value=self.preserve(path,[self.row(v,path,mode=mode,call=str(at))],True)[0]
            self.assertFalse(value['result']['capture']['binding_checks_ok'])
            self.assertFalse(value['result']['observation']['applicable'])
            self.assertLess(len(value['regions']),full)
        wrong=dict(before,bytes='1')
        value=self.preserve(path,[self.row(v,path,expected_source=wrong,mode='mutate_request')],True)[0]
        self.assertEqual(value['refusal'],'ntfs_file_source_changed')

    def test_held_source_parent_exclusion_release_and_normal_fault_isolation(self):
        v,path=self.fixture(DirectoryVolume(minor=0),name='owned/inner/source.img')
        value=self.good(v,path,dict(mode='held_access',call=str(len(v.bootstrap_reads)+1),release_check=True,
            access_parents=[str(path.parent),str(path.parent.parent)]),True)
        for group in value['held_access']:
            self.assertFalse(group[0]['opened'] or group[1]['opened'] or group[2]['moved'])
        self.assertTrue(all(r['opened'] for r in value['released_access']))
        self.assertTrue(all(r['opened'] for group in value['released_parent_access'] for r in group))
        environment=dict(os.environ,DISKED_NTFS_FILE_TEST_MODE='error',DISKED_NTFS_FILE_FAULT='1')
        value=self.preserve(path,[self.row(v,path,mode='cancel',call='1')],False,environment)[0]
        directory_good(value['result']['observation'],v)
        self.assertEqual(value['stop_calls'],'0')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe',type=Path,required=True);parser.add_argument('--fault',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    held.PROBE=args.probe.resolve();held.FAULT=args.fault.resolve()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    summary=dict(cases=len(held.RECEIPTS),methods=result.testsRun,failures=len(result.failures),errors=len(result.errors),
        receipts=held.RECEIPTS,unverified=held.UNVERIFIED,
        scope='Generated Windows ordinary-file source-bound directory collection only; no worker/public/physical/full-product admission.')
    args.output.write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__=='__main__':main()
