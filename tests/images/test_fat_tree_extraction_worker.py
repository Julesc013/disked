"""Actual owned child, exact grant and dependency lifetime tests on generated files."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_fat_tree_extraction import collection, encoded, ledger_records
from test_fat_tree_file import write
from test_fat_tree_content import image
from test_fat_content_stream import fixture

PROBE = None
FAULT = None
RESULTS = []


def run(tree=None, request=None, extra=None, fault=False):
    folder = Path(tempfile.mkdtemp(prefix="disked-owned-tree-writer-"))
    source, destination, ledger = folder/"source.img", folder/"output", folder/"metadata.ndjson"
    if tree is not None:
        write(tree, source)
        request = tree.request()
    else:
        image(request, source)
    original = source.read_bytes()
    inputs = {"source": str(source), "offset": request["offset"], "length": request["length"],
              "destination": str(destination), "ledger": str(ledger), **(extra or {})}
    completed = subprocess.run([str(FAULT if fault else PROBE)], input=encoded(inputs),
                               capture_output=True, timeout=100)
    assert completed.returncode == 0 and not completed.stderr, (completed.returncode, completed.stderr.decode())
    rows = [json.loads(line) for line in completed.stdout.splitlines()]
    assert rows
    for row in rows:
        state = row.get('value') or row.get('retirement')
        if isinstance(state, dict) and 'dependencies_retained' in state:
            assert state['dependencies_retained'] == (state['worker']['observation'] not in ('exited','not_started')), state
    final = rows[-1]
    if final["kind"] == "finished":
        state = final["value"]
        assert state["worker"]["observation"] == "exited", state
        assert not state["dependencies_retained"] and final["retained"] == "0"
        assert state["claims"]["compiled_effects_capable"]
        assert not state["claims"]["mutation_authority"] and not state["claims"]["physical_admission"]
        assert state["effects_possible"] == state["grant_sent"]
        for row in rows:
            if row["kind"] in ("before_retirement", "outcome_before_exit"):
                assert row["value"]["dependencies_retained"]
    if final["kind"] == "startup_error":
        assert final["retirement"]["worker"]["observation"] in ("not_started", "exited")
        assert not final["retirement"]["dependencies_retained"]
    prepared = next((row for row in rows if row["kind"] == "prepared"), None)
    records = []
    if prepared and ledger.exists():
        records = ledger_records(ledger, prepared["definition"], prepared["digest"],
            final["kind"] == "finished" and final["value"]["outcome"] is not None and
            final["value"]["outcome"]["status"] == "complete")
    if prepared and final["kind"] == "finished":
        actual = final["value"]["worker"]
        context = prepared["definition"]["selection"]["preparation_context"]
        assert context["process_id"] == actual["pid"] and context["process_created"] == actual["created"]
        assert prepared["owner"]["worker_epoch"] == final["value"]["worker_epoch"]
        assert prepared["owner"]["attempt_id"] == final["value"]["attempt_id"]
        assert prepared["definition"]["resources"]["executable"]["observed"]["sha256"] == "sha256:" + final["value"]["code_sha256"]
        if final["value"]["outcome"]:
            outcome = final["value"]["outcome"]
            assert outcome["definition_digest"] == prepared["digest"]
            assert outcome["attempt_id"] == final["value"]["attempt_id"]
            assert int(outcome["ledger_records"]) == len(records)
    assert source.read_bytes() == original
    RESULTS.append({"fault": fault, "extra": extra, "last": final, "records": len(records),
                    "source_sha256": hashlib.sha256(original).hexdigest(),
                    "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
                    "folder": str(folder)})
    return folder, rows, records


class WorkerTests(unittest.TestCase):
    def test_complete_variants_in_actual_owned_child(self):
        for bits in (12, 16, 32):
            tree, expected = collection(bits, count=150)
            folder, rows, records = run(tree)
            self.assertEqual("complete", rows[-1]["value"]["outcome"]["status"], rows[-1])
            self.assertEqual("0", rows[-1]["value"]["worker"]["exit_code"])
            for name, (data, _) in expected.items():
                self.assertEqual(data, (folder/"output"/name).read_bytes())
            self.assertEqual(150, sum(record["kind"] == "file-complete" for record in records))

    def test_large_content_and_worker_budget(self):
        nodes = [n + shift for n in range(3, 33003, 3) for shift in (2, 0, 1)]
        request, expected, _, _ = fixture(16, 40000, nodes=nodes)
        folder, rows, _ = run(request=request, extra={"wait_ms": "60000"})
        self.assertEqual("complete", rows[-1]["value"]["outcome"]["status"], rows[-1])
        self.assertEqual(expected, (folder/"output/CONTENT.BIN").read_bytes())

    def test_prepared_wait_and_invalid_grant_have_no_outputs(self):
        tree, _ = collection(count=2)
        for mode in ("hold_prepared", "prepare_only", "cancel_prepared", "bad_grant"):
            folder, rows, _ = run(tree, extra={"mode": mode, "wait_ms": "200"})
            self.assertTrue(any(row["kind"] == "prepared" for row in rows))
            self.assertFalse((folder/"output").exists() or (folder/"metadata.ndjson").exists())
            self.assertFalse(rows[-1]["value"]["grant_sent"])
        folder, rows, _ = run(tree, fault=True, extra={"fixture": {"worker_fault": "late"}, "cancel_after_ms": "10", "wait_ms": "1000"})
        self.assertFalse((folder/"output").exists() or (folder/"metadata.ndjson").exists())

    def test_hangs_keep_dependencies_until_owned_job_exit(self):
        tree, _ = collection(count=2)
        for mode in ("prepare_hang", "execute_hang"):
            folder, rows, records = run(tree, fault=True, extra={"fixture": {"worker_fault": mode}, "wait_ms": "300"})
            before = next(row["value"] for row in rows if row["kind"] == "before_retirement")
            self.assertEqual("running", before["worker"]["observation"])
            self.assertTrue(before["dependencies_retained"])
            self.assertEqual("31", rows[-1]["value"]["worker"]["exit_code"])
            if mode == "prepare_hang":
                self.assertFalse((folder/"output").exists() or (folder/"metadata.ndjson").exists())
            else:
                self.assertTrue((folder/"output").exists() and records)
                self.assertTrue(before["grant_sent"])
                self.assertNotEqual("outcome", records[-1]["kind"])

    def test_poisoned_definitions_owners_process_and_hashes_never_get_grants(self):
        tree, _ = collection(count=2)
        for mode in ("definition_changed", "definition_rehashed", "owner_changed", "process_changed", "publication_digest"):
            folder, rows, _ = run(tree, fault=True, extra={"fixture": {"worker_fault": mode}, "wait_ms": "1000"})
            self.assertEqual("unknown", rows[-1]["value"]["status"])
            self.assertFalse(rows[-1]["value"]["grant_sent"])
            self.assertFalse((folder/"output").exists() or (folder/"metadata.ndjson").exists())

    def test_late_outcome_publication_is_not_actual_exit(self):
        tree, _ = collection(count=2)
        folder, rows, _ = run(tree, fault=True, extra={"fixture": {"worker_fault": "outcome_hold"}})
        before = next(row["value"] for row in rows if row["kind"] == "outcome_before_exit")
        self.assertEqual("running", before["worker"]["observation"])
        self.assertEqual("complete", before["outcome"]["status"])
        self.assertTrue(before["dependencies_retained"])
        self.assertEqual("complete", rows[-1]["value"]["outcome"]["status"])

    def test_actual_unexpected_exits_preserve_effects_and_ledger(self):
        tree, _ = collection(count=2)
        for mode in ("exit_after_root", "exit_after_completion"):
            folder, rows, records = run(tree, fault=True, extra={"fixture": {"worker_fault": mode}})
            self.assertEqual("93", rows[-1]["value"]["worker"]["exit_code"])
            self.assertIsNone(rows[-1]["value"]["outcome"])
            self.assertTrue((folder/"output").exists() and records)
            if mode == "exit_after_completion":
                self.assertEqual("complete", records[-1]["payload"]["status"])
            else:
                self.assertNotEqual("outcome", records[-1]["kind"])

    def test_before_and_after_spawn_failure_ownership(self):
        tree, _ = collection(count=2)
        for mode in ("before_spawn", "after_spawn", "after_spawn_alloc"):
            folder, rows, _ = run(tree, fault=True, extra={"fixture": {"startup_fault": mode}})
            self.assertEqual("startup_error", rows[-1]["kind"])
            self.assertFalse((folder/"output").exists() or (folder/"metadata.ndjson").exists())

    def test_normal_image_rejects_fixture_controls(self):
        tree, _ = collection(count=2)
        folder, rows, _ = run(tree, extra={"fixture": {"worker_fault": "prepare_hang"}})
        self.assertEqual("error", rows[-1]["kind"])
        self.assertEqual("fat_tree_writer_fixture_not_compiled", rows[-1]["code"])
        self.assertFalse((folder/"output").exists() or (folder/"metadata.ndjson").exists())

    def test_each_explicit_grant_and_cooperative_effect_cancellation(self):
        tree, _ = collection(count=2)
        for role in ("source", "destination", "ledger", "host"):
            folder, rows, _ = run(tree, extra={"missing_grant": role})
            self.assertTrue(any(row["kind"] == "grant_refused" for row in rows))
            self.assertFalse((folder/"output").exists() or (folder/"metadata.ndjson").exists())
        folder, rows, records = run(tree, fault=True, extra={
            "fixture": {"worker_fault": "execute_wait_cancel"}, "cancel_after_pulse": "5"})
        self.assertEqual("partial", rows[-1]["value"]["outcome"]["status"])
        self.assertTrue(rows[-1]["value"]["outcome"]["cancellation_observed"])
        self.assertTrue((folder/"output").exists() and records)
        self.assertEqual("0", rows[-1]["value"]["worker"]["exit_code"])

    def test_shared_four_worker_quota(self):
        tree, _ = collection(count=2)
        folder, rows, _ = run(tree, extra={"mode": "quota"})
        self.assertEqual("quota", rows[-1]["kind"])
        self.assertTrue(rows[-1]["fifth_refused"])
        self.assertTrue(all(value["worker"]["observation"] == "running" for value in rows[-1]["before"]))
        self.assertIn(rows[-1]["fifth_retirement"]["worker"]["observation"], ("not_started", "exited"))
        self.assertEqual(4, len(rows[-1]["retirement"]))
        for value in rows[-1]["retirement"]:
            self.assertEqual("exited", value["worker"]["observation"])
            self.assertFalse(value["dependencies_retained"])
        self.assertFalse((folder/"output").exists() or (folder/"metadata.ndjson").exists())


def main():
    global PROBE, FAULT
    parser = argparse.ArgumentParser()
    for name in ("probe", "fault", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    PROBE, FAULT = args.probe.resolve(), args.fault.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(WorkerTests))
    args.output.write_text(json.dumps({"passed": result.wasSuccessful(), "methods": result.testsRun,
                                      "cases": len(RESULTS), "records": RESULTS}, indent=2) + "\n",
                           encoding="utf-8", newline="\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
