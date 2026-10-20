"""Native ownership, fresh review admission and independently retained store facts."""
import argparse
import copy
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_fat_tree_extraction import collection
from test_fat_tree_file import write
from test_fat_content_stream import fixture as content_fixture
from test_fat_tree_content import image
from test_fat_tree_review import canonical, rebind

PROBE = None
FAULT = None
RESULTS = []


def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def file_id(path):
    class Id(ctypes.Structure):
        _fields_ = [("volume", ctypes.c_ulonglong), ("identifier", ctypes.c_ubyte * 16)]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p,
                                  ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.GetFileInformationByHandleEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.CreateFileW(str(path), 0x80, 7, None, 3, 0x02200000, None)
    assert handle != ctypes.c_void_p(-1).value, ctypes.get_last_error()
    try:
        value = Id()
        assert kernel.GetFileInformationByHandleEx(handle, 18, ctypes.byref(value), ctypes.sizeof(value)), ctypes.get_last_error()
        return dict(file_id=bytes(value.identifier).hex(), volume_id=str(value.volume))
    finally:
        kernel.CloseHandle(handle)


def fixture(bits=16, count=3):
    root = Path(tempfile.mkdtemp(prefix="disked-native-admission-"))
    tree, expected = collection(bits, count=count)
    source, destination, ledger, store = (root / name for name in ("source.img", "output", "metadata.ndjson", "store"))
    write(tree, source)
    store.mkdir()
    inputs = dict(source=str(source), destination=str(destination), ledger=str(ledger), store=str(store),
                  offset=str(tree.offset), length=str(tree.length), copy=str(tree.fat_copy))
    return root, inputs, expected


def run(root, inputs, extra=None, fault=False, store_fault=None):
    value = dict(inputs, **(extra or {}))
    source = root / "source.img"
    original = sha(source.read_bytes())
    env = {k:v for k,v in os.environ.items() if k != "DISKED_TEST_STORE_FAULT"}
    if store_fault:
        env["DISKED_TEST_STORE_FAULT"] = store_fault
    completed = subprocess.run([str(FAULT if fault else PROBE)], input=canonical(value),
                               capture_output=True, env=env, timeout=240 if value.get("wait_ms")=="180000" else 100)
    assert completed.returncode == 0 and not completed.stderr, (completed.returncode, completed.stderr)
    rows = [json.loads(line) for line in completed.stdout.splitlines()]
    assert rows and sha(source.read_bytes()) == original
    if rows[-1]["kind"] == "finished":
        final = rows[-1]["observation"]
        assert final["worker"]["worker"]["observation"] == "exited", final
        assert not final["worker"]["dependencies_retained"] and rows[-1]["retained"] == "0"
        assert not final["persistent_reconnect_qualified"]
    if rows[-1].get("retirement"):
        state = rows[-1]["retirement"]["worker"]
        assert state["worker"]["observation"] in ("not_started", "exited"), state
    RESULTS.append(dict(folder=str(root), extra=extra, fault=fault, store_fault=store_fault,
                        source_sha256=original, stdout_sha256=sha(completed.stdout), rows=rows))
    return rows


def prepare(root, inputs, fault=False):
    rows = run(root, inputs, dict(mode="prepare"), fault=fault)
    p = next(row for row in rows if row["kind"] == "prepared")
    assert not any((root / name).exists() for name in ("output", "metadata.ndjson"))
    assert list((root / "store").iterdir()) == []
    assert p["observation"]["operation_id"] is None and not p["observation"]["store_effects_possible"]
    return p


