"""Adverse ACL deltas for the private guest setup candidate; no OS mutation."""
import importlib.util
from pathlib import Path
import struct
import unittest

ROOT=Path(__file__).resolve().parents[2]
definition=importlib.util.spec_from_file_location('crypto_candidate',ROOT/'.aide/evidence/2026-10-18-ordinary-worker/crypto-device.py')
candidate=importlib.util.module_from_spec(definition);definition.loader.exec_module(candidate)

def sid(number):return b'\x01\x01\x00\x00\x00\x00\x00\x05'+struct.pack('<I',number)
def entry(subject,mask=1,kind=0):return struct.pack('<BBHI',kind,0,8+len(subject),mask)+subject
def acl(*items):return struct.pack('<BBHHH',2,0,8+sum(map(len,items)),len(items),0)+b''.join(items)

class CryptoAclCandidateTests(unittest.TestCase):
    def test_exact_subject_roundtrip_preserves_unrelated_allow_and_deny(self):
        original=acl(entry(sid(18),0x1f01ff),entry(sid(32),2,1),entry(sid(11),1))
        granted=candidate.add_subject(original,sid(1001))
        self.assertEqual(candidate.aces(granted)[:-1],candidate.aces(original))
        restored,count=candidate.remove_subject(granted,sid(1001))
        self.assertEqual((restored,count),(original,1))

    def test_retirement_preserves_concurrently_added_unrelated_entry(self):
        first=candidate.add_subject(acl(entry(sid(18))),sid(1001))
        changed=candidate.packed_acl(first,candidate.aces(first)+[entry(sid(2002),0x12)])
        restored,count=candidate.remove_subject(changed,sid(1001))
        self.assertEqual(count,1)
        self.assertEqual(restored,acl(entry(sid(18)),entry(sid(2002),0x12)))

    def test_absent_subject_retirement_is_idempotent(self):
        original=acl(entry(sid(18)))
        self.assertEqual(candidate.remove_subject(original,sid(1001)),(original,0))

    def test_existing_subject_is_never_upgraded(self):
        with self.assertRaisesRegex(ValueError,'already'):candidate.add_subject(acl(entry(sid(1001))),sid(1001))

    def test_changed_subject_mask_is_not_deleted(self):
        with self.assertRaisesRegex(ValueError,'changed'):candidate.remove_subject(acl(entry(sid(1001),2)),sid(1001))

    def test_duplicate_owned_entry_is_not_deleted(self):
        own=candidate.owned_ace(sid(1001))
        with self.assertRaisesRegex(ValueError,'duplicated'):candidate.remove_subject(acl(own,own),sid(1001))

    def test_subject_deny_entry_is_not_deleted(self):
        with self.assertRaises(ValueError):candidate.remove_subject(acl(entry(sid(1001),candidate.MASK,1)),sid(1001))

    def test_truncated_declared_acl_and_ace_are_refused(self):
        raw=acl(entry(sid(18)))
        for changed in (raw[:-1],raw[:10],raw[:8]+raw[8:10]+b'\xff\x7f'+raw[12:]):
            with self.subTest(value=changed),self.assertRaises(ValueError):candidate.aces(changed)

    def test_object_or_inherited_ace_is_refused(self):
        raw=bytearray(acl(entry(sid(18))))
        for field,value in ((8,5),(9,0x10)):
            changed=bytearray(raw);changed[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):candidate.aces(bytes(changed))

    def test_unknown_revision_and_nonzero_padding_are_refused(self):
        original=acl(entry(sid(18)));changed=bytearray(original);changed[0]=3
        with self.assertRaises(ValueError):candidate.aces(bytes(changed))
        padded=struct.pack('<BBHHH',2,0,len(original)+4,1,0)+original[8:]+b'\0\0\0\x01'
        with self.assertRaises(ValueError):candidate.aces(padded)

    def test_malformed_sid_is_refused(self):
        for value in (b'',sid(18)[:-1],b'\x02'+sid(18)[1:]):
            with self.subTest(value=value),self.assertRaises(ValueError):candidate.owned_ace(value)

    def test_candidate_grants_only_declared_data_and_synchronization_rights(self):
        own=candidate.owned_ace(sid(1001))
        self.assertEqual(struct.unpack_from('<I',own,4)[0],0x100003)
        self.assertEqual(struct.unpack_from('<I',own,4)[0]&0xf0000,0)

if __name__=='__main__':unittest.main()
