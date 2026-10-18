"""Independent header/FSInfo/backup and ordinary-file preservation fixtures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from support.tempdir import fixture_parent,managed_directory
import struct
import unittest

import test_fat_capture as capture
from test_fat_capture import Volume, MASKS
from test_fat import packed

UNKNOWN=0xffffffff

def fsinfo(unit=512,count=UNKNOWN,hint=UNKNOWN):
    raw=bytearray(unit)
    struct.pack_into('<I',raw,0,0x41615252);struct.pack_into('<I',raw,484,0x61417272)
    struct.pack_into('<II',raw,488,count,hint);struct.pack_into('<I',raw,508,0xaa550000)
    if unit>512:raw[512:]=b'P'*(unit-512)
    return bytes(raw)

class MetadataVolume(Volume):
    def __init__(self,bits=32,unit=512,offset=0,count=UNKNOWN,hint=UNKNOWN):
        super().__init__(bits,unit=unit,offset=offset)
        if bits==32:
            self.regions[unit]=fsinfo(unit,count,hint);self.regions[2*unit]=b'B'*unit
            self.regions[6*unit]=bytes(self.boot);self.regions[7*unit]=fsinfo(unit,count,hint)
            self.regions[8*unit]=b'B'*unit
    def refs(self,info=1,backup=6):
        struct.pack_into('<HH',self.boot,48,info,backup)
        self.regions[0]=bytes(self.boot)
        if backup not in (0,65535):self.regions[backup*self.unit]=bytes(self.boot)
    def observe_request(self,scan=False,**limits):
        request=self.request();request.update(auxiliary_checks=True,allocation_scan=scan)
        if limits:request['limits']={k:str(v) for k,v in limits.items()}
        return request

def report(volume,scan=False,**limits):
    value,calls=capture.report(volume.observe_request(scan,**limits))
    return value,value['auxiliary_checks'],calls

def diagnostic(aux,code):return code in aux['diagnostics']

class AuxiliaryTests(unittest.TestCase):
    def test_header_media_status_flags_and_raw_high_bits(self):
        requests=[];expected=[]
        for bits in (12,16,32):
            mask=MASKS[bits]
            for media in [0xf0,*range(0xf8,0x100)]:
                for flags in ([3] if bits==12 else range(4)):
                    one=mask if bits==12 else (mask & ~({16:0xc000,32:0x0c000000}[bits])) | (flags&1)*({16:0x8000,32:0x08000000}[bits]) | ((flags>>1)&1)*({16:0x4000,32:0x04000000}[bits])
                    zero=(mask & ~255)|media
                    if bits==32:zero|=0xa0000000;one|=0xb0000000
                    raw=packed(bits,{0:zero,1:one})
                    requests.append(dict(op='header',raw=raw.hex(),bits=str(bits),media=str(media)))
                    expected.append((bits,flags,zero&mask,one&mask))
        for row,(bits,flags,zero,one) in zip(capture.run(requests),expected):
            self.assertEqual(row['status'],'0');self.assertEqual(row['issues'],'0')
            self.assertTrue(row['fields_present']);self.assertEqual(int(row['zero']),zero);self.assertEqual(int(row['one']),one)
            self.assertEqual(row['flags_supported'],bits!=12)
            if bits!=12:self.assertEqual(row['clean_shutdown'],bool(flags&1));self.assertEqual(row['no_io_error'],bool(flags&2))
            if bits==32:self.assertGreater(int(row['raw_one']),MASKS[32])

    def test_header_shapes_short_overlong_null_and_invalid_type(self):
        for bits in (12,16,32):
            raw=packed(bits,{0:MASKS[bits]&~255|0xf8,1:MASKS[bits]})
            rows=capture.run([dict(op='header',raw=raw[:n].hex(),bits=str(bits),media='248') for n in range(len(raw))])
            for row in rows:self.assertEqual(row['status'],'0');self.assertFalse(row['fields_present']);self.assertEqual(int(row['issues'])&1,1)
            base=dict(op='header',raw=raw.hex(),bits=str(bits),media='248')
            invalid=[dict(base,raw=(raw+b'x').hex()),dict(base,null=True),dict(base,bits='8')]
            self.assertTrue(all(r['status']!='0' for r in capture.run(invalid)))
            bad=packed(bits,{0:0,1:0});row=capture.run([dict(base,raw=bad.hex(),media='1')])[0]
            self.assertEqual(int(row['issues']),2|4|8)

    def test_fsinfo_unknown_known_sector_units_and_opaque_padding(self):
        requests=[];expected=[]
        for unit in (512,1024,2048,4096):
            for count,hint in ((UNKNOWN,UNKNOWN),(0,2),(65525,65526),(123,37)):
                requests.append(dict(op='fsinfo',raw=fsinfo(unit,count,hint).hex(),unit=str(unit),clusters='65525'))
                expected.append((count,hint))
        for row,(count,hint) in zip(capture.run(requests),expected):
            self.assertEqual(row['status'],'0');self.assertEqual(row['issues'],'0');self.assertTrue(row['fields_present'])
            self.assertEqual(row['free_count'],str(count));self.assertEqual(row['next_free'],str(hint))
            self.assertEqual(row['free_count_known'],count!=UNKNOWN);self.assertEqual(row['next_free_known'],hint!=UNKNOWN)

    def test_fsinfo_signatures_reserved_ranges_and_short_prefix(self):
        rows=[];expected=[]
        for at in (0,484,508):
            raw=bytearray(fsinfo());raw[at]^=1;rows.append(dict(op='fsinfo',raw=raw.hex(),unit='512',clusters='65525'));expected.append(2)
        for at in (4,483,496,507):
            raw=bytearray(fsinfo());raw[at]=1;rows.append(dict(op='fsinfo',raw=raw.hex(),unit='512',clusters='65525'));expected.append(4)
        for count,hint in ((65526,UNKNOWN),(UNKNOWN,0),(UNKNOWN,1),(UNKNOWN,65527)):
            rows.append(dict(op='fsinfo',raw=fsinfo(count=count,hint=hint).hex(),unit='512',clusters='65525'));expected.append(8 if count!=UNKNOWN else 16)
        for row,issues in zip(capture.run(rows),expected):self.assertEqual(int(row['issues']),issues)
        for n in (0,1,483,484,488,492,508,511,512):
            row=capture.run([dict(op='fsinfo',raw=fsinfo()[:n].hex(),unit='4096',clusters='65525')])[0]
            self.assertEqual(row['status'],'0');self.assertEqual(row['issues'],'1');self.assertEqual(row['fields_present'],n>=512)
        bad=[dict(op='fsinfo',raw=fsinfo().hex(),unit='513',clusters='65525'),dict(op='fsinfo',raw=fsinfo().hex(),unit='512',clusters='65524'),
             dict(op='fsinfo',raw=fsinfo().hex(),unit='512',clusters='268435446'),dict(op='fsinfo',raw=(fsinfo()+b'x').hex(),unit='512',clusters='65525'),
             dict(op='fsinfo',raw=fsinfo().hex(),unit='512',clusters='65525',null=True)]
        self.assertTrue(all(r['status']!='0' for r in capture.run(bad)))

    def test_complete_metadata_all_formats_and_sector_sizes(self):
        for bits in (12,16,32):
            for unit in (512,1024,2048,4096):
                volume=MetadataVolume(bits,unit,offset=17);value,aux,calls=report(volume)
                self.assertTrue(aux['coverage_complete']);self.assertTrue(aux['metadata_agreement']);self.assertFalse(aux['needs_attention'])
                self.assertTrue(value['selected_tree_complete']);self.assertTrue(value['observed_metadata_consistent'])
                self.assertEqual(len(aux['headers']),2);self.assertTrue(aux['header_comparison_complete'])
                if bits==32:
                    self.assertTrue(aux['backup']['record_exact_equal']);self.assertTrue(aux['backup']['record_structural_equal'])
                    self.assertEqual(len(aux['backup']['records']),3);self.assertFalse(aux['fsinfo']['count_comparison_applicable'])
                else:self.assertEqual(aux['fsinfo']['status'],'not_applicable');self.assertEqual(aux['backup']['status'],'not_applicable')
                for row in calls:self.assertLessEqual(int(row['bytes']),4096);self.assertGreaterEqual(int(row['offset']),volume.offset)
                self.assertFalse(value['filesystem_health_qualified'])

    def test_recorded_dirty_and_io_flags_are_not_shape_failures(self):
        for bits in (16,32):
            for flags in range(4):
                volume=MetadataVolume(bits);mask=MASKS[bits];both={16:0xc000,32:0x0c000000}[bits]
                clean={16:0x8000,32:0x08000000}[bits];error=clean>>1
                volume.link(1,(mask&~both)|(clean if flags&1 else 0)|(error if flags&2 else 0))
                value,aux,_=report(volume)
                self.assertTrue(aux['metadata_agreement']);self.assertEqual(aux['needs_attention'],flags!=3)
                self.assertTrue(value['observed_metadata_consistent']);self.assertEqual(aux['headers'][0]['issues'],'0')
        volume=MetadataVolume();volume.boot[21]=1;volume.regions[0]=bytes(volume.boot)
        value,aux,_=report(volume);self.assertFalse(aux['metadata_agreement']);self.assertTrue(diagnostic(aux,'fat_header_shape'))
        self.assertTrue(value['selected_tree_complete']);self.assertFalse(value['observed_metadata_consistent'])

    def test_absent_references_and_nonconventional_locations(self):
        volume=MetadataVolume();volume.refs(65535,0);value,aux,calls=report(volume)
        self.assertEqual(aux['fsinfo']['status'],'absent');self.assertEqual(aux['backup']['status'],'absent')
        self.assertTrue(aux['metadata_agreement']);self.assertFalse(any(int(c['offset']) in (512,3072) for c in calls))
        volume=MetadataVolume();volume.regions[3*512]=fsinfo();volume.refs(3,6)
        _,aux,_=report(volume);self.assertFalse(aux['metadata_agreement']);self.assertFalse(aux['backup']['shadow_location_known'])
        self.assertTrue(diagnostic(aux,'fat_fsinfo_nonconventional_placement'))
        volume=MetadataVolume();volume.refs(1,29);volume.regions[30*512]=fsinfo();volume.regions[31*512]=b'B'*512
        _,aux,_=report(volume);self.assertTrue(diagnostic(aux,'fat_backup_nonconventional_placement'));self.assertTrue(aux['backup']['record_structural_equal'])

    def test_backup_structural_conflicts_and_stale_advisory_shadow(self):
        volume=MetadataVolume(count=65524,hint=3);volume.regions[7*512]=fsinfo(count=100,hint=40)
        _,aux,_=report(volume,scan=True)
        self.assertTrue(aux['fsinfo']['free_count_matches']);self.assertTrue(aux['fsinfo']['next_free_is_free'])
        self.assertFalse(aux['backup']['advisory_hints_equal']);self.assertFalse(aux['backup']['record_exact_equal'])
        self.assertTrue(aux['backup']['record_structural_equal']);self.assertTrue(aux['metadata_agreement'])
        for at in (11,67,90):
            volume=MetadataVolume();raw=bytearray(volume.regions[6*512]);raw[at]^=1;volume.regions[6*512]=bytes(raw)
            value,aux,_=report(volume);self.assertFalse(aux['metadata_agreement']);self.assertFalse(aux['backup']['record_structural_equal'])
            self.assertTrue(value['selected_tree_complete']);self.assertFalse(value['observed_metadata_consistent'])
        volume=MetadataVolume();raw=bytearray(volume.regions[7*512]);raw[4]=1;volume.regions[7*512]=bytes(raw)
        _,aux,_=report(volume);self.assertTrue(diagnostic(aux,'fat_backup_fsinfo_shape'))
        volume=MetadataVolume();volume.regions[8*512]=b'D'*512
        _,aux,_=report(volume);self.assertTrue(diagnostic(aux,'fat_backup_record_disagreement'))

    def test_hint_and_count_comparison_applicability(self):
        volume=MetadataVolume(count=100,hint=2);value,aux,_=report(volume,scan=True)
        self.assertTrue(aux['fsinfo']['count_comparison_applicable']);self.assertFalse(aux['fsinfo']['free_count_matches'])
        self.assertFalse(aux['fsinfo']['next_free_is_free']);self.assertTrue(diagnostic(aux,'fat_fsinfo_next_not_free'))
        self.assertTrue(value['allocation_scan']['coverage_complete']);self.assertTrue(value['selected_tree_complete'])
        _,aux,_=report(MetadataVolume(count=65524,hint=3),scan=True,allocation_clusters=10)
        self.assertFalse(aux['fsinfo']['count_comparison_applicable']);self.assertIsNone(aux['fsinfo']['free_count_matches'])
        volume=MetadataVolume(count=65524,hint=3);volume.link(3,MASKS[32],copy_index=1)
        _,aux,_=report(volume,scan=True);self.assertFalse(aux['fsinfo']['count_comparison_applicable'])
        self.assertFalse(aux['fsinfo']['next_free_copies_agree']);self.assertTrue(diagnostic(aux,'fat_fsinfo_next_copy_disagreement'))
        volume=MetadataVolume(count=65526,hint=3);_,aux,_=report(volume)
        self.assertTrue(diagnostic(aux,'fat_fsinfo_shape'));self.assertIsNone(aux['fsinfo']['next_free_is_free'])

    def test_reference_bounds_and_backup_record_limit(self):
        for info,bak in ((0,6),(32,6),(1,32),(6,6)):
            volume=MetadataVolume();volume.refs(info,bak);value,aux,calls=report(volume)
            self.assertFalse(value['geometry']['usable_layout']);self.assertEqual(aux['status'],'not_observed')
            self.assertEqual(len(calls),1)
        volume=MetadataVolume();volume.refs(1,31);value,aux,calls=report(volume)
        self.assertEqual(aux['backup']['status'],'invalid_record_extent');self.assertFalse(aux['coverage_complete'])
        self.assertFalse(any(int(c['offset'])==31*512 and int(c['bytes'])==512 for c in calls))
        self.assertTrue(value['selected_tree_complete'])

    def test_callback_failures_and_combined_budgets_preserve_prior_results(self):
        volume=MetadataVolume();value,aux,calls=report(volume,scan=True)
        plain=volume.request();plain['allocation_scan']=True;base,base_calls=capture.report(plain)
        requests=[]
        for n in range(len(base_calls)+1,len(calls)+1):
            for kind in ('short','null','oversized','throw','change'):
                r=volume.observe_request(True);r['fault']=dict(call=str(n),kind=kind);requests.append(r)
        for supplied,row in zip(requests,capture.run(requests)):
            value=row['report'];self.assertTrue(value['selected_tree_complete']);self.assertTrue(value['allocation_scan']['coverage_complete'])
            self.assertFalse(value['observed_metadata_consistent'])
            if supplied['fault']['kind']!='change':self.assertFalse(value['auxiliary_checks']['coverage_complete'])
            self.assertTrue(value['auxiliary_checks']['diagnostics'])
            if not value['reads']['overlap_equal']:
                self.assertFalse(value['allocation_scan']['unreferenced_allocation_qualified'])
        for limits in ({'read_requests':len(base_calls)},{'read_bytes':sum(int(c['bytes']) for c in base_calls)}):
            value,aux,_=report(volume,scan=True,**limits);self.assertTrue(value['allocation_scan']['coverage_complete'])
            self.assertTrue(value['selected_tree_complete']);self.assertFalse(aux['coverage_complete'])
        value,aux,_=report(MetadataVolume(unit=4096),output_bytes=131072)
        self.assertTrue(aux['coverage_complete']);self.assertLessEqual(len(json.dumps(value,separators=(',',':')).encode()),131072)
        r=volume.observe_request(output_bytes=131071);row=capture.run([r])[0];self.assertIn('error',row);self.assertEqual(row['calls'],[])

    def test_partial_tree_does_not_supply_health_or_count_authority(self):
        volume=MetadataVolume();volume.chain([3]);volume.directory([bytes(capture.short(cluster=3,size=1))])
        value,aux,_=report(volume,scan=True,nodes=1)
        self.assertFalse(value['selected_tree_complete']);self.assertFalse(value['observed_metadata_consistent'])
        self.assertTrue(value['allocation_scan']['coverage_complete']);self.assertFalse(value['allocation_scan']['tree_ownership_complete'])
        self.assertTrue(aux['coverage_complete']);self.assertTrue(aux['metadata_agreement'])
        self.assertFalse(aux['fsinfo']['count_comparison_applicable']);self.assertFalse(value['filesystem_health_qualified'])

    def test_default_mode_and_wide_source_window(self):
        volume=MetadataVolume(offset=2**48+33);plain,_=capture.report(volume.request())
        r=volume.request();r['auxiliary_checks']=False;disabled,_=capture.report(r)
        self.assertEqual(plain,disabled);self.assertNotIn('auxiliary_checks',plain)
        value,aux,calls=report(volume);self.assertTrue(aux['metadata_agreement'])
        self.assertTrue(all(int(c['offset'])>=volume.offset for c in calls));self.assertEqual(value['volume_offset'],str(volume.offset))

    def test_ordinary_file_preservation_and_recapture_controls(self):
        root=fixture_parent()
        self.assertTrue(root.resolve().is_relative_to(Path(os.environ['DISKED_WORK_ROOT']).resolve()))
        with managed_directory(prefix='fataux-') as folder:
            self.assertTrue(Path(folder).resolve().is_relative_to(root.resolve()))
            for bits in (12,16,32):
                volume=MetadataVolume(bits,offset=512);path=Path(folder)/f'{bits}.img';volume.write(path)
                before=hashlib.sha256(path.read_bytes()).hexdigest()
                request=dict(op='file',path=str(path),offset='512',length=str(volume.length),copy='0',auxiliary_checks=True,allocation_scan=True)
                v=capture.run([request])[0]['result'];self.assertTrue(v['capture']['observed_stable'])
                self.assertTrue(v['observation']['auxiliary_checks']['metadata_agreement'])
                for flag in ('DISKED_FAT_TEST_VERIFY_CHANGED','DISKED_FAT_TEST_VERIFY_ERROR','DISKED_FAT_TEST_METADATA_CHANGED'):
                    env=os.environ.copy();env[flag]='1'
                    bad=capture.run([request],probe=capture.FAULT_PROBE,environment=env)[0]['result']
                    good=capture.run([request],environment=env)[0]['result']
                    self.assertFalse(bad['capture']['observed_stable']);self.assertTrue(good['capture']['observed_stable'])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)
                refused=capture.run([dict(request,copy=str(2**32))])[0]
                self.assertIn('error',refused);self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--probe',type=Path,required=True)
    parser.add_argument('--fault-probe',type=Path,required=True);parser.add_argument('--output',type=Path);args=parser.parse_args()
    capture.PROBE=args.probe.resolve();capture.FAULT_PROBE=args.fault_probe.resolve()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AuxiliaryTests))
    if args.output:args.output.write_text(json.dumps(dict(tests_run=result.testsRun,passed=result.wasSuccessful(),
        cases=sum(r['cases'] for r in capture.RECEIPTS),batches=capture.RECEIPTS),indent=2)+'\n',encoding='utf-8',newline='\n')
    print('FAT auxiliary cases executed: '+str(sum(r['cases'] for r in capture.RECEIPTS)),flush=True)
    raise SystemExit(0 if result.wasSuccessful() else 1)

if __name__=='__main__':main()
