"""Real owned NTFS reader children and strict retained-byte frames, generated files only."""
import argparse
import copy
import ctypes
from ctypes import wintypes as T
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_ntfs_capture import Volume, bytes_at
from test_ntfs_file import canonical, digest, file_digest, temporary_directory, size_fixture, record_sparse_fixture

PROBE = FAULT = None
RECEIPTS = []
OBSERVATIONS = []


def run(row, fault=False):
    data = canonical(row) + b'\n'
    p = subprocess.run([str(FAULT if fault else PROBE)], input=data, capture_output=True, timeout=35)
    assert p.returncode == 0 and not p.stderr, (p.returncode, p.stderr[:3000])
    lines = p.stdout.splitlines()
    assert len(lines) == 1
    value = json.loads(lines[0])
    RECEIPTS.append(dict(input_sha256=digest(data), output_sha256=digest(p.stdout), fault=fault, exit_code=p.returncode))
    if 'retirement' in value:
        OBSERVATIONS.append(dict(worker=value['retirement']['worker'], retired=value['retirement']['retired'],
                                 independent=value.get('independent_process'), has_snapshot=value.get('has_snapshot',False)))
    return value


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory(prefix='disked-ntfs-worker-')
        self.root = Path(self.temp.name).resolve()
        self.index = 0

    def tearDown(self):
        self.assertEqual(self.root.parent, Path(tempfile.gettempdir()).resolve())
        self.assertTrue(self.root.name.startswith('disked-ntfs-worker-'))
        self.temp.cleanup()

    def fixture(self, volume=None):
        volume = volume or Volume(offset=173)
        self.index += 1
        path = self.root / f'generated-{self.index}.img'
        with path.open('xb') as stream:
            size = int(volume.input['source_bytes'])
            size_fixture(stream,size)
            for row in volume.input['regions']:
                stream.seek(int(row['offset'])); stream.write(bytes.fromhex(row['hex']))
            record_sparse_fixture(stream,size)
        return volume, path, dict(path=str(path), offset=volume.input['offset'], length=volume.input['length'],capture_epoch='77')

    def preserve(self, path, row, fault=False):
        before = file_digest(path)
        value = run(row, fault)
        self.assertEqual(before,file_digest(path))
        return value

    def retired(self, out):
        self.assertNotIn('error',out,out)
        state=out['retirement']
        self.assertTrue(state['retired'],state)
        self.assertEqual('exited',state['worker']['observation'],state)
        self.assertNotEqual('259',state['worker']['exit_code'])
        if identity:=out.get('independent_process'):
            self.assertEqual(identity['pid'],state['worker']['pid'])
            self.assertEqual(identity['created'],state['worker']['created'])
            self.assertTrue(identity['in_job'])

    def test_named_lease_acl_keeps_record_acl_and_actual_package_identity(self):
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        security=ctypes.WinDLL('advapi32',use_last_error=True)
        kernel.GetCurrentProcess.restype=T.HANDLE
        kernel.CloseHandle.argtypes=[T.HANDLE];kernel.LocalFree.argtypes=[ctypes.c_void_p]
        security.OpenProcessToken.argtypes=[T.HANDLE,T.DWORD,ctypes.POINTER(T.HANDLE)]
        security.GetTokenInformation.argtypes=[T.HANDLE,ctypes.c_int,ctypes.c_void_p,T.DWORD,ctypes.POINTER(T.DWORD)]
        security.ConvertSidToStringSidW.argtypes=[ctypes.c_void_p,ctypes.POINTER(T.LPWSTR)]
        token=T.HANDLE();self.assertTrue(security.OpenProcessToken(kernel.GetCurrentProcess(),8,ctypes.byref(token)))
        def sid(kind):
            size=T.DWORD();security.GetTokenInformation(token,kind,None,0,ctypes.byref(size))
            self.assertTrue(0<size.value<=65536)
            buffer=ctypes.create_string_buffer(size.value)
            self.assertTrue(security.GetTokenInformation(token,kind,buffer,len(buffer),ctypes.byref(size)))
            pointer=ctypes.cast(buffer,ctypes.POINTER(ctypes.c_void_p))[0];text=T.LPWSTR()
            self.assertTrue(security.ConvertSidToStringSidW(pointer,ctypes.byref(text)))
            try:return text.value
            finally:kernel.LocalFree(text)
        try:
            size=T.DWORD();container=T.DWORD()
            self.assertTrue(security.GetTokenInformation(token,29,ctypes.byref(container),4,ctypes.byref(size)))
            user=sid(1);package=sid(31) if container.value else None
        finally:kernel.CloseHandle(token)
        for fault in (False,True):
            value=run(dict(security_probe=True),fault)
            self.assertEqual(value['appcontainer'],bool(container.value))
            user_ace=dict(sid=user,mask=str(0x1f01ff),flags='0')
            self.assertTrue(value['record']['protected'] and value['lease']['protected'])
            self.assertEqual(value['record']['aces'],[user_ace])
            self.assertEqual(value['lease']['aces'],[user_ace]+([dict(sid=package,mask=str(0x1f01ff),flags='0')] if package else []))
            self.assertEqual(value['record']['query_opened'],not bool(container.value))
            self.assertEqual(value['record']['query_error'],'5' if container.value else '0')
            self.assertTrue(value['lease']['query_opened'])
            self.assertEqual(value['lease']['query_error'],'0')

    def test_actual_profiles_geometry_and_retention_after_teardown(self):
        for minor,selector,sector,size,usa in [(0,'auto',512,1024,48),(1,'auto',512,1024,48),
                (0,'3.0',512,1024,42),(1,'3.1',4096,4096,48),(0,'3.1',512,1024,48),(1,'3.0',512,1024,48)]:
            v,path,row=self.fixture(Volume(minor=minor,offset=173,sector=sector,size=size,usa=usa))
            out=self.preserve(path,dict(row,profile=selector))
            self.retired(out);self.assertTrue(out['has_snapshot'],out)
            self.assertTrue(out['retained_unchanged'])
            result=out['snapshot'];context=out['context'];frame=out['frame']
            self.assertEqual(frame['process_id'],context['pid'])
            self.assertEqual(frame['process_created'],context['created'])
            self.assertEqual('exited',out['before']['worker']['observation'])
            self.assertEqual(digest(canonical(frame)),context['frame_sha256'])
            self.assertEqual('77',context['capture_epoch'])
            self.assertEqual('ordinary-file-ntfs',context['image_profile'])
            self.assertEqual(selector=='auto' or selector==f'3.{minor}',result['observation']['applicable'])
            self.assertEqual(str(minor),result['observation']['volume_information']['minor'])
            self.assertEqual(v.initial_reads*2,[(int(r['offset']),int(r['requested'])) for r in frame['regions']])
            for region in frame['regions']:
                self.assertEqual(bytes_at(v.input,int(region['offset']),int(region['requested'])),bytes.fromhex(region['bytes']))
                self.assertTrue(region['seek_attempted'] and region['read_attempted'])
            self.assertFalse(result['authorizes_effects']);self.assertFalse(result['product_dispatch_admitted'])

    def test_parent_replay_after_source_removed_and_inert_preparation(self):
        _,path,row=self.fixture()
        original=self.preserve(path,dict(row,mode='frame'))
        self.assertEqual(original['frame']['result'],original['verified'])
        source=original['frame']['result']['capture']['source_before']
        path.unlink()
        base=dict(row,expected_source=source)
        self.assertTrue(run(dict(base,mode='construction'))['never_launched'])
        self.assertEqual(original['verified'],run(dict(base,mode='verify',replace=original['frame']))['verified'])
        unavailable=run(base);self.retired(unavailable);self.assertFalse(unavailable['has_snapshot'])

    def test_source_bound_closure_and_extended_frame_replay(self):
        from ntfs_closure_fixture import ClosureVolume
        from test_ntfs_closure import good
        for minor in (0,1):
            for nonresident in (False,True):
                v,path,row=self.fixture(ClosureVolume(minor=minor,offset=173,nonresident_list=nonresident,volume_nonresident=nonresident))
                out=self.preserve(path,row);self.retired(out)
                self.assertTrue(out['has_snapshot'] and out['retained_unchanged'],out)
                good(out['snapshot']['observation'],v)
                frame=out['frame'];self.assertEqual(v.initial_reads*2,[(int(r['offset']),int(r['requested'])) for r in frame['regions']])
                self.assertEqual(out['context']['frame_sha256'],digest(canonical(frame)))
        base=dict(row,mode='verify',expected_source=frame['result']['capture']['source_before'])
        # The new list and extension reads have the same exact ordered replay
        # obligations as boot/seed reads, including after source removal.
        path.unlink()
        self.assertEqual(frame['result'],run(dict(base,replace=frame))['verified'])
        for index in range(3,len(v.initial_reads)):
            for change in ('alter','missing','reorder','extra'):
                changed=copy.deepcopy(frame)
                if change=='alter':changed['regions'][index]['bytes']='ff'+changed['regions'][index]['bytes'][2:]
                elif change=='missing':changed['regions'].pop(index)
                elif change=='reorder':changed['regions'][index],changed['regions'][index-1]=changed['regions'][index-1],changed['regions'][index]
                else:changed['regions'].insert(index,copy.deepcopy(changed['regions'][index]))
                self.assertIn('error',run(dict(base,replace=changed)),(index,change))

    def test_strict_frame_relationships_and_byte_reconstruction(self):
        _,path,row=self.fixture(Volume(minor=0,offset=173))
        original=self.preserve(path,dict(row,mode='frame'))['frame']
        base=dict(row,mode='verify',expected_source=original['result']['capture']['source_before'])
        for change in ['epoch','input','claim','metadata','final','domain','process','parent','sequence','profile',
                       'probe','selected','replays','calls','binding','cancel','stable','extra','offset','requested',
                       'seek','read','error','refusal','bytes','missing','extra-row','applicable','output']:
            frame=copy.deepcopy(original);c=frame['result']['capture'];region=frame['regions'][0]
            if change=='epoch':frame['capture_epoch']='78'
            elif change=='input':frame['input']['profile']='3.1'
            elif change=='claim':frame['result']['authorizes_effects']=True
            elif change=='metadata':c['metadata_equal']=False
            elif change=='final':c['source_final']['written']='1'
            elif change=='domain':c['capture_domain']='sha256:'+'0'*64
            elif change=='process':frame['process_created']='1'
            elif change=='parent':c['parent_generations'][0]['file_id']='bad'
            elif change=='sequence':c['sequence']='0'
            elif change=='profile':c['selector']='3.0'
            elif change=='probe':c['profile_probe_diagnostic']=''
            elif change=='selected':c['selected_profile']='3.1'
            elif change=='replays':c['retained_replays']='1'
            elif change=='calls':c['replay_calls']='1'
            elif change=='binding':c['binding_checks']='1'
            elif change=='cancel':c['cancel_observed']=True
            elif change=='stable':c['observed_stable']=False
            elif change=='extra':frame['unknown']=True
            elif change=='offset':region['offset']='0'
            elif change=='requested':region['requested']='0'
            elif change=='seek':region['seek_attempted']=False
            elif change=='read':region['read_attempted']=False
            elif change=='error':region['error']='4294967296'
            elif change=='refusal':region['refusal']='x'*129
            elif change=='bytes':region['bytes']='00'+region['bytes'][2:]
            elif change=='missing':frame['regions'].pop()
            elif change=='extra-row':frame['regions'].append(copy.deepcopy(region))
            elif change=='applicable':frame['result']['observation']['applicable']=False
            else:frame['result']['observation']['extra']='unverified'
            self.assertIn('error',self.preserve(path,dict(base,replace=frame)),change)

    def test_invalid_request_and_normal_fault_refusal(self):
        _,path,row=self.fixture()
        frame=self.preserve(path,dict(row,mode='frame'))['frame']
        for change in [dict(capture_epoch='0'),dict(profile='future'),dict(offset=str(1<<64)),dict(limits={'read_bytes':'0'}),
                       dict(fixture={'worker_fault':'hang'}),dict(fixture={'capture_fault':'short'}),dict(fixture={'reply_fault':'hold'})]:
            self.assertIn('error',self.preserve(path,dict(row,mode='construction',**change)))
        for change in ['schema','unknown','missing','limit','metadata','selector']:
            wire=copy.deepcopy(frame['input'])
            if change=='schema':wire['schema']='org.disked.ntfs-source-request/2'
            elif change=='unknown':wire['unknown']=1
            elif change=='missing':del wire['profile']
            elif change=='limit':wire['limits']['read_bytes']=str(1<<64)
            elif change=='metadata':wire['expected_source']['hardlinks']='2'
            else:wire['profile']='unknown'
            self.assertIn('error',self.preserve(path,dict(row,mode='decode_input',replace_input=wire)))

    def test_actual_corrupt_publications_and_host_reply_bindings(self):
        _,path,row=self.fixture()
        for fault in ['payload_changed','result_changed','receipt_changed','process_changed','domain_changed','row_changed','claims']:
            out=self.preserve(path,dict(row,fixture={'worker_fault':fault}),True)
            self.retired(out);self.assertFalse(out['has_snapshot'],(fault,out))
            self.assertEqual('unknown',out['before']['status'])
        for fault in ['capture','worker','code','request','scope','host','observer','attempt','pid','created','shape','status','claims','schema','digest']:
            out=self.preserve(path,dict(row,fixture={'reply_fault':fault}),True)
            self.retired(out);self.assertFalse(out['has_snapshot'],(fault,out))

    def test_cancel_hang_late_exit_startup_and_zero_retirement(self):
        _,path,row=self.fixture()
        for fault in ['before_spawn','after_spawn','after_spawn_alloc']:
            out=self.preserve(path,dict(row,fixture={'startup_fault':fault}),True)
            self.assertIn('startup_error',out)
            self.assertEqual(fault=='before_spawn',out['never_launched'])
            if fault!='before_spawn':self.retired(out)
        for fault in ['hang','late']:
            out=self.preserve(path,dict(row,mode='pending',fixture={'worker_fault':fault}),True)
            self.retired(out);self.assertFalse(out['has_snapshot'])
            self.assertEqual('running',out['before']['worker']['observation'])
        out=self.preserve(path,dict(row,fixture={'worker_fault':'exit'}),True)
        self.retired(out);self.assertFalse(out['has_snapshot'])
        out=self.preserve(path,dict(row,cancel=True));self.retired(out);self.assertFalse(out['has_snapshot'])
        out=self.preserve(path,dict(row,fixture={'worker_fault':'late'}),True)
        self.retired(out);self.assertTrue(out['has_snapshot'],out)
        out=self.preserve(path,dict(row,mode='publication-live',fixture={'reply_fault':'hold'}),True)
        self.retired(out);self.assertFalse(out['has_snapshot'],out)
        self.assertEqual('ntfs_worker_exit_pending',out['before']['diagnostic'],out)
        self.assertEqual('running',out['before']['worker']['observation'])
        self.assertIsNone(out['before']['result'])
        for _ in range(4):
            out=self.preserve(path,dict(row,mode='retire-zero',fixture={'worker_fault':'hang'}),True)
            zero=out['zero_retirement'];self.assertEqual(zero['retired'],zero['worker']['observation']=='exited')
            self.retired(out)

    def test_incomplete_native_and_binding_observations_remain_inspectable(self):
        _,path,row=self.fixture()
        for fault in ['short','error','changed','metadata','binding']:
            out=self.preserve(path,dict(row,fixture={'capture_fault':fault}),True)
            self.retired(out);self.assertTrue(out['has_snapshot'],(fault,out))
            self.assertFalse(out['snapshot']['observation']['applicable'])
            self.assertFalse(out['snapshot']['capture']['observed_stable'])
        for fault in ['replay_bytes','replay_offset']:
            out=self.preserve(path,dict(row,fixture={'capture_fault':fault}),True)
            self.retired(out);self.assertFalse(out['has_snapshot'],(fault,out))

    def test_unsupported_profiles_budget_prefixes_and_expected_source(self):
        for minor in (0,1,2):
            _,path,row=self.fixture(Volume(minor=minor,offset=173))
            if minor==2:
                out=self.preserve(path,row);self.retired(out);self.assertTrue(out['has_snapshot'])
                self.assertIsNone(out['snapshot']['capture']['selected_profile'])
                self.assertFalse(out['snapshot']['observation']['applicable'])
                self.assertEqual('ntfs_file_profile_unresolved',out['snapshot']['observation']['binding_diagnostic'])
            out=self.preserve(path,dict(row,limits={'read_requests':'1'}))
            self.retired(out);self.assertTrue(out['has_snapshot'],out)
            self.assertEqual(1,len(out['frame']['regions']))
            self.assertFalse(out['snapshot']['observation']['applicable'])
            original=self.preserve(path,dict(row,mode='frame'))['frame']
            expected=copy.deepcopy(original['result']['capture']['source_before']);expected['written']='1'
            out=self.preserve(path,dict(row,expected_source=expected))
            self.retired(out);self.assertFalse(out['has_snapshot'])


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--probe',type=Path,required=True);ap.add_argument('--fault',type=Path,required=True);ap.add_argument('--output',type=Path)
    a=ap.parse_args();PROBE=a.probe.resolve();FAULT=a.fault.resolve()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    if a.output:a.output.write_bytes(json.dumps(dict(status='pass' if result.wasSuccessful() else 'fail',tests=result.testsRun,cases=len(RECEIPTS),receipts=RECEIPTS,workers=OBSERVATIONS,full_0_1_0_complete=False),indent=2).encode()+b'\n')
    raise SystemExit(not result.wasSuccessful())