def controls(root, prepared=None):
    store = root / "store"
    header = json.loads((store / "recursive-request.json").read_bytes())
    assert header["schema"] == "org.disked.fat-tree-operation-request-prototype/2"
    assert (store / "recursive-request.json").read_bytes() == canonical(header)
    assert header["operation_id"].startswith("tree-op:") and len(header["operation_id"]) == 40
    assert header["review_digest"] == sha(b"disked:fat-tree-extraction-review:1\n" + canonical(header["review"]))
    if prepared:
        assert header["review"] == prepared["review"] and header["review_digest"] == prepared["digest"]
    for name, expected in zip(("recursive-request.json", "recursive-cancel", "recursive-state.ndjson"),
                              header["files"], strict=True):
        actual = file_id(store / name)
        assert all(actual[key] == expected[key] for key in ("file_id", "volume_id"))
    assert (store / "recursive-cancel").read_bytes() in (b"0", b"1")
    previous = "sha256:" + "0" * 64
    records = []
    for seq, line in enumerate((store / "recursive-state.ndjson").read_bytes().splitlines(keepends=True)):
        assert line.endswith(b"\n")
        row = json.loads(line)
        assert line == canonical(row) + b"\n"
        assert row["sequence"] == str(seq) and row["previous"] == previous
        assert row["operation_id"] == header["operation_id"] and row["review_digest"] == header["review_digest"]
        assert row["schema"] == "org.disked.fat-tree-state-record-prototype/1"
        previous = sha(line); records.append(row)
    assert records and len(records) <= 64
    assert sum(p.stat().st_size for p in store.iterdir()) <= 1048576
    assert records[0]["payload"]["phase"] == "admitted"
    return header, records


