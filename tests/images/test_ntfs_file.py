"""Actual disposable file identity/profile/replay tests; never raw devices."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support.tempdir import temporary_directory

from test_ntfs_capture import Volume, bytes_at

PROBE = FAULT = None
RECEIPTS = []
UNVERIFIED = []
BINDING_OBSERVATIONS = []


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def file_digest(path):
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        while raw := stream.read(1048576):
            sha.update(raw)
    return 'sha256:' + sha.hexdigest()


def run(rows, fault=False, env=None, capture=None):
    process = subprocess.Popen([str(FAULT if fault else PROBE)], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    try:
        stdout, stderr = process.communicate(canonical(rows), timeout=100)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        raise
    assert process.returncode == 0 and not stderr, (process.returncode, stderr[:2000])
    values = json.loads(stdout)
    assert len(values) == len(rows)
    times = [wintypes.FILETIME() for _ in range(4)]
    get_times = ctypes.windll.kernel32.GetProcessTimes
    get_times.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)]*4
    get_times.restype = wintypes.BOOL
    assert get_times(int(process._handle), *(ctypes.byref(t) for t in times))
    created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
    if capture is not None:
        capture.append(dict(input_hex=canonical(rows).hex(),output_hex=stdout.hex(),stderr_hex=stderr.hex(),
                            process_id=process.pid,process_created=str(created),exit_code=process.returncode))
    for row, result in zip(rows, values):
        assert result['fault_controls_available'] == fault
        if 'result' in result:
            capture = result['result']['capture']
            assert capture['process_id'] == str(process.pid)
            assert capture['process_created'] == str(created)
        RECEIPTS.append(dict(input_sha256=digest(canonical(row)), observation_sha256=digest(canonical(result)), fault=fault, process_exit_code=0))
    return values


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory(prefix='disked-ntfs-owned-')
        self.root = Path(self.temp.name).resolve()
        self.assertEqual(self.root.parent, Path(tempfile.gettempdir()).resolve())
        self.index = 0

    def tearDown(self):
        # Exact owned temporary root; no traversal of unrelated paths.
        self.assertEqual(self.root.parent, Path(tempfile.gettempdir()).resolve())
        self.assertTrue(self.root.name.startswith('disked-ntfs-owned-'))
        self.temp.cleanup()

    def fixture(self, v=None, name=None):
        v = v or Volume()
        self.index += 1
        path = self.root / (name or f'generated-{self.index}.img')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            if int(v.input['offset']) > (1<<32):
                import msvcrt
                returned = wintypes.DWORD()
                sparse = ctypes.windll.kernel32.DeviceIoControl
                sparse.argtypes = [wintypes.HANDLE,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,
                                   wintypes.LPVOID,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),wintypes.LPVOID]
                sparse.restype = wintypes.BOOL
                if not sparse(msvcrt.get_osfhandle(stream.fileno()),0x000900c4,None,0,None,0,ctypes.byref(returned),None):
                    reason = 'owned sparse fixture unsupported: '+str(ctypes.GetLastError())
                    UNVERIFIED.append(dict(check='actual-offset-over4GiB',reason=reason))
                    self.skipTest(reason)
            stream.truncate(int(v.input['source_bytes']))
            for region in v.input['regions']:
                stream.seek(int(region['offset']))
                stream.write(bytes.fromhex(region['hex']))
        # Closing makes fixture bytes visible; this is not a power-loss test.
        return v, path

    def test_normalized_binding_keeps_full_name_and_volume(self):
        _, path = self.fixture()
        original = file_digest(path), path.stat().st_size
        other_root = os.environ.get('DISKED_TEST_OTHER_VOLUME_ROOT')
        self.assertTrue(other_root, 'Qualification requires an explicitly selected other-volume root')
        self.assertEqual(str(Path(other_root)), Path(other_root).anchor)
        self.assertNotEqual(Path(other_root).anchor.casefold(), path.anchor.casefold())
        rows = [
            (str(path), True),
            (str(path).swapcase(), True),
            (str(path.parent) + '\\.\\' + path.name, True),
            (str(path.with_name('different.img')), False),
            (path.anchor, False),
            (str(Path(other_root)) + str(path)[len(path.anchor):], False),
        ]
        raw = []
        actual = run([dict(path=str(path),binding_expected=expected) for expected,_ in rows],capture=raw)
        BINDING_OBSERVATIONS.append(dict(expected=[passed for _,passed in rows],raw=raw,
                                        source_before=original,source_after=(file_digest(path),path.stat().st_size)))
        for value,(_,passed) in zip(actual,rows):
            self.assertEqual(value['binding_passed'],passed,value)
            self.assertEqual(value['read_calls'],'0')
            if not passed:
                self.assertEqual(value['refusal'],'image_path_identity')
                self.assertEqual(value['platform_error'],'0')  # Identity mismatch, not an inaccessible comparison root.
        self.assertEqual((file_digest(path),path.stat().st_size),original)

    def row(self, v, path, **extra):
        return dict(path=str(path), offset=v.input['offset'], length=v.input['length'], **extra)

    def preserve(self, path, rows, fault=False, env=None):
        before, size = file_digest(path), path.stat().st_size
        values = run(rows, fault, env)
        self.assertEqual(file_digest(path), before)
        self.assertEqual(path.stat().st_size, size)
        return values

    def good(self, v, path, extra=None, fault=False):
        row = self.row(v, path, **(extra or {}))
        value = self.preserve(path, [row], fault)[0]
        self.assertNotIn('refusal', value, value)
        result = value['result']; capture = result['capture']; obs = result['observation']
        self.assertTrue(obs['applicable'], value)
        self.assertTrue(obs['complete'] and obs['reread_equal'])
        for name in ('metadata_complete','metadata_equal','binding_checks_ok','replay_equal','profile_selection_equal','observed_stable'):
            self.assertTrue(capture[name], (name, value))
        self.assertEqual(capture['source_before'], capture['source_after'])
        self.assertEqual(capture['source_before'], capture['source_final'])
        self.assertEqual(capture['source_before']['bytes'], str(path.stat().st_size))
        self.assertEqual(capture['source_before']['hardlinks'], '1')
        self.assertEqual(capture['source_identity_digest'], digest(canonical(capture['source_before'])))
        self.assertEqual(obs['source_id'], capture['source_identity_digest'])
        self.assertEqual(obs['epoch'], capture['sequence'])
        self.assertGreater(int(capture['sequence']), 0)
        self.assertEqual(capture['capture_domain'], digest(canonical(capture['domain'])))
        self.assertEqual(capture['domain']['source'], capture['source_before'])
        self.assertEqual(capture['domain']['volume_offset'], row['offset'])
        self.assertEqual(capture['domain']['volume_bytes'], row['length'])
        selected = '3.'+v.input['minor']
        self.assertEqual(capture['selected_profile'], selected)
        self.assertEqual(capture['domain']['selected_profile'], selected)
        self.assertEqual(capture['selector'], row.get('profile','auto'))
        self.assertEqual(obs['requested_minor'], v.input['minor'])
        self.assertEqual(obs['volume_information']['minor'], v.input['minor'])
        self.assertEqual(capture['retained_replays'], '2' if selected == '3.0' and row.get('profile','auto') == 'auto' else '1')
        self.assertFalse(result['authorizes_effects'] or result['product_dispatch_admitted'])
        self.assertFalse(obs['current_source_authority'] or obs['effects_authorized'] or obs['atomic_snapshot'])
        self.assertFalse(capture['atomic_snapshot'])
        self.assertEqual(capture['source_consistency'], 'live-uncoordinated')
        expected = v.initial_reads*2
        self.assertEqual([(int(r['offset']),int(r['requested'])) for r in value['regions']], expected)
        self.assertEqual(int(obs['read_requests']), len(expected))
        for region, (start, size) in zip(value['regions'], expected):
            self.assertTrue(region['seek_attempted'] and region['read_attempted'])
            self.assertEqual(region['error'], '0'); self.assertEqual(region['refusal'], '')
            self.assertEqual(bytes.fromhex(region['bytes']), bytes_at(v.input,start,size))
        return value

    def test_actual_profile_geometry_mapping_and_release(self):
        for minor in (0,1):
            for usa in (42,48):
                v,path = self.fixture(Volume(minor=minor,usa=usa,offset=173))
                for profile in ('auto','3.'+str(minor)):
                    value = self.good(v,path,dict(profile=profile,release_check=True))
                    self.assertTrue(all(r['opened'] for r in value['released_access']))
        for options in [dict(fragmented=False),dict(first_lcn=32,second_lcn=8),dict(sector=4096),dict(spc=8),dict(size=32768)]:
            v,path = self.fixture(Volume(**options)); self.good(v,path)
        v,path = self.fixture(name='ntfs-\u03bb.img'); self.good(v,path)

    def test_actual_source_bound_record_closures(self):
        from ntfs_closure_fixture import ClosureVolume
        from test_ntfs_closure import good
        for minor in (0,1):
            for nonresident in (False,True):
                v,path=self.fixture(ClosureVolume(minor=minor,offset=173,nonresident_list=nonresident,volume_nonresident=nonresident))
                value=self.good(v,path,dict(release_check=True));good(value['result']['observation'],v)
                self.assertTrue(all(r['opened'] for r in value['released_access']))
        v,path=self.fixture(ClosureVolume(cluster=512,offset=173,nonresident_list=True,volume_nonresident=True,padding=20))
        good(self.good(v,path)['result']['observation'],v)
        # Do not hash a multi-gigabyte sparse hole: check all fixture regions,
        # size and the existing before/final source generation instead.
        v,path=self.fixture(ClosureVolume(offset=(1<<32)+173,nonresident_list=True))
        size=path.stat().st_size
        value=run([self.row(v,path)])[0];good(value['result']['observation'],v)
        self.assertTrue(value['result']['capture']['observed_stable'])
        self.assertEqual(path.stat().st_size,size)
        with path.open('rb') as stream:
            for region in v.input['regions']:
                raw=bytes.fromhex(region['hex']);stream.seek(int(region['offset']))
                self.assertEqual(stream.read(len(raw)),raw)

    def test_profile_mismatch_unknown_and_no_native_retry(self):
        for minor in (0,1):
            v,path = self.fixture(Volume(minor=minor))
            values = self.preserve(path,[self.row(v,path,profile='3.'+str(1-minor))])
            obs = values[0]['result']['observation']; capture = values[0]['result']['capture']
            self.assertEqual(obs['diagnostic'],'ntfs_volume_version'); self.assertFalse(obs['applicable'])
            self.assertFalse(capture['observed_stable']); self.assertTrue(capture['replay_equal'])
            self.assertEqual(len(values[0]['regions']), len(v.initial_reads)*2)
        # Build the unsupported value directly rather than changing protected tails.
        from test_ntfs_attributes import resident
        info = resident(b'\0'*8+b'\x03\x02\0\0',kind=0x70)[0]
        v,path = self.fixture(Volume(info_payload=info))
        value = self.preserve(path,[self.row(v,path)])[0]
        self.assertIsNone(value['result']['capture']['selected_profile'])
        self.assertFalse(value['result']['observation']['applicable'])
        self.assertEqual(value['result']['observation']['volume_information']['minor'],'2')
        self.assertEqual(value['result']['observation']['binding_diagnostic'],'ntfs_file_profile_unresolved')

    def test_actual_native_offset_over4GiB(self):
        v,path = self.fixture(Volume(offset=(1<<32)+173))
        self.good(v,path)

    def test_expected_source_context_and_snapshot_before_callbacks(self):
        v,path = self.fixture(Volume(minor=0))
        before = self.good(v,path)['result']['capture']['source_before']
        self.good(v,path,dict(expected_source=before,mode='mutate_request'),True)
        wrong = dict(before,bytes='1')
        for mode in ('','mutate_request'):
            value = self.preserve(path,[self.row(v,path,expected_source=wrong,mode=mode,release_check=True)],True)[0]
            self.assertEqual(value['refusal'],'ntfs_file_source_changed')
            self.assertTrue(all(r['opened'] for r in value['released_access']))
        values = self.preserve(path,[self.row(v,path),self.row(v,path)])
        self.assertEqual(int(values[1]['result']['capture']['sequence']),int(values[0]['result']['capture']['sequence'])+1)

    def test_paths_windows_aliases_and_pre_read_refusals(self):
        v,path = self.fixture()
        cases = [(dict(profile='unknown'),'ntfs_file_profile'),(dict(length=str(1<<63)),'ntfs_file_seek_range'),
                 (dict(offset=str(1<<63)),'ntfs_file_seek_range'),(dict(length='511'),'ntfs_capture_inputs'),
                 (dict(length=str(path.stat().st_size+1)),'ntfs_capture_window'),
                 (dict(limits={'read_requests':'0'}),'ntfs_capture_limits'),(dict(expected_source=[]),'ntfs_file_expected_source'),
                 (dict(path=str(path)+':stream'),'image_path_profile'),(dict(path='NUL'),'image_path_profile'),
                 (dict(path='\\\\.\\PhysicalDrive0'),'image_path_profile'),(dict(path='\\\\server\\share\\x.img'),'image_path_profile'),
                 (dict(path=str(self.root/'absent.img')),'ntfs_file_open'),(dict(path=str(self.root)),'image_file_type')]
        rows=[]
        for extra,_ in cases:
            row=self.row(v,path);row.update(extra);rows.append(row)
        values=self.preserve(path,rows)
        for value,(_,expected) in zip(values,cases):self.assertEqual(value['refusal'],expected,value)
        alias=self.root/'hardlink.img';os.link(path,alias)
        try:self.assertEqual(self.preserve(path,[self.row(v,path)])[0]['refusal'],'image_file_aliases')
        finally:alias.unlink()
        folder=self.root/'target';folder.mkdir();moved=folder/'source.img';path.rename(moved)
        junction=self.root/'junction'
        result=subprocess.run(['cmd','/c','mklink','/J',str(junction),str(folder)],capture_output=True)
        if result.returncode:
            UNVERIFIED.append(dict(check='parent-junction',reason=result.stderr.decode(errors='replace')))
        else:
            try:
                self.assertEqual(self.preserve(moved,[self.row(v,junction/'source.img')])[0]['refusal'],'image_reparse_source')
                self.assertEqual(self.preserve(moved,[self.row(v,junction)])[0]['refusal'],'image_reparse_source')
            finally:os.rmdir(junction)
        link=self.root/'leaf.img'
        try:os.symlink(moved,link)
        except OSError as error:UNVERIFIED.append(dict(check='actual-file-symlink',reason=str(error)))
        else:
            try:self.assertEqual(self.preserve(moved,[self.row(v,link)])[0]['refusal'],'image_reparse_source')
            finally:link.unlink()

    def test_native_prefix_failures_and_sticky_cancellation(self):
        v,path=self.fixture()
        for mode,code in [('short','ntfs_read_length'),('error','ntfs_reader_failure'),('partial_error','ntfs_reader_failure'),('throw','ntfs_reader_failure'),
                          ('read_throw','ntfs_reader_failure'),('changed','ntfs_source_changed')]:
            call=2 if mode!='changed' else len(v.initial_reads)+1
            value=self.preserve(path,[self.row(v,path,mode=mode,call=str(call))],True)[0]
            self.assertFalse(value['result']['observation']['applicable'])
            self.assertEqual(value['result']['observation']['diagnostic'],code)
            self.assertTrue(value['result']['capture']['replay_equal'])
            self.assertEqual(len(value['regions']),call)
            if mode=='partial_error':
                self.assertTrue(0 < len(bytes.fromhex(value['regions'][-1]['bytes'])) < int(value['regions'][-1]['requested']))
        for mode in ('cancel','cancel_once','cancel_throw','binding','binding_throw'):
            for call in (1,3):
                value=self.preserve(path,[self.row(v,path,mode=mode,call=str(call),release_check=True)],True)[0]
                self.assertTrue(all(r['opened'] for r in value['released_access']))
                if call==1:self.assertIn('refusal',value);continue
                capture=value['result']['capture'];self.assertFalse(capture['binding_checks_ok'] or capture['observed_stable'])
                self.assertTrue(capture['binding_error'])
                self.assertFalse(value['result']['observation']['applicable'])
                self.assertEqual(len(value['regions']),1)
                self.assertTrue(value['regions'][0]['read_attempted'])
        normal=self.good(v,path)
        total=int(normal['result']['capture']['binding_checks'])
        for mode in ('cancel','binding'):
            value=self.preserve(path,[self.row(v,path,mode=mode,call=str(total))],True)[0]
            self.assertFalse(value['result']['observation']['applicable'])
            self.assertTrue(value['result']['observation']['complete'])
            self.assertTrue(value['result']['capture']['replay_equal'])

    def test_metadata_profile_and_replay_disagreements(self):
        for minor in (0,1):
            v,path=self.fixture(Volume(minor=minor))
            for mode in ('metadata','metadata_throw','replay_bytes','replay_offset','replay_provenance','replay_throw'):
                value=self.preserve(path,[self.row(v,path,mode=mode,call='1')],True)[0]
                capture=value['result']['capture'];obs=value['result']['observation']
                self.assertFalse(capture['observed_stable'] or obs['applicable'])
                self.assertIn('binding_diagnostic',obs)
                if mode.startswith('replay_'):
                    self.assertFalse(capture['replay_equal'] if minor else capture['profile_selection_equal'])
                if mode=='metadata':self.assertFalse(capture['metadata_equal'])
                if mode=='metadata_throw':self.assertFalse(capture['binding_checks_ok'])

    def test_held_native_access_and_release(self):
        v,path=self.fixture(name='owned/inner/source.img')
        value=self.good(v,path,dict(mode='held_access',call='1',release_check=True,
                                   access_parents=[str(path.parent),str(path.parent.parent)]),True)
        for row in value['held_access']:
            self.assertFalse(row[0]['opened'] or row[1]['opened'] or row[2]['moved'],row)
            self.assertTrue(all(int(item['error']) for item in row))
        self.assertTrue(all(row['opened'] for row in value['released_access']))
        self.assertTrue(all(row['opened'] for group in value['released_parent_access'] for row in group))

    def test_normal_ignores_fault_protocol(self):
        v,path=self.fixture(Volume(minor=0))
        env=dict(os.environ,DISKED_NTFS_FILE_TEST_MODE='error',DISKED_NTFS_FILE_FAULT='1')
        value=self.preserve(path,[self.row(v,path,mode='cancel',call='1')],False,env)[0]
        self.assertTrue(value['result']['observation']['applicable'])
        self.assertEqual(value['stop_calls'],'0')


def main():
    global PROBE,FAULT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe',type=Path,required=True);parser.add_argument('--fault',type=Path,required=True)
    parser.add_argument('--output',type=Path);args=parser.parse_args()
    PROBE=args.probe.resolve();FAULT=args.fault.resolve()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    summary=dict(cases=len(RECEIPTS),methods=result.testsRun,failures=len(result.failures),errors=len(result.errors),
                 receipts=RECEIPTS,unverified=UNVERIFIED,path_binding=BINDING_OBSERVATIONS,
                 scope='Generated Windows ordinary-file NTFS bootstrap only; no public/physical/full-product admission.')
    if args.output:args.output.write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__=='__main__':main()
