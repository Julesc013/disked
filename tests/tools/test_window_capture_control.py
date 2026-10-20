"""Reject requests outside the private window-capture coordinator boundary."""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('owned_window',ROOT/'.aide/evidence/2026-10-18-ordinary-worker/owned-window.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class CaptureRequests(unittest.TestCase):
    def setUp(self):
        self.nonce='a'*32
        self.value=dict(nonce=self.nonce,id='b'*32,window=4096,pid=123,desktop='DiskEdTest-'+'c'*32)

    def rejected(self,**changes):
        value=dict(self.value,**changes)
        with self.assertRaises(ValueError):module.validate_request(value,self.nonce)

    def test_bound_request(self):
        module.validate_request(self.value,self.nonce)

    def test_nonce_and_receipt_identity(self):
        for value in ('','A'*32,'x'*32,'b'*31,'../'+'b'*32):self.rejected(id=value)
        self.rejected(nonce='d'*32)

    def test_only_new_fixture_desktops(self):
        for value in ('Default','Winlogon','Proof-'+'c'*32,'WinSta0\\DiskEdTest-'+'c'*32,'DiskEdTest-'+'c'*31):
            self.rejected(desktop=value)

    def test_bounded_typed_window_process_ids(self):
        for key,limit in (('pid',2**32),('window',2**64)):
            for value in (True,False,0,-1,limit,str(123),None):self.rejected(**{key:value})

    def test_closed_request_shape(self):
        self.rejected(path='C:/unrelated')
        for key in self.value:
            value=dict(self.value);del value[key]
            with self.assertRaises(ValueError):module.validate_request(value,self.nonce)

    def test_non_object(self):
        for value in (None,[],True,'request'):
            with self.assertRaises(ValueError):module.validate_request(value,self.nonce)


@unittest.skipUnless(os.name=='nt','Windows descriptor parser')
class DesktopSecurity(unittest.TestCase):
    expected='D:P(A;;0xf01ff;;;SY)S:(ML;;NW;;;ME)'

    def test_equivalent_aliases_and_auto_inheritance(self):
        actual='D:P(A;;CCDCLCSWRPWPDTLOCRSDRCWDWO;;;SY)S:AI(ML;;NW;;;ME)'
        self.assertEqual(module.desktop_acls(actual),module.desktop_acls(self.expected))

    def test_extra_principal_or_changed_rights(self):
        for actual in ('D:P(A;;0xf01ff;;;SY)(A;;0xf01ff;;;WD)S:(ML;;NW;;;ME)',
                       'D:P(A;;0x20081;;;SY)S:(ML;;NW;;;ME)'):
            self.assertNotEqual(module.desktop_acls(actual),module.desktop_acls(self.expected))

    def test_changed_mandatory_label_or_policy(self):
        for actual in ('D:P(A;;0xf01ff;;;SY)S:(ML;;NW;;;LW)',
                       'D:P(A;;0xf01ff;;;SY)S:(ML;;NRNW;;;ME)'):
            self.assertNotEqual(module.desktop_acls(actual),module.desktop_acls(self.expected))

    def test_unprotected_or_missing_acl_refused(self):
        for actual in ('D:(A;;0xf01ff;;;SY)S:(ML;;NW;;;ME)','D:PS:(ML;;NW;;;ME)','D:P(A;;0xf01ff;;;SY)'):
            with self.assertRaises(ValueError):module.desktop_acls(actual)

if __name__=='__main__':unittest.main()
