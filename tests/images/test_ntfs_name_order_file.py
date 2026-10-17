"""Actual ordinary-file binding and replay for joint NTFS key-order facts."""
import argparse
import copy
import json
import os
from pathlib import Path
import unittest

import test_ntfs_file as held
import ntfs_name_order_native_expectations as native
from test_ntfs_name_order import JointVolume
from test_ntfs_upcase_capture import MAXIMUM

INSPECTION = None


class Tests(unittest.TestCase):
    setUp = held.Tests.setUp
    tearDown = held.Tests.tearDown

    def fixture(self, volume=None, name=None):
        return held.Tests.fixture(self, volume or JointVolume(), name)

    def preserve(self, path, rows, fault=False, env=None):
        before = held.file_digest(path), path.stat().st_size
        values = []
        try:
            values = native.run_file(rows, fault, env)
            return values
        finally:
            native.source_receipt(path, before, rows, values)

    def batches(self, path, rows):
        values = []
        for at in range(0, len(rows), 4):
            values.extend(self.preserve(path, rows[at:at + 4], True))
        return values

    def good(self, volume, path, extra=None, fault=False):
        request = native.row(volume, path, **(extra or {}))
        value = self.preserve(path, [request], fault)[0]
        self.assertIn("result", value)
        native.complete(self, volume, request, value["result"], value["regions"])
        return value

    def test_actual_layout_profiles_order_groups_and_selected_aliases(self):
        for name, volume, _, diagnostic in native.layouts():
            volume, path = self.fixture(volume)
            for profile in ("auto", "3." + volume.input["minor"]):
                request = native.row(volume, path, profile=profile)
                value = self.preserve(path, [request])[0]
                self.assertIn("result", value, name)
                if diagnostic in ("", "ntfs_name_order_mapped_descent"):
                    native.complete(self, volume, request, value["result"], value["regions"])
                else:
                    observation = value["result"]["observation"]
                    self.assertEqual(observation["diagnostic"], diagnostic, name)
                    self.assertFalse(observation["complete"] or observation["applicable"])
                    self.assertIsNone(observation["name_order"])
                    self.assertFalse(value["result"]["capture"]["observed_stable"])

    def test_root_discovery_and_explicit_profile_mismatch(self):
        for minor in (0, 1):
            volume, path = self.fixture(JointVolume(minor=minor))
            self.good(volume, path, dict(directory=dict(reference="0")))
            value = self.preserve(path, [native.row(volume, path, profile="3." + str(1 - minor))])[0]
            observation = value["result"]["observation"]
            self.assertEqual(observation["diagnostic"], "ntfs_volume_version")
            self.assertFalse(observation["complete"] or observation["applicable"])
            self.assertIsNone(observation["name_order"])
            self.assertFalse(value["result"]["capture"]["observed_stable"])

    def test_each_native_read_fault_and_changed_reread(self):
        for minor in (0, 1):
            volume, path = self.fixture(JointVolume(minor=minor))
            count = 2 * len(volume.initial_reads)
            rows, wanted = [], []
            for call in range(1, count + 1):
                for mode in ("short", "error", "partial_error", "throw", "read_throw"):
                    rows.append(native.row(volume, path, mode=mode, call=str(call)))
                    wanted.append((call, "ntfs_read_length" if mode == "short" else "ntfs_reader_failure"))
                if call > len(volume.initial_reads):
                    rows.append(native.row(volume, path, mode="changed", call=str(call)))
                    wanted.append((call, "ntfs_source_changed"))
            for (call, diagnostic), value in zip(wanted, self.batches(path, rows)):
                capture, observation = value["result"]["capture"], value["result"]["observation"]
                self.assertEqual(observation["diagnostic"], diagnostic, (minor, call))
                self.assertFalse(observation["applicable"] or capture["observed_stable"])
                self.assertTrue(capture["replay_equal"])
                self.assertEqual(len(value["regions"]), call)
                if call > len(volume.initial_reads):
                    self.assertTrue(observation["name_order"]["complete"])
                    self.assertTrue(observation["upcase"]["complete"])

    def test_profile_prefix_and_final_replay_boundaries(self):
        volume, path = self.fixture(JointVolume(minor=0))
        prefix = len(volume.directory.bootstrap_reads)
        rows = [native.row(volume, path, mode=mode, call=str(call))
                for call in range(1, 2 * prefix + 1)
                for mode in ("replay_bytes", "replay_offset", "replay_provenance", "replay_throw")]
        for value in self.batches(path, rows):
            capture = value["result"]["capture"]
            self.assertFalse(capture["profile_selection_equal"] or capture["observed_stable"])
            self.assertIsNone(capture["selected_profile"])
            self.assertEqual(len(value["regions"]), prefix)
            self.assertEqual(value["result"]["observation"]["binding_diagnostic"], "ntfs_file_profile_disagreement")
        for minor in (0, 1):
            volume, path = self.fixture(JointVolume(minor=minor))
            count = 2 * len(volume.initial_reads)
            offset = 2 * len(volume.directory.bootstrap_reads) if minor == 0 else 0
            rows = [native.row(volume, path, mode=mode, call=str(offset + call))
                    for call in range(1, count + 1)
                    for mode in ("replay_bytes", "replay_offset", "replay_provenance", "replay_throw")]
            for value in self.batches(path, rows):
                capture = value["result"]["capture"]
                self.assertFalse(capture["replay_equal"] or capture["observed_stable"])
                self.assertTrue(capture["profile_selection_equal"])
                self.assertEqual(len(value["regions"]), count)

    def test_exact_and_one_short_source_budgets(self):
        for minor in (0, 1):
            volume, path = self.fixture(JointVolume(minor=minor))
            count, total = 2 * len(volume.initial_reads), sum(n for _, n in volume.initial_reads)
            self.good(volume, path, dict(limits=dict(MAXIMUM, read_requests=str(count),
                           read_bytes=str(total * 2), retained_bytes=str(total))))
            for limits, diagnostic in [(dict(read_requests=str(count - 1)), "ntfs_read_budget"),
                                        (dict(read_bytes=str(total * 2 - 1)), "ntfs_read_budget"),
                                        (dict(retained_bytes=str(total - 1)), "ntfs_retained_budget"),
                                        (dict(output_bytes="16384"), "ntfs_output_budget")]:
                request = native.row(volume, path, limits=dict(MAXIMUM, **limits))
                value = self.preserve(path, [request])[0]
                self.assertEqual(value["result"]["observation"]["diagnostic"], diagnostic)
                self.assertFalse(value["result"]["capture"]["observed_stable"])

    def test_copied_controls_binding_metadata_and_expected_source(self):
        volume, path = self.fixture(JointVolume(minor=0))
        original = self.good(volume, path)
        self.good(volume, path, dict(mode="mutate_request"), True)
        for mode in ("binding", "binding_throw", "cancel", "cancel_once", "cancel_throw", "metadata", "metadata_throw"):
            value = self.preserve(path, [native.row(volume, path, mode=mode, call="1")], True)[0]
            if "result" in value:
                self.assertFalse(value["result"]["capture"]["observed_stable"])
            else:
                self.assertIn("refusal", value)
        expected = copy.deepcopy(original["result"]["capture"]["source_before"])
        expected["written"] = "1"
        value = self.preserve(path, [native.row(volume, path, expected_source=expected)])[0]
        self.assertEqual(value["refusal"], "ntfs_file_source_changed")

    def test_held_source_parent_exclusion_and_release(self):
        volume, path = self.fixture(name="owned/inner/name-order.img")
        value = self.good(volume, path, dict(mode="held_access", call="1", release_check=True,
                          access_parents=[str(path.parent), str(path.parent.parent)]), True)
        self.assertTrue(value["held_access"])
        self.assertTrue(all(not v.get("opened", v.get("moved", False)) for group in value["held_access"] for v in group))
        self.assertTrue(all(v.get("opened", v.get("moved", False)) for v in value["released_access"]))
        self.assertTrue(all(v["opened"] for group in value["released_parent_access"] for v in group))

    def test_invalid_controls_and_public_kind_gate(self):
        volume, path = self.fixture()
        for changes, diagnostic in [
            (dict(directory=dict(reference="5")), "ntfs_directory_reference"),
            (dict(directory=dict(limits=dict(entries="0"))), "ntfs_directory_limits"),
            (dict(limits=dict(MAXIMUM, read_requests="513")), "ntfs_capture_limits"),
            (dict(offset=str(1 << 63)), "ntfs_file_seek_range"),
        ]:
            value = self.preserve(path, [native.row(volume, path, **changes)], True)[0]
            self.assertEqual(value["refusal"], diagnostic)
            self.assertNotIn("result", value)
            self.assertEqual(value.get("regions", []), [])
        for kind in ("name_order", "unknown"):
            _, raw = native.invoke(INSPECTION, held.canonical(dict(private_kind=kind)), 10)
            expected = dict(rejected=False) if kind == "name_order" else dict(rejected=True, diagnostic="ntfs_inspection_kind")
            self.assertEqual(json.loads(raw), expected)

    def test_normal_and_fault_controls_remain_isolated(self):
        volume, path = self.fixture()
        self.good(volume, path, dict(mode="cancel", call="1"), False)
        env = dict(os.environ, DISKED_NTFS_FILE_TEST_MODE="changed")
        request = native.row(volume, path)
        value = self.preserve(path, [request], False, env)[0]
        native.complete(self, volume, request, value["result"], value["regions"])


def main():
    global INSPECTION
    parser = argparse.ArgumentParser()
    for name in ("probe", "fault", "pure", "inspection", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    native.PROBE, native.FAULT, native.PURE = args.probe.resolve(), args.fault.resolve(), args.pure.resolve()
    native.OUTPUT, INSPECTION = args.output.resolve(), args.inspection.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    summary = dict(status="pass" if result.wasSuccessful() else "fail", methods=result.testsRun,
                   failures=len(result.failures), errors=len(result.errors),
                   recipe_sha256=held.file_digest(Path(__file__)), helper_sha256=held.file_digest(Path(native.__file__)),
                   calls=len(native.RECEIPTS), receipts=native.RECEIPTS, source_receipts=native.SOURCE_RECEIPTS,
                   unverified=held.UNVERIFIED, owner_accepted=False, full_0_1_0_complete=False)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
