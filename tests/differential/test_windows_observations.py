"""Independent synthetic controls for requests and SDK-byte binding, not Windows evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import unittest

from windows_observations import api_projection, native_expectations, request, matching_candidates

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('windows_observation_fixtures',ROOT/'tests/corpus/windows_partitions.py')
fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
ABI=dict(layout_entries_offset=48,partition_bytes=144,query_controls=dict(length=0x7405c,geometry=0x700a0,device=0x2d1080,layout=0x70050))


def synthetic_api():
    # Independently laid-out SDK Win64 bytes. No query or process is executed.
    raw=bytearray(48+4*144);struct.pack_into('<III',raw,0,0,4,0xd15ced01)
    rows=[]
    for index in range(4):
        offset,length,kind=(2048*512,1024*512,7) if index==0 else (4096*512,1024*512,0x83) if index==1 else (0,0,0)
        start=48+144*index
        # The first q is aligned to8, not packed immediately after the DWORD.
        struct.pack_into('<I',raw,start,0);struct.pack_into('<qqI',raw,start+8,offset,length,index+1)
        raw[start+32]=kind
        rows.append(dict(index=index,style=0,number=index+1,offset_bytes=str(offset),length_bytes=str(length),
                         rewrite_partition=False,type=kind,boot_indicator=False,recognized=False,hidden_sectors=0))
    geometry=bytearray(32);struct.pack_into('<I',geometry,20,512);struct.pack_into('<q',geometry,24,4194304)
    def query(name,data):return dict(control=ABI['query_controls'][name],success=True,winerror=0,returned_bytes=len(data),raw_hex=bytes(data).hex())
    return dict(handle_inheritable=False,write_denied=True,write_success=False,write_bytes=0,write_winerror=5,
                queries=dict(length=query('length',struct.pack('<q',4194304)),geometry=query('geometry',geometry),
                             device=query('device',struct.pack('<III',7,3,0xffffffff)),layout=query('layout',raw)),
                disk_bytes='4194304',geometry_disk_bytes='4194304',sector_bytes=512,device_type=7,device_number=3,
                partition_number=0xffffffff,style=0,partition_count=4,disk_signature=0xd15ced01,partitions=rows)


class WindowsObservationTests(unittest.TestCase):
    def test_mbr_request_is_one_sector_with_exact_full_geometry(self):
        body=fixtures.generate('mbr-valid');value=request(body,fixtures.describe('mbr-valid'))
        self.assertEqual('8192',value['blocks']);self.assertEqual({'0':body[:512].hex()},value['image'])
        self.assertLess(len(json.dumps(value)),2048)

    def test_gpt_requests_have_two_independent_bounded_arrays(self):
        body=fixtures.generate('gpt-conflicting');value=request(body,fixtures.describe('gpt-conflicting'))
        self.assertEqual('8192',value['blocks'])
        self.assertEqual(16384,len(bytes.fromhex(value['primary_array'])))
        self.assertEqual(16384,len(bytes.fromhex(value['backup_array'])))
        self.assertEqual(2048,struct.unpack_from('<Q',bytes.fromhex(value['primary_array']),32)[0])
        self.assertEqual(2049,struct.unpack_from('<Q',bytes.fromhex(value['backup_array']),32)[0])
        self.assertLess(len(json.dumps(value)),131072)

    def test_changed_fixture_cannot_generate_a_request(self):
        body=bytearray(fixtures.generate('mbr-valid'));body[0]^=1
        with self.assertRaisesRegex(ValueError,'identity'):request(bytes(body),fixtures.describe('mbr-valid'))

    def test_expectations_retain_damaged_primary_and_two_valid_conflicting_copies(self):
        conflict=native_expectations(fixtures.describe('gpt-conflicting'))
        self.assertEqual(2,conflict['comparison']);self.assertEqual('2048',conflict['copies.0.candidate.entries.0.first'])
        self.assertEqual('2049',conflict['copies.1.candidate.entries.0.first'])
        damaged=native_expectations(fixtures.describe('gpt-primary-damaged'))
        self.assertEqual(16,damaged['copies.0.header.issues']);self.assertEqual(0,damaged['copies.1.header.issues'])

    def test_raw_mbr_normalization_preserves_exact_extents(self):
        value=api_projection(synthetic_api(),ABI)
        self.assertEqual(dict(label='dos',rows=[dict(start=2048,end=3072,type='7'),dict(start=4096,end=5120,type='83')]),value)

    def test_rehashed_or_plausible_parsed_values_cannot_override_raw_bytes(self):
        value=synthetic_api();value['partitions'][0]['offset_bytes']=str(2049*512)
        with self.assertRaisesRegex(ValueError,'raw contradiction'):api_projection(value,ABI)

    def test_real_refusal_has_no_invented_projection(self):
        value=synthetic_api();value['queries']['layout']=dict(control=0x70050,success=False,winerror=5,returned_bytes=0,raw_hex='')
        self.assertIsNone(api_projection(value,ABI))

    def test_empty_raw_or_invalid_copy_is_not_a_matching_gpt_candidate(self):
        native=dict(label='gpt',comparison=0,candidates=[dict(role='primary',rows=[],header_issues=16,
            array_issues=None,complete=False,consistent=False)])
        self.assertEqual([],matching_candidates(native,dict(label='raw',rows=[])))
        self.assertEqual([],matching_candidates(native,dict(label='gpt',rows=[])))

    def test_reference_match_preserves_both_conflicting_candidates(self):
        native=dict(label='gpt',comparison=2,candidates=[dict(role=role,rows=[dict(start=start,end=3072,type='test')],
            header_issues=0,array_issues=0,complete=True,consistent=True) for role,start in [('primary',2048),('backup',2049)]])
        before=copy.deepcopy(native)
        self.assertEqual(['primary'],matching_candidates(native,dict(label='gpt',rows=[dict(start=2048,end=3072,type='test')])))
        self.assertEqual(before,native);self.assertEqual(2,len(native['candidates']))

    def test_contradictory_geometry_or_write_access_never_qualifies(self):
        for mode in ('geometry','write','count','raw-size'):
            value=synthetic_api()
            if mode=='geometry':value['sector_bytes']=4096
            elif mode=='write':value['write_denied']=False
            elif mode=='count':value['partition_count']=3
            else:value['queries']['layout']['returned_bytes']+=1
            with self.subTest(mode=mode),self.assertRaises(ValueError):api_projection(value,ABI)


if __name__=='__main__':unittest.main()
