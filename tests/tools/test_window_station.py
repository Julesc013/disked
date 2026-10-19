"""Pure exact-subject station ACL deltas; no host user-object access."""
import importlib.util
from pathlib import Path
import struct
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('station_delta',ROOT/'.aide/evidence/2026-10-18-ordinary-worker/window-station.py')
S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)

def sid(number):return bytes([1,2,0,0,0,0,0,5])+struct.pack('<II',21,number)
def ace(number,flags=0,mask=3):return struct.pack('<BBHI',0,flags,8+len(sid(number)),mask)+sid(number)
def acl(rows):
    data=b''.join(rows);return struct.pack('<BBHHH',2,0,8+len(data),len(rows),0)+data

class StationDeltaTests(unittest.TestCase):
    def test_own_delta_preserves_inherited_and_unrelated_ace_bytes(self):
        before=acl([ace(1,4),ace(2,11),ace(3,19)])
        applied=S.add_subject(before,sid(8))
        self.assertEqual(S.aces(applied)[:-1],S.aces(before))
        # A concurrent unrelated addition must survive exact-subject retirement.
        current=acl(S.aces(applied)+[ace(9,4)])
        retired,count=S.remove_subject(current,sid(8))
        self.assertEqual(count,1)
        self.assertEqual(S.aces(retired),S.aces(before)+[ace(9,4)])
        self.assertEqual(S.remove_subject(retired,sid(8)),(retired,0))

    def test_existing_changed_or_duplicate_subject_is_refused(self):
        for rows in ([ace(8)], [S.owned_ace(sid(8)),S.owned_ace(sid(8))]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):S.add_subject(acl(rows),sid(8))
        for rows in ([ace(8)], [S.owned_ace(sid(8)),S.owned_ace(sid(8))]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):S.remove_subject(acl(rows),sid(8))

    def test_truncation_unknown_flags_and_ace_types_are_refused(self):
        original=acl([ace(1)])
        invalid=bytearray(original);invalid[8]=5
        for value in (original[:-1],acl([ace(1,32)]),bytes(invalid)):
            with self.subTest(value=value),self.assertRaises(ValueError):S.aces(value)

    def test_minimal_declared_mask_excludes_shared_desktop_authority(self):
        self.assertEqual(struct.unpack_from('<I',S.owned_ace(sid(8)),4)[0],0x2012b)
        for forbidden in (0x10000,0x40000,0x80000,4,0x10,0x40,0x200):
            self.assertEqual(S.MASK&forbidden,0)

if __name__=='__main__':unittest.main()
