"""Owned table-reader identity, immutable frames and source-free parent reconstruction."""
import argparse
import copy
import json
from pathlib import Path
import unittest

import test_ntfs_file as held
import test_ntfs_worker as worker
import test_ntfs_directory_file as directory_file
from test_ntfs_upcase_capture import UpcaseVolume, MAXIMUM
from ntfs_upcase_expectations import complete, prefix_reports

SOURCE_RECEIPTS = []
UNEXPECTED = []


def run(row, fault=False):
    value = worker.run(row, fault)
    return value


class Tests(unittest.TestCase):
    setUp = worker.Tests.setUp
    tearDown = worker.Tests.tearDown
    retired = worker.Tests.retired

    def fixture(self, volume=None):
        volume, path = held.Tests.fixture(self, volume or UpcaseVolume())
        row = dict(path=str(path), offset=volume.input["offset"], length=volume.input["length"],
                   capture_epoch="77", upcase=True, limits=copy.deepcopy(volume.input["limits"]))
        return volume, path, row

    def preserve(self, path, row, fault=False):
        before = held.file_digest(path), path.stat().st_size
        value = run(row, fault)
        after = held.file_digest(path), path.stat().st_size
        self.assertEqual(before, after)
        SOURCE_RECEIPTS.append(dict(before_sha256=before[0], after_sha256=after[0], bytes=before[1],
            input_sha256=held.digest(held.canonical(row)), output_sha256=held.digest(held.canonical(value))))
        return value

    def good(self, volume, path, row, **extra):
        selected = dict(row, **extra)
        value = self.preserve(path, selected)
        if not value.get("has_snapshot"):
            UNEXPECTED.append(dict(request=selected, output=value))
        self.assertTrue(value.get("has_snapshot"), value)
        self.retired(value)
        self.assertTrue(value["retained_unchanged"])
        frame, context = value["frame"], value["context"]
        complete(self, volume, selected, value["snapshot"], frame["regions"])
        self.assertEqual(frame["schema"], "org.disked.ntfs-upcase-region-frame/1")
        self.assertEqual(frame["input"]["schema"], "org.disked.ntfs-upcase-source-request/1")
        self.assertEqual(set(frame["input"]), {"schema", "path", "expected_source", "volume_offset",
                                              "volume_bytes", "profile", "limits", "fixture"})
        self.assertEqual(context["image_profile"], "ordinary-file-ntfs-upcase")
        self.assertEqual(context["capture_epoch"], selected["capture_epoch"])
        self.assertEqual(context["code_sha256"], held.file_digest(worker.PROBE).removeprefix("sha256:"))
        self.assertEqual(context["frame_sha256"], held.digest(held.canonical(frame)))
        for frame_key, key in (("process_id", "pid"), ("process_created", "created")):
            self.assertEqual(frame[frame_key], context[key])
            self.assertEqual(context[key], value["independent_process"][key])
        self.assertTrue(value["independent_process"]["in_job"])
        return value

    def test_owned_profiles_layouts_and_frozen_controls(self):
        for minor in (0, 1):
            for parameters in ({}, dict(cluster=512, mft_first=21), dict(usa=42),
                               dict(cluster=65536), dict(size=32768),
                               dict(list_form="resident", split=True, reverse=True),
                               dict(mft_closure=True, list_form="nonresident", split=True)):
                volume, path, row = self.fixture(UpcaseVolume(minor=minor, **parameters))
                for profile in ("auto", "3." + str(minor)):
                    self.good(volume, path, row, profile=profile)
            self.good(volume, path, row, mutate_after_prepare=True)

    def test_actual_above4GiB_and_independent_prefix_reports(self):
        volume, path, row = self.fixture(UpcaseVolume(minor=0, offset=(1 << 32) + 4096))
        value = self.good(volume, path, row)
        prefix_reports(self, volume, row, dict(result=value["snapshot"]))

    def test_source_free_reconstruction_and_inert_preparation(self):
        for minor in (0, 1):
            volume, path, row = self.fixture(UpcaseVolume(minor=minor, list_form="nonresident", split=True))
            original = self.preserve(path, dict(row, mode="frame"))
            frame = original["frame"]
            self.assertEqual(frame["result"], original["verified"])
            base = dict(row, expected_source=frame["result"]["capture"]["source_before"])
            path.unlink()
            self.assertTrue(run(dict(base, mode="construction"))["never_launched"])
            self.assertEqual(run(dict(base, mode="verify", replace=frame))["verified"], frame["result"])
            unavailable = run(base)
            self.retired(unavailable)
            self.assertFalse(unavailable["has_snapshot"])

    def test_strict_upcase_input_and_graph_control_isolation(self):
        _, path, row = self.fixture()
        original = self.preserve(path, dict(row, mode="frame"))["frame"]
        base = dict(row, mode="decode_input", expected_source=original["result"]["capture"]["source_before"])
        self.assertEqual(self.preserve(path, base)["input"], original["input"])
        for field, value in (("directory_reference", "0"), ("directory_limits", {}), ("target_limit", "64"),
                              ("unknown", True)):
            candidate = copy.deepcopy(original["input"])
            candidate[field] = value
            self.assertIn("error", self.preserve(path, dict(base, replace_input=candidate)))
        for controls in (dict(nonmember_target_limit="63"), dict(invalid_kind=True)):
            self.assertIn("error", self.preserve(path, dict(base, **controls)))
        for fixture in (dict(capture_fault="error"), dict(worker_fault="upcase_changed"), dict(capture_call="1")):
            self.assertIn("error", self.preserve(path, dict(base, fixture=fixture)))
        for kind in ("org.disked.ntfs-source-request/1", "org.disked.ntfs-directory-source-request/1",
                     "org.disked.ntfs-membership-source-request/1", "org.disked.ntfs-upcase-source-request/9"):
            frame = copy.deepcopy(original)
            frame["input"]["schema"] = kind
            self.assertIn("error", self.preserve(path, dict(base, mode="verify", replace=frame)))

    def test_every_table_context_digest_and_profile_receipt_is_reconstructed(self):
        for minor in (0, 1):
            volume, path, row = self.fixture(UpcaseVolume(minor=minor))
            original = self.preserve(path, dict(row, mode="frame"))["frame"]
            base = dict(row, mode="verify", expected_source=original["result"]["capture"]["source_before"])
            for field in ("table_bytes", "table_sha256", "source_id", "epoch", "volume_offset",
                          "volume_bytes", "volume_serial", "base_reference", "base_record_sha256", "schema"):
                frame = copy.deepcopy(original)
                table = frame["result"]["observation"]["upcase"]
                table[field] = "wrong" if "sha256" in field or field in ("source_id", "schema") else "1"
                self.assertIn("error", self.preserve(path, dict(base, replace=frame)), (minor, field))
            frame = copy.deepcopy(original)
            table = frame["result"]["observation"]["upcase"]
            raw = bytearray.fromhex(table["table_hex"])
            raw[0] ^= 1
            table.update(table_hex=raw.hex(), table_sha256=held.digest(raw))
            self.assertIn("error", self.preserve(path, dict(base, replace=frame)))
            for change in ("schema", "capture-schema", "provider", "epoch", "process", "complete", "authority"):
                frame = copy.deepcopy(original)
                capture, obs = frame["result"]["capture"], frame["result"]["observation"]
                if change == "schema": frame["schema"] = "org.disked.ntfs-region-frame/1"
                elif change == "capture-schema": frame["result"]["schema"] = "org.disked.ntfs-file-capture/1"
                elif change == "provider":
                    capture["domain"]["provider"] = "ntfs-file-prototype"
                    capture["capture_domain"] = held.digest(held.canonical(capture["domain"]))
                elif change == "epoch": frame["capture_epoch"] = "1"
                elif change == "process": frame["process_id"] = "1"
                elif change == "complete": obs["upcase"]["complete"] = False
                else: obs["current_source_authority"] = True
                self.assertIn("error", self.preserve(path, dict(base, replace=frame)), (minor, change))
            capture_keys = ("profile_probe_response_count", "profile_probe_sha256", "profile_prefix_validation_attempted",
                "profile_prefix_validated", "profile_prefix_boundary", "profile_prefix_continued",
                "profile_prefix_validation_calls", "profile_prefix_reused", "profile_prefix_validation_sha256",
                "profile_probe_foundation_sha256", "profile_selected_foundation_sha256", "replay_calls", "retained_replays")
            for key in capture_keys:
                frame = copy.deepcopy(original)
                capture = frame["result"]["capture"]
                old = capture[key]
                capture[key] = not old if isinstance(old, bool) else "sha256:" + "0" * 64 if old is None or "sha256" in key else str(int(old) + 1)
                self.assertIn("error", self.preserve(path, dict(base, replace=frame)), (minor, key))

    def test_every_response_provenance_and_table_bytes_are_bound(self):
        _, path, row = self.fixture()
        original = self.preserve(path, dict(row, mode="frame"))["frame"]
        base = dict(row, mode="verify", expected_source=original["result"]["capture"]["source_before"])
        for index in range(len(original["regions"])):
            for field in ("offset", "requested", "error", "seek_attempted", "read_attempted", "bytes", "refusal"):
                frame = copy.deepcopy(original)
                region = frame["regions"][index]
                if field in ("seek_attempted", "read_attempted"): region[field] = False
                elif field == "bytes":
                    raw = bytearray.fromhex(region[field]); raw[0] ^= 1; region[field] = raw.hex()
                elif field == "refusal": region[field] = "changed"
                else: region[field] = str(int(region[field]) + 1)
                self.assertIn("error", self.preserve(path, dict(base, replace=frame)), (index, field))

    def test_partial_source_observations_are_retained_without_applicability(self):
        for parameters, diagnostic in [(dict(data_length=131071, place_data=False), "ntfs_upcase_stream_size"),
                                        (dict(initialized=131071), "ntfs_upcase_stream_size"),
                                        (dict(base_options=dict(flags=3)), "ntfs_upcase_record")]:
            _, path, row = self.fixture(UpcaseVolume(**parameters))
            value = self.preserve(path, row)
            self.retired(value)
            self.assertTrue(value["has_snapshot"], value)
            self.assertEqual(value["snapshot"]["observation"]["diagnostic"], diagnostic)
            self.assertFalse(value["snapshot"]["capture"]["observed_stable"])
        volume, path, row = self.fixture()
        for call in (1, len(volume.initial_reads), len(volume.initial_reads) + 1, 2 * len(volume.initial_reads)):
            value = self.preserve(path, dict(row, fixture=dict(capture_fault="short", capture_call=str(call))), True)
            self.retired(value)
            self.assertTrue(value["has_snapshot"], value)
            self.assertFalse(value["snapshot"]["capture"]["observed_stable"])
            self.assertEqual(value["snapshot"]["observation"]["diagnostic"], "ntfs_read_length")

    def test_real_worker_forgery_faults_never_admit_a_snapshot(self):
        _, path, row = self.fixture()
        for fault in ("result_changed", "receipt_changed", "process_changed", "domain_changed",
                      "row_changed", "prefix_changed", "upcase_changed"):
            value = self.preserve(path, dict(row, fixture=dict(worker_fault=fault)), True)
            self.retired(value)
            self.assertFalse(value["has_snapshot"], (fault, value))
        value = self.preserve(path, dict(row, fixture=dict(capture_fault="metadata")), True)
        self.retired(value)
        self.assertFalse(value["has_snapshot"])

    def test_actual_lifecycle_cancellation_and_exit_boundary(self):
        _, path, row = self.fixture(UpcaseVolume(minor=0))
        for fault in ("before_spawn", "after_spawn", "after_spawn_alloc"):
            value = self.preserve(path, dict(row, fixture=dict(startup_fault=fault)), True)
            self.assertIn("startup_error", value)
            self.assertEqual(value["never_launched"], fault == "before_spawn")
            if fault != "before_spawn": self.retired(value)
        for fault in ("hang", "late"):
            value = self.preserve(path, dict(row, mode="pending", fixture=dict(worker_fault=fault)), True)
            self.retired(value); self.assertFalse(value["has_snapshot"])
        for extra in (dict(cancel=True), dict(fixture=dict(worker_fault="exit"))):
            value = self.preserve(path, dict(row, **extra), bool(extra.get("fixture")))
            self.retired(value); self.assertFalse(value["has_snapshot"])
        value = self.preserve(path, dict(row, mode="publication-live", fixture=dict(reply_fault="hold")), True)
        self.retired(value); self.assertFalse(value["has_snapshot"])
        self.assertEqual(value["before"]["diagnostic"], "ntfs_worker_exit_pending")
        value = self.preserve(path, dict(row, mode="retire-zero", fixture=dict(worker_fault="hang")), True)
        self.assertEqual(value["zero_retirement"]["retired"], value["zero_retirement"]["worker"]["observation"] == "exited")
        self.retired(value)

    def test_frame_component_limits_remain_finite(self):
        _, path, row = self.fixture()
        original = self.preserve(path, dict(row, mode="frame"))["frame"]
        base = dict(row, mode="verify", expected_source=original["result"]["capture"]["source_before"])
        for part, size in (("observation", 2 * 1024 * 1024), ("capture", 65536)):
            frame = copy.deepcopy(original); frame["result"][part]["overflow"] = "x" * size
            self.assertIn("error", self.preserve(path, dict(base, replace=frame)))
        frame = copy.deepcopy(original); frame["input"]["overflow"] = "x" * 131072
        self.assertIn("error", self.preserve(path, dict(base, replace=frame)))
        frame = copy.deepcopy(original); frame["regions"] = [copy.deepcopy(frame["regions"][0]) for _ in range(513)]
        self.assertIn("error", self.preserve(path, dict(base, replace=frame)))


def main():
    parser = argparse.ArgumentParser()
    for key in ("probe", "fault", "pure", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    worker.PROBE, worker.FAULT, directory_file.PURE = args.probe.resolve(), args.fault.resolve(), args.pure.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    summary = dict(status="pass" if result.wasSuccessful() else "fail", methods=result.testsRun,
        cases=len(worker.RECEIPTS), failures=len(result.failures), errors=len(result.errors),
        recipe_sha256=held.file_digest(Path(__file__)), receipts=worker.RECEIPTS, source_receipts=SOURCE_RECEIPTS,
        observations=worker.OBSERVATIONS, unexpected_outputs=UNEXPECTED, unverified=held.UNVERIFIED,
        pure_receipts=directory_file.PURE_RECEIPTS, owner_accepted=False, full_0_1_0_complete=False)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
