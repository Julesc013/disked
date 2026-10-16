"""Owned joint NTFS readers, strict frames, replay and lifecycle boundaries."""
import argparse
import copy
import json
from pathlib import Path
import unittest

import test_ntfs_file as held
import test_ntfs_worker as worker
import ntfs_name_order_native_expectations as native
from test_ntfs_name_order import JointVolume


class Tests(unittest.TestCase):
    setUp = worker.Tests.setUp
    tearDown = worker.Tests.tearDown
    retired = worker.Tests.retired

    def fixture(self, volume=None):
        volume, path = held.Tests.fixture(self, volume or JointVolume())
        return volume, path, native.row(volume, path, capture_epoch="77")

    def preserve(self, path, request, fault=False):
        before = held.file_digest(path), path.stat().st_size
        values = []
        try:
            value = native.run_worker(request, fault)
            values = [value]
            return value
        finally:
            native.source_receipt(path, before, [request], values)

    def good(self, volume, path, request, **extra):
        selected = dict(request, **extra)
        value = self.preserve(path, selected)
        self.assertTrue(value.get("has_snapshot"), value)
        self.retired(value)
        self.assertTrue(value["retained_unchanged"])
        frame, context = value["frame"], value["context"]
        native.complete(self, volume, selected, value["snapshot"], frame["regions"])
        self.assertEqual(frame["schema"], "org.disked.ntfs-name-order-region-frame/1")
        self.assertEqual(frame["input"]["schema"], "org.disked.ntfs-name-order-source-request/1")
        self.assertEqual(set(frame["input"]), {"schema", "path", "expected_source", "volume_offset", "volume_bytes",
                                              "profile", "limits", "fixture", "directory_reference", "directory_limits"})
        self.assertEqual(context["image_profile"], "ordinary-file-ntfs-name-order")
        self.assertEqual(context["capture_epoch"], selected["capture_epoch"])
        self.assertEqual(context["code_sha256"], held.file_digest(native.PROBE).removeprefix("sha256:"))
        self.assertEqual(context["frame_sha256"], held.digest(held.canonical(frame)))
        self.assertIn("independent_process", value)
        for frame_key, key in (("process_id", "pid"), ("process_created", "created")):
            self.assertEqual(frame[frame_key], context[key])
            self.assertEqual(context[key], value["independent_process"][key])
        self.assertTrue(value["independent_process"]["in_job"])
        return value

    def test_owned_profiles_layouts_order_groups_and_copied_controls(self):
        wanted = {"profile-0-empty", "profile-0-siblings", "profile-1-deep", "high-window", "old-record",
                  "large-record", "small-index", "directory-list", "mft-volume-closure",
                  "table-nonresident-list", "folded-raw-reverse", "namespace-candidates", "descending", "large-order"}
        found = set()
        for name, volume, _, _ in native.layouts():
            if name not in wanted:
                continue
            found.add(name)
            volume, path, request = self.fixture(volume)
            for profile in ("auto", "3." + volume.input["minor"]):
                self.good(volume, path, request, profile=profile)
        self.assertEqual(found, wanted)
        volume, path, request = self.fixture(JointVolume(minor=0))
        self.good(volume, path, request, mutate_after_prepare=True)

    def test_source_free_replay_and_inert_preparation(self):
        for minor in (0, 1):
            volume, path, request = self.fixture(JointVolume(minor=minor, list_form="nonresident"))
            original = self.preserve(path, dict(request, mode="frame"))
            frame = original["frame"]
            self.assertEqual(frame["result"], original["verified"])
            base = dict(request, expected_source=frame["result"]["capture"]["source_before"])
            path.unlink()
            self.assertTrue(native.run_worker(dict(base, mode="construction"))["never_launched"])
            self.assertEqual(native.run_worker(dict(base, mode="verify", replace=frame))["verified"], frame["result"])
            unavailable = native.run_worker(base)
            self.retired(unavailable)
            self.assertFalse(unavailable["has_snapshot"])

    def test_strict_input_kind_and_control_relationships(self):
        _, path, request = self.fixture()
        original = self.preserve(path, dict(request, mode="frame"))["frame"]
        base = dict(request, mode="decode_input", expected_source=original["result"]["capture"]["source_before"])
        self.assertEqual(self.preserve(path, base)["input"], original["input"])
        for field, value in (("target_limit", "64"), ("unknown", True)):
            candidate = copy.deepcopy(original["input"])
            candidate[field] = value
            self.assertIn("error", self.preserve(path, dict(base, replace_input=candidate)))
        for field in ("directory_reference", "directory_limits"):
            candidate = copy.deepcopy(original["input"])
            del candidate[field]
            self.assertIn("error", self.preserve(path, dict(base, replace_input=candidate)))
        for controls in (dict(nonmember_target_limit="63"), dict(invalid_kind=True),
                         dict(directory=dict(reference="5")), dict(directory=dict(limits=dict(entries="0")))):
            self.assertIn("error", self.preserve(path, dict(base, **controls)))
        for fixture in (dict(capture_fault="error"), dict(worker_fault="name_order_changed"), dict(capture_call="1")):
            self.assertIn("error", self.preserve(path, dict(base, fixture=fixture)))
        for schema in ("org.disked.ntfs-source-request/1", "org.disked.ntfs-directory-source-request/1",
                       "org.disked.ntfs-membership-source-request/1", "org.disked.ntfs-upcase-source-request/1",
                       "org.disked.ntfs-name-order-source-request/9"):
            frame = copy.deepcopy(original)
            frame["input"]["schema"] = schema
            self.assertIn("error", self.preserve(path, dict(base, mode="verify", replace=frame)))

    def test_every_name_order_context_counter_claim_and_group_is_reconstructed(self):
        for minor in (0, 1):
            _, path, request = self.fixture(JointVolume(minor=minor))
            original = self.preserve(path, dict(request, mode="frame"))["frame"]
            base = dict(request, mode="verify", expected_source=original["result"]["capture"]["source_before"])
            for field in ("schema", "policy", "case_policy", "source_id", "epoch", "volume_offset", "volume_bytes",
                          "directory_reference", "table_sha256", "directory_sha256", "key_count", "keys_returned",
                          "adjacent_returned", "reference_groups_returned", "mapped_groups_returned", "complete",
                          "mapped_nondecreasing", "namespace_verified", "collation_verified", "target_membership_verified",
                          "alias_resolution_admitted", "lookup_admitted"):
                frame = copy.deepcopy(original)
                audit = frame["result"]["observation"]["name_order"]
                old = audit[field]
                audit[field] = (not old if isinstance(old, bool) else
                                "wrong" if field in ("schema", "policy", "case_policy", "source_id") or "sha256" in field
                                else str(int(old) + 1))
                self.assertNotEqual(audit[field], old)
                self.assertIn("error", self.preserve(path, dict(base, replace=frame)), (minor, field))
            for array in ("order", "adjacent", "reference_groups", "mapped_groups"):
                frame = copy.deepcopy(original)
                audit = frame["result"]["observation"]["name_order"]
                audit[array] = audit[array][1:] if audit[array] else [dict(forged=True)]
                self.assertIn("error", self.preserve(path, dict(base, replace=frame)), (minor, array))
            frame = copy.deepcopy(original)
            observation = frame["result"]["observation"]
            table = observation["upcase"]
            raw = bytearray.fromhex(table["table_hex"])
            raw[0] ^= 1
            table.update(table_hex=raw.hex(), table_sha256=held.digest(raw))
            observation["name_order"]["table_sha256"] = table["table_sha256"]
            self.assertIn("error", self.preserve(path, dict(base, replace=frame)))
            frame = copy.deepcopy(original)
            observation = frame["result"]["observation"]
            observation["directory"]["entries"][0]["name_hex"] = "5a00"
            observation["name_order"]["directory_sha256"] = held.digest(held.canonical(observation["directory"]))
            self.assertIn("error", self.preserve(path, dict(base, replace=frame)))

    def test_every_response_provenance_and_ingredient_bytes_are_bound(self):
        _, path, request = self.fixture()
        original = self.preserve(path, dict(request, mode="frame"))["frame"]
        base = dict(request, mode="verify", expected_source=original["result"]["capture"]["source_before"])
        for index in range(len(original["regions"])):
            for field in ("offset", "requested", "error", "seek_attempted", "read_attempted", "bytes", "refusal"):
                frame = copy.deepcopy(original)
                region = frame["regions"][index]
                if field in ("seek_attempted", "read_attempted"):
                    region[field] = False
                elif field == "bytes":
                    raw = bytearray.fromhex(region[field])
                    raw[0] ^= 1
                    region[field] = raw.hex()
                elif field == "refusal":
                    region[field] = "changed"
                else:
                    region[field] = str(int(region[field]) + 1)
                self.assertIn("error", self.preserve(path, dict(base, replace=frame)), (index, field))

    def test_source_profile_domain_and_prefix_receipts_are_bound(self):
        _, path, request = self.fixture(JointVolume(minor=0))
        original = self.preserve(path, dict(request, mode="frame"))["frame"]
        base = dict(request, mode="verify", expected_source=original["result"]["capture"]["source_before"])
        fields = ("profile_probe_response_count", "profile_probe_sha256", "profile_prefix_validation_attempted",
                  "profile_prefix_validated", "profile_prefix_boundary", "profile_prefix_continued",
                  "profile_prefix_validation_calls", "profile_prefix_reused", "profile_prefix_validation_sha256",
                  "profile_probe_foundation_sha256", "profile_selected_foundation_sha256", "replay_calls", "retained_replays")
        for field in fields:
            frame = copy.deepcopy(original)
            capture = frame["result"]["capture"]
            old = capture[field]
            capture[field] = (not old if isinstance(old, bool) else
                              "sha256:" + "0" * 64 if old is None or "sha256" in field else str(int(old) + 1))
            self.assertIn("error", self.preserve(path, dict(base, replace=frame)), field)
        for change in ("frame-schema", "file-schema", "provider", "directory-reference", "process", "epoch", "authority"):
            frame = copy.deepcopy(original)
            capture, observation = frame["result"]["capture"], frame["result"]["observation"]
            if change == "frame-schema":
                frame["schema"] = "org.disked.ntfs-upcase-region-frame/1"
            elif change == "file-schema":
                frame["result"]["schema"] = "org.disked.ntfs-directory-file-capture/1"
            elif change in ("provider", "directory-reference"):
                capture["domain"]["provider" if change == "provider" else "directory_reference"] = "wrong" if change == "provider" else "1"
                capture["capture_domain"] = held.digest(held.canonical(capture["domain"]))
            elif change == "process":
                frame["process_id"] = "1"
            elif change == "epoch":
                frame["capture_epoch"] = "1"
            else:
                observation["current_source_authority"] = True
            self.assertIn("error", self.preserve(path, dict(base, replace=frame)), change)

    def test_completed_negative_and_authentic_partial_results_remain_distinct(self):
        for name, volume, _, diagnostic in native.layouts():
            if name not in {"descending", "table-index-alias", "table-list-directory-list-alias"}:
                continue
            volume, path, request = self.fixture(volume)
            value = self.preserve(path, request)
            self.retired(value)
            self.assertTrue(value["has_snapshot"], value)
            observation = value["snapshot"]["observation"]
            self.assertEqual(observation["diagnostic"], diagnostic)
            self.assertFalse(value["snapshot"]["capture"]["observed_stable"])
            self.assertEqual(observation["complete"], name == "descending")
            if name == "descending":
                self.assertTrue(observation["name_order"]["complete"])
        volume, path, request = self.fixture()
        for call in (1, len(volume.initial_reads), len(volume.initial_reads) + 1, 2 * len(volume.initial_reads)):
            value = self.preserve(path, dict(request, fixture=dict(capture_fault="short", capture_call=str(call))), True)
            self.retired(value)
            self.assertTrue(value["has_snapshot"], value)
            self.assertFalse(value["snapshot"]["capture"]["observed_stable"])
            self.assertEqual(value["snapshot"]["observation"]["diagnostic"], "ntfs_read_length")
        value = self.preserve(path, dict(request, fixture=dict(capture_fault="metadata")), True)
        self.retired(value)
        self.assertTrue(value["has_snapshot"])
        self.assertFalse(value["snapshot"]["capture"]["metadata_equal"] or value["snapshot"]["capture"]["observed_stable"])

    def test_real_worker_forgery_never_admits_snapshot(self):
        _, path, request = self.fixture()
        for fault in ("result_changed", "receipt_changed", "process_changed", "domain_changed", "row_changed",
                      "prefix_changed", "name_order_directory_changed", "upcase_changed", "name_order_changed"):
            value = self.preserve(path, dict(request, fixture=dict(worker_fault=fault)), True)
            self.retired(value)
            self.assertFalse(value["has_snapshot"], (fault, value))

    def test_lifecycle_exit_cancellation_late_and_retirement_boundaries(self):
        _, path, request = self.fixture(JointVolume(minor=0))
        for fault in ("before_spawn", "after_spawn", "after_spawn_alloc"):
            value = self.preserve(path, dict(request, fixture=dict(startup_fault=fault)), True)
            self.assertIn("startup_error", value)
            self.assertEqual(value["never_launched"], fault == "before_spawn")
            if fault != "before_spawn":
                self.retired(value)
        for fault in ("hang", "late"):
            value = self.preserve(path, dict(request, mode="pending", fixture=dict(worker_fault=fault)), True)
            self.retired(value)
            self.assertFalse(value["has_snapshot"])
        for extra in (dict(cancel=True), dict(fixture=dict(worker_fault="exit"))):
            value = self.preserve(path, dict(request, **extra), bool(extra.get("fixture")))
            self.retired(value)
            self.assertFalse(value["has_snapshot"])
        value = self.preserve(path, dict(request, mode="publication-live", fixture=dict(reply_fault="hold")), True)
        self.retired(value)
        self.assertFalse(value["has_snapshot"])
        self.assertEqual(value["before"]["diagnostic"], "ntfs_worker_exit_pending")
        value = self.preserve(path, dict(request, mode="retire-zero", fixture=dict(worker_fault="hang")), True)
        self.assertEqual(value["zero_retirement"]["retired"], value["zero_retirement"]["worker"]["observation"] == "exited")
        self.retired(value)

    def test_frame_component_limits_remain_finite(self):
        _, path, request = self.fixture()
        original = self.preserve(path, dict(request, mode="frame"))["frame"]
        base = dict(request, mode="verify", expected_source=original["result"]["capture"]["source_before"])
        for part, size in (("observation", 2 * 1024 * 1024), ("capture", 65536)):
            frame = copy.deepcopy(original)
            frame["result"][part]["overflow"] = "x" * size
            self.assertIn("error", self.preserve(path, dict(base, replace=frame)))
        frame = copy.deepcopy(original)
        frame["input"]["overflow"] = "x" * 131072
        self.assertIn("error", self.preserve(path, dict(base, replace=frame)))
        frame = copy.deepcopy(original)
        frame["regions"] = [copy.deepcopy(frame["regions"][0]) for _ in range(513)]
        self.assertIn("error", self.preserve(path, dict(base, replace=frame)))


def main():
    parser = argparse.ArgumentParser()
    for name in ("probe", "fault", "pure", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    native.PROBE, native.FAULT, native.PURE = args.probe.resolve(), args.fault.resolve(), args.pure.resolve()
    native.OUTPUT = args.output.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    summary = dict(status="pass" if result.wasSuccessful() else "fail", methods=result.testsRun,
                   failures=len(result.failures), errors=len(result.errors), calls=len(native.RECEIPTS),
                   recipe_sha256=held.file_digest(Path(__file__)), helper_sha256=held.file_digest(Path(native.__file__)),
                   receipts=native.RECEIPTS, source_receipts=native.SOURCE_RECEIPTS, unverified=held.UNVERIFIED,
                   owner_accepted=False, full_0_1_0_complete=False)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