class AdmissionTests(unittest.TestCase):
    def test_cooperative_cancel_keeps_control_request_partial_tree_and_evidence(self):
        root, inputs, _ = fixture()
        rows = run(root, inputs, dict(cancel_when_root="yes",
                        fixture=dict(worker_fault="execute_wait_cancel")), fault=True)
        final = rows[-1]["observation"]["worker"]
        self.assertEqual("partial", final["outcome"]["status"])
        self.assertTrue(final["outcome"]["cancellation_observed"])
        self.assertTrue((root / "output").exists() and (root / "metadata.ndjson").exists())
        self.assertEqual(b"1", (root / "store" / "recursive-cancel").read_bytes())
        controls(root)

    def test_large_noncontiguous_file_keeps_control_history_bounded(self):
        root = Path(tempfile.mkdtemp(prefix="disked-native-admission-large-"))
        nodes = [n + shift for n in range(3, 33003, 3) for shift in (2, 0, 1)]
        request, expected, _, _ = content_fixture(16, 40000, nodes=nodes)
        source = root / "source.img"; image(request, source)
        (root / "store").mkdir()
        inputs = dict(source=str(source), destination=str(root / "output"),
                      ledger=str(root / "metadata.ndjson"), store=str(root / "store"),
                      offset=request["offset"], length=request["length"])
        rows = run(root, inputs, dict(wait_ms="180000"))
        self.assertEqual("complete", rows[-1]["observation"]["worker"]["outcome"]["status"])
        self.assertEqual(expected, (root / "output" / "CONTENT.BIN").read_bytes())
        _, records = controls(root)
        self.assertLessEqual(len(records), 64)

    def test_published_outcome_keeps_native_store_pins_until_actual_exit(self):
        root, inputs, _ = fixture()
        original = sha((root / "source.img").read_bytes())
        value = dict(inputs, fixture=dict(worker_fault="outcome_hold"))
        child = subprocess.Popen([str(FAULT)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        child.stdin.write(canonical(value)); child.stdin.close()
        rows = []
        for line in child.stdout:
            row = json.loads(line); rows.append(row)
            if row["kind"] != "outcome_before_exit":
                continue
            state = row["observation"]
            self.assertTrue(state["worker"]["dependencies_retained"])
            self.assertEqual("complete", state["worker"]["outcome"]["status"])
            before, after = root / "store", root / "renamed-store"
            assert before.resolve().is_relative_to(root.resolve()) and after.resolve().is_relative_to(root.resolve())
            with self.assertRaises(OSError):
                before.rename(after)
        self.assertEqual(0, child.wait(timeout=30))
        self.assertFalse(child.stderr.read())
        self.assertTrue(any(r["kind"] == "outcome_before_exit" for r in rows))
        self.assertEqual("exited", rows[-1]["observation"]["worker"]["worker"]["observation"])
        self.assertEqual(original, sha((root / "source.img").read_bytes()))
        controls(root)
        RESULTS.append(dict(folder=str(root), extra=value["fixture"], fault=True,
                            source_sha256=original, rows=rows))

    def test_native_prepare_and_independent_store_identity_without_effects(self):
        root, inputs, _ = fixture()
        p = prepare(root, inputs)
        observed = p["review"]["operation_store"]["observed"]
        actual = file_id(root / "store")
        self.assertEqual(actual, {k:observed["file"][k] for k in actual})
        self.assertEqual(str(root / "store"), observed["path"])

    def test_fresh_process_execution_and_retained_header_state_content(self):
        for bits in (12, 16, 32):
            root, inputs, expected = fixture(bits, count=150)
            p = prepare(root, inputs)
            rows = run(root, dict(review=p["review"], review_digest=p["digest"], wait_ms="180000"))
            self.assertEqual("finished", rows[-1]["kind"], rows[-1])
            final = rows[-1]["observation"]
            self.assertEqual("complete", final["worker"]["outcome"]["status"], rows[-1])
            header, records = controls(root, p)
            self.assertEqual(final["operation_id"], header["operation_id"])
            self.assertEqual("dispatch_possible", records[1]["payload"]["phase"])
            self.assertEqual("exited", records[-1]["payload"]["phase"])
            self.assertTrue(any(r["payload"]["phase"] == "outcome_published" for r in records))
            self.assertNotEqual(p["observation"]["worker"]["worker"]["pid"],
                                final["worker"]["worker"]["pid"])
            for name, (data, _) in expected.items():
                self.assertEqual(data, (root / "output" / name).read_bytes())

    def test_each_grant_and_wrong_digest_refuse_before_native_paths(self):
        root, inputs, _ = fixture()
        p = prepare(root, inputs)
        for missing in ("source", "destination", "ledger", "operation", "host"):
            rows = run(root, dict(review=p["review"], missing_grant=missing))
            self.assertEqual("fat_tree_review_grant", rows[-1]["code"])
            self.assertEqual([], list((root / "store").iterdir()))
        rows = run(root, dict(review=p["review"], review_digest="sha256:" + "0" * 64))
        self.assertEqual("fat_tree_review_grant", rows[-1]["code"])
        review = copy.deepcopy(p["review"])
        review["operation_store"]["observed"]["path"] = "invalid-unopened-native-path"
        rebind(review["operation_store"])
        rows = run(root, dict(review=review, missing_grant="operation"))
        self.assertEqual("fat_tree_review_grant", rows[-1]["code"])
        self.assertFalse((root / "output").exists())

    def test_changed_source_store_code_or_namespace_refuse_no_control_writes(self):
        for change in ("source", "store", "code", "namespace"):
            root, inputs, _ = fixture()
            p = prepare(root, inputs)
            review = copy.deepcopy(p["review"])
            if change == "source":
                source = root / "source.img"; stat = source.stat()
                os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10000000))
            elif change == "store":
                before, after = root / "store", root / "old-store"
                assert before.resolve().is_relative_to(root.resolve()) and after.resolve().is_relative_to(root.resolve())
                before.rename(after); before.mkdir()
            elif change == "code":
                for role, key in (("executable", "sha256"), ("provider", "code_sha256")):
                    review["backend"]["resources"][role]["observed"][key] = "sha256:" + "1" * 64
                    rebind(review["backend"]["resources"][role])
            else:
                review["backend"]["selection"]["tree_digest"] = "sha256:" + "1" * 64
            rows = run(root, dict(review=review))
            self.assertEqual("error", rows[-1]["kind"])
            self.assertFalse((root / "output").exists() or (root / "metadata.ndjson").exists())
            self.assertEqual([], list((root / "store").iterdir()))

    def test_reserved_children_and_control_resource_aliases_preserve_foreign_files(self):
        for name in ("recursive-request.json", "recursive-cancel", "recursive-state.ndjson"):
            root, inputs, _ = fixture()
            marker = root / "store" / name
            marker.write_bytes(b"foreign retained resource")
            rows = run(root, inputs)
            self.assertEqual("fat_tree_store_reserved_exists", rows[-1]["code"])
            self.assertEqual(b"foreign retained resource", marker.read_bytes())
            self.assertFalse((root / "output").exists())
        for key in ("destination", "ledger"):
            root, inputs, _ = fixture()
            inputs[key] = str(root / "store" / "RECURSIVE-REQUEST.JSON")
            rows = run(root, inputs)
            self.assertEqual("fat_tree_store_resource_alias", rows[-1]["code"])
            self.assertEqual([], list((root / "store").iterdir()))

    def test_owned_hangs_partial_effects_and_real_exit_preserve_store(self):
        for mode in ("prepare_hang", "execute_hang"):
            root, inputs, _ = fixture()
            rows = run(root, inputs, dict(wait_ms="30000" if mode=="execute_hang" else "400",
                    retire_after_root_ms="400" if mode=="execute_hang" else "0", fixture=dict(worker_fault=mode)), fault=True)
            before = next(r for r in rows if r["kind"] == "before_retirement")
            self.assertTrue(before["observation"]["worker"]["dependencies_retained"])
            self.assertEqual("31", rows[-1]["observation"]["worker"]["worker"]["exit_code"])
            if mode == "execute_hang":
                _, records = controls(root)
                self.assertEqual("exited", records[-1]["payload"]["phase"])
                self.assertIsNone(records[-1]["payload"]["worker"]["outcome"])
                self.assertTrue((root / "output").exists())
            else:
                self.assertEqual([], list((root / "store").iterdir()))

    def test_interrupted_control_creation_is_retained_before_backend_effects(self):
        for mode in ("fat_tree_request.full", "fat_tree_request.short", "fat_tree_request.flush",
                     "fat_tree_cancel.full", "fat_tree_state.full",
                     "fat_tree_state.short", "fat_tree_state.flush"):
            root, inputs, _ = fixture()
            rows = run(root, inputs, fault=True, store_fault=mode)
            self.assertEqual("error", rows[-1]["kind"], rows[-1])
            self.assertFalse((root / "output").exists() or (root / "metadata.ndjson").exists())
            self.assertTrue((root / "store" / "recursive-request.json").exists())
            self.assertTrue(rows[-1]["retirement"]["store_effects_possible"])
            state = (root / "store" / "recursive-state.ndjson").read_bytes()
            if mode == "fat_tree_state.short":
                self.assertTrue(state and not state.endswith(b"\n"))
                self.assertEqual(0, state.count(b"\n"))
            if mode == "fat_tree_state.flush":
                self.assertEqual(1, len(state.splitlines()))
                self.assertEqual("admitted", json.loads(state)["payload"]["phase"])
            if mode.startswith("fat_tree_state."):
                self.assertNotIn(b'"phase":"admission_uncertain"', state)
                self.assertNotIn(b'"phase":"exited"', state)

    def test_normal_store_ignores_fault_environment(self):
        root, inputs, _ = fixture()
        rows = run(root, inputs, store_fault="fat_tree_request.full")
        self.assertEqual("complete", rows[-1]["observation"]["worker"]["outcome"]["status"])
        controls(root)


def main():
    global PROBE, FAULT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--fault", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    PROBE, FAULT = args.probe.resolve(), args.fault.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AdmissionTests))
    args.output.write_text(json.dumps(dict(passed=result.wasSuccessful(), methods=result.testsRun,
                           cases=len(RESULTS), records=RESULTS), indent=2) + "\n",
                           encoding="utf-8", newline="\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
