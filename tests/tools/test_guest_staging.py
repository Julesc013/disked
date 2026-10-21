import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('ordinary_campaign_staging',ROOT/'.aide/evidence/2026-10-18-ordinary-worker/campaign.py')
campaign=importlib.util.module_from_spec(spec);spec.loader.exec_module(campaign)


class GuestStaging(unittest.TestCase):
    def test_local_stage_does_not_substitute_for_guest_delivery(self):
        with self.assertRaisesRegex(ValueError,'omits staged input'):
            campaign.assert_staged_delivery("@{relative='native-port.py'}",('native-port.py','volume-namespace.py'))

    def test_controller_and_nested_sources_are_required(self):
        required=('native-port.py','volume-namespace.py','source/platform/windows/storage/volume_namespace.cpp')
        campaign.assert_staged_delivery('\n'.join("@{relative='"+p+"'}" for p in required),required)

    def test_duplicate_transfer_paths_are_refused(self):
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            campaign.assert_staged_delivery("@{relative='a'}\n@{relative='a'}",('a',))
