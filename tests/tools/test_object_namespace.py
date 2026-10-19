"""Pure typed namespace ACE deltas; no host object-manager access."""
import importlib.util
from pathlib import Path
import struct
import unittest

ROOT=Path(__file__).resolve().parents[2]

def module(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'.aide/evidence/2026-10-18-ordinary-worker'/file)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

N=module('namespace_candidate','object-namespace.py')
C=module('unchanged_crypto_candidate','crypto-device.py')

def sid(n):return bytes([1,2,0,0,0,0,0,5])+struct.pack('<II',21,n)
def acl(rows):
    raw=b''.join(rows);return struct.pack('<BBHHH',2,0,len(raw)+8,len(rows),0)+raw

class NamespaceDeltaTests(unittest.TestCase):
    def test_only_fixed_directory_name_creation_and_isolated_codec(self):
        self.assertEqual(N.api.DEVICE,'\\Sessions\\3\\BaseNamedObjects')
        self.assertEqual(N.api.MASK,4)
        self.assertEqual(struct.unpack_from('<I',N.api.owned_ace(sid(8)),4)[0],4)
        self.assertEqual(C.DEVICE,'\\Device\\KsecDD')
        self.assertEqual(C.MASK,0x100003)
        self.assertEqual(struct.unpack_from('<I',C.owned_ace(sid(8)),4)[0],0x100003)

    def test_exact_retirement_preserves_unrelated_concurrent_entry(self):
        before=acl([N.api.owned_ace(sid(1))]);applied=N.api.add_subject(before,sid(8))
        current=acl(N.api.aces(applied)+[N.api.owned_ace(sid(9))])
        retired,count=N.api.remove_subject(current,sid(8))
        self.assertEqual(count,1)
        self.assertEqual(N.api.aces(retired),N.api.aces(before)+[N.api.owned_ace(sid(9))])
        self.assertEqual(N.api.remove_subject(retired,sid(8)),(retired,0))

    def test_changed_duplicate_or_preexisting_subject_refused(self):
        changed=C.owned_ace(sid(8));own=N.api.owned_ace(sid(8))
        for rows in ([changed],[own,own]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):N.api.remove_subject(acl(rows),sid(8))
        with self.assertRaises(ValueError):N.api.add_subject(acl([own]),sid(8))

    def test_inheritance_flags_preserved_without_relaxing_device_parser(self):
        inherited=bytearray(N.api.owned_ace(sid(1)));inherited[1]=11
        before=acl([bytes(inherited)]);applied=N.api.add_subject(before,sid(8))
        self.assertEqual(N.api.remove_subject(applied,sid(8)),(before,1))
        with self.assertRaises(ValueError):C.aces(before)
        inherited[1]=32
        with self.assertRaises(ValueError):N.api.aces(acl([bytes(inherited)]))

if __name__=='__main__':unittest.main()
