"""Pinned controller stop requests fail closed before further native work."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('native_stop_candidate',ROOT/'.aide/evidence/2026-10-18-ordinary-worker/full-native.py')
native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)


class StopRequestTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=os.environ.get('DISKED_WORK_ROOT'))
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.path=self.root/'stop-request.json'
        self.request=dict(schema='org.disked.guest-stop/1',nonce='a'*32,reason='shared_backing_growth',
                          observed_growth_bytes=1073741825,limit_bytes=1073741824)

    def write(self,value):self.path.write_text(json.dumps(value),encoding='utf-8')

    def test_absence_allows_work_and_exact_request_retains_reason(self):
        native.require_uninterrupted(self.root,'a'*32)
        self.write(self.request)
        with self.assertRaises(native.CampaignStop) as caught:native.require_uninterrupted(self.root,'a'*32)
        self.assertEqual(caught.exception.args[0],self.request)

    def test_wrong_campaign_or_reason_cannot_be_adopted(self):
        for changes in ({'nonce':'b'*32},{'reason':'other'},{'schema':'other'},{'extra':0}):
            with self.subTest(changes=changes):
                self.write(dict(self.request,**changes))
                with self.assertRaises(ValueError):native.require_uninterrupted(self.root,'a'*32)

    def test_integer_relationships_cannot_be_weakened(self):
        for changes in ({'observed_growth_bytes':True},{'observed_growth_bytes':1073741824},
                        {'observed_growth_bytes':2**64},{'limit_bytes':2147483648}):
            with self.subTest(changes=changes):
                self.write(dict(self.request,**changes))
                with self.assertRaises(ValueError):native.require_uninterrupted(self.root,'a'*32)

    def test_malformed_oversized_and_non_file_requests_fail_closed(self):
        for data in (b'{',b' '*4097):
            self.path.write_bytes(data)
            with self.assertRaises(ValueError):native.require_uninterrupted(self.root,'a'*32)
        self.path.unlink();self.path.mkdir()
        with self.assertRaises(ValueError):native.require_uninterrupted(self.root,'a'*32)

    def test_probe_cannot_impersonate_actual_budget_exhaustion(self):
        request=dict(self.request,reason='controller_probe',observed_growth_bytes=0)
        self.write(request)
        with self.assertRaises(ValueError):native.require_uninterrupted(self.root,'a'*32)
        with self.assertRaises(native.CampaignStop) as caught:
            native.require_uninterrupted(self.root,'a'*32,allow_probe=True)
        self.assertEqual(caught.exception.args[0],request)

    def test_actual_operator_cancellation_needs_no_fake_budget_exhaustion(self):
        request=dict(self.request,reason='operator_cancel',observed_growth_bytes=0)
        self.write(request)
        with self.assertRaises(native.CampaignStop) as caught:
            native.require_uninterrupted(self.root,'a'*32)
        self.assertEqual(caught.exception.args[0],request)


if __name__=='__main__':unittest.main()
