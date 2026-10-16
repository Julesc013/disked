"""Actual held ordinary-image table binding, exact reads and all replay boundaries."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import unittest

import test_ntfs_file as held
import test_ntfs_directory_file as directory_file
from test_ntfs_upcase_capture import UpcaseVolume, MAXIMUM
from ntfs_upcase_expectations import complete, prefix_reports

SOURCE_RECEIPTS = []
INSPECTION = None


class Tests(unittest.TestCase):
    setUp = held.Tests.setUp
    tearDown = held.Tests.tearDown

    def fixture(self, volume=None, name=None):
        return held.Tests.fixture(self, volume or UpcaseVolume(), name)

    def row(self, volume, path, **extra):
        value = dict(path=str(path), offset=volume.input["offset"], length=volume.input["length"],
                     upcase=True, limits=copy.deepcopy(volume.input["limits"]))
        value.update(extra)
        return value

    def preserve(self, path, rows, fault=False, env=None):
        before = held.file_digest(path), path.stat().st_size
        values = held.run(rows, fault, env)
        after = held.file_digest(path), path.stat().st_size
        self.assertEqual(before, after)
        SOURCE_RECEIPTS.append(dict(before_sha256=before[0], after_sha256=after[0], bytes=before[1],
            inputs=[held.digest(held.canonical(r)) for r in rows],
            outputs=[held.digest(held.canonical(r)) for r in values]))
        return values

    def batches(self, path, rows):
        values = []
        for at in range(0, len(rows), 4):
            values.extend(self.preserve(path, rows[at:at + 4], True))
        return values

    def good(self, volume, path, extra=None, fault=False):
        row = self.row(volume, path, **(extra or {}))
        value = self.preserve(path, [row], fault)[0]
        self.assertIn("result", value)
        complete(self, volume, row, value["result"], value["regions"])
        return value

    def test_actual_profiles_mappings_lists_and_owned_table(self):
        for minor in (0, 1):
            for parameters in ({}, dict(cluster=512, mft_first=21), dict(usa=42),
                               dict(cluster=65536), dict(size=32768),
                               dict(list_form="resident", split=True, reverse=True),
                               dict(list_form="nonresident", extension_only=True),
                               dict(mft_closure=True, list_form="nonresident", split=True)):
                volume, path = self.fixture(UpcaseVolume(minor=minor, **parameters))
                for profile in ("auto", "3." + str(minor)):
                    value = self.good(volume, path, dict(profile=profile))
                    self.assertEqual(value["result"]["capture"]["source_before"]["bytes"], str(path.stat().st_size))

    def test_actual_above4GiB_reads_and_independent_prefix_reports(self):
        volume, path = self.fixture(UpcaseVolume(minor=0, offset=(1 << 32) + 4096))
        value = self.good(volume, path)
        prefix_reports(self, volume, self.row(volume, path), value)

    def test_each_native_read_failure_and_changed_reread(self):
        for minor in (0, 1):
            volume, path = self.fixture(UpcaseVolume(minor=minor))
            count = len(volume.initial_reads) * 2
            rows, wanted = [], []
            for call in range(1, count + 1):
                for mode in ("short", "error", "partial_error", "throw", "read_throw"):
                    rows.append(self.row(volume, path, mode=mode, call=str(call)))
                    wanted.append((call, "ntfs_read_length" if mode == "short" else "ntfs_reader_failure"))
                if call > len(volume.initial_reads):
                    rows.append(self.row(volume, path, mode="changed", call=str(call)))
                    wanted.append((call, "ntfs_source_changed"))
            for (call, code), value in zip(wanted, self.batches(path, rows)):
                capture, observation = value["result"]["capture"], value["result"]["observation"]
                self.assertEqual(observation["diagnostic"], code, (minor, call))
                self.assertFalse(observation["applicable"] or capture["observed_stable"])
                self.assertTrue(capture["replay_equal"])
                self.assertEqual(len(value["regions"]), call)

    def test_every_profile_prefix_and_final_replay_fault(self):
        volume, path = self.fixture(UpcaseVolume(minor=0))
        prefix = len(volume.bootstrap_reads)
        rows = [self.row(volume, path, mode=mode, call=str(call))
                for call in range(1, 2 * prefix + 1)
                for mode in ("replay_bytes", "replay_offset", "replay_provenance", "replay_throw")]
        for value in self.batches(path, rows):
            capture = value["result"]["capture"]
            self.assertFalse(capture["profile_selection_equal"] or capture["observed_stable"])
            self.assertIsNone(capture["selected_profile"])
            self.assertEqual(len(value["regions"]), prefix)
            self.assertEqual(value["result"]["observation"]["binding_diagnostic"], "ntfs_file_profile_disagreement")
        for minor in (0, 1):
            volume, path = self.fixture(UpcaseVolume(minor=minor))
            count = 2 * len(volume.initial_reads)
            prefix = 2 * len(volume.bootstrap_reads) if minor == 0 else 0
            rows = [self.row(volume, path, mode=mode, call=str(prefix + call))
                    for call in range(1, count + 1)
                    for mode in ("replay_bytes", "replay_offset", "replay_provenance", "replay_throw")]
            for value in self.batches(path, rows):
                capture = value["result"]["capture"]
                self.assertFalse(capture["replay_equal"] or capture["observed_stable"])
                self.assertTrue(capture["profile_selection_equal"])
                self.assertEqual(len(value["regions"]), count)

    def test_quotas_and_semantic_partial_results(self):
        for minor in (0, 1):
            volume, path = self.fixture(UpcaseVolume(minor=minor))
            count, total = 2 * len(volume.initial_reads), sum(n for _, n in volume.initial_reads)
            self.good(volume, path, dict(limits=dict(MAXIMUM, read_requests=str(count),
                read_bytes=str(2 * total), retained_bytes=str(total), attributes="4", runs="6")))
            for limits, code in [(dict(read_requests=str(count - 1)), "ntfs_read_budget"),
                                 (dict(read_bytes=str(total * 2 - 1)), "ntfs_read_budget"),
                                 (dict(retained_bytes=str(total - 1)), "ntfs_retained_budget"),
                                 (dict(output_bytes="16384"), "ntfs_output_budget")]:
                value = self.preserve(path, [self.row(volume, path, limits=dict(MAXIMUM, **limits))])[0]
                self.assertEqual(value["result"]["observation"]["diagnostic"], code)
                self.assertFalse(value["result"]["capture"]["observed_stable"])
        for parameters, code in [(dict(data_length=131071, place_data=False), "ntfs_upcase_stream_size"),
                                 (dict(initialized=131071), "ntfs_upcase_stream_size"),
                                 (dict(base_options=dict(flags=3)), "ntfs_upcase_record"),
                                 (dict(table_runs=[(32, 8)], place_data=False), "ntfs_upcase_physical_alias")]:
            volume, path = self.fixture(UpcaseVolume(**parameters))
            value = self.preserve(path, [self.row(volume, path)])[0]
            self.assertEqual(value["result"]["observation"]["diagnostic"], code)
            self.assertFalse(value["result"]["capture"]["observed_stable"])

    def test_binding_cancellation_metadata_and_frozen_controls(self):
        volume, path = self.fixture(UpcaseVolume(minor=0))
        original = self.good(volume, path)
        self.good(volume, path, dict(mode="mutate_request"), True)
        for mode in ("binding", "binding_throw", "cancel", "cancel_once", "cancel_throw",
                     "metadata", "metadata_throw"):
            value = self.preserve(path, [self.row(volume, path, mode=mode, call="1")], True)[0]
            if "result" in value:
                self.assertFalse(value["result"]["capture"]["observed_stable"])
            else:
                self.assertIn("refusal", value)
        expected = copy.deepcopy(original["result"]["capture"]["source_before"])
        expected["written"] = "1"
        value = self.preserve(path, [self.row(volume, path, expected_source=expected)])[0]
        self.assertEqual(value["refusal"], "ntfs_file_source_changed")
        environment = dict(os.environ, DISKED_NTFS_FILE_TEST_MODE="changed")
        self.good(volume, path, dict(mode="cancel", call="1"), False)
        value = self.preserve(path, [self.row(volume, path)], False, environment)[0]
        complete(self, volume, self.row(volume, path), value["result"], value["regions"])

    def test_held_source_parent_exclusion_and_release(self):
        volume, path = self.fixture(UpcaseVolume(), name="owned/inner/source.img")
        value = self.good(volume, path, dict(mode="held_access", call="1", release_check=True,
            access_parents=[str(path.parent), str(path.parent.parent)]), True)
        self.assertTrue(value["held_access"])
        self.assertTrue(all(not r.get("opened", r.get("moved", False))
                            for group in value["held_access"] for r in group))
        self.assertTrue(all(r.get("opened", r.get("moved", False)) for r in value["released_access"]))
        self.assertTrue(all(r["opened"] for group in value["released_parent_access"] for r in group))

    def test_public_inspection_rejects_unknown_kind(self):
        process = subprocess.run([str(INSPECTION)], input=held.canonical(dict(private_kind="unknown")),
                                 capture_output=True, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout), dict(rejected=True, diagnostic="ntfs_inspection_kind"))


def main():
    global INSPECTION
    parser = argparse.ArgumentParser()
    for key in ("probe", "fault", "pure", "inspection", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    held.PROBE, held.FAULT = args.probe.resolve(), args.fault.resolve()
    directory_file.PURE, INSPECTION = args.pure.resolve(), args.inspection.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    summary = dict(status="pass" if result.wasSuccessful() else "fail", methods=result.testsRun,
        cases=len(held.RECEIPTS), failures=len(result.failures), errors=len(result.errors),
        recipe_sha256=held.file_digest(Path(__file__)), receipts=held.RECEIPTS,
        source_receipts=SOURCE_RECEIPTS, pure_receipts=directory_file.PURE_RECEIPTS, unverified=held.UNVERIFIED,
        scope="Held ordinary-image NTFS table capture; worker/public/physical/full-product admission separate.")
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
