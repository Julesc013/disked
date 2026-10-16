"""Independent retained control semantics and real cross-process observations."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import time
import threading
import os
import unittest
import test_fat_tree_admission as admission
from test_fat_tree_review import canonical

PROBE = None
RESULTS = []


def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def invoke(value, error=None):
    completed = subprocess.run([str(PROBE)], input=canonical(value), capture_output=True, timeout=20)
    assert not completed.stderr, completed.stderr
    out = json.loads(completed.stdout)
    if error:
        assert completed.returncode == 20 and out.get("error") == error, out
    else:
        assert completed.returncode == 0 and "error" not in out, out
        assert not out["claims"]["mutation_authority"] and not out["claims"]["replay_authority"]
    RESULTS.append(dict(input_sha256=sha(canonical(value)), exit_code=completed.returncode, result=out))
    return out


def rechain(rows):
    previous = "sha256:" + "0" * 64
    result = bytearray()
    for seq, row in enumerate(rows):
        row["sequence"], row["previous"] = str(seq), previous
        raw = canonical(row) + b"\n"
        previous = sha(raw); result.extend(raw)
    return result.decode()


def load(root):
    store = root / "store"
    header = json.loads((store / "recursive-request.json").read_bytes())
    history = (store / "recursive-state.ndjson").read_text(encoding="utf-8")
    return header, history


class ReconnectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, inputs, cls.expected = admission.fixture(count=3)
        rows = admission.run(cls.root, inputs)
        assert rows[-1]["kind"] == "finished"
        cls.header, cls.history = load(cls.root)
        cls.records = [json.loads(line) for line in cls.history.splitlines()]

    def test_exact_completed_history_and_actual_native_store_read(self):
        out = invoke(dict(header=self.header, history=self.history))
        self.assertEqual("recorded_complete", out["state"])
        self.assertEqual(str(len(self.records)), out["records"])
        self.assertEqual(sha(self.history.splitlines(keepends=True)[-1].encode()), out["last_digest"])
        native = invoke(dict(operation_id=self.header["operation_id"], store=str(self.root / "store")))
        self.assertEqual("observed", native["status"], native)
        self.assertEqual("recorded_complete", native["history"]["state"])
        for name, (data, _) in self.expected.items():
            self.assertEqual(data, (self.root / "output" / name).read_bytes())
        before = {p.name:sha(p.read_bytes()) for p in (self.root / "store").iterdir()}
        late = invoke(dict(operation_id=self.header["operation_id"], store=str(self.root / "store"), cancel=True))
        self.assertEqual("too_late_recorded", late["cancellation_request"])
        self.assertEqual(before, {p.name:sha(p.read_bytes()) for p in (self.root / "store").iterdir()})

    def test_old_header_is_readable_as_historical_declarations(self):
        header = copy.deepcopy(self.header)
        header["schema"] = "org.disked.fat-tree-operation-request-prototype/1"
        header.pop("controller"); header.pop("writer")
        out = invoke(dict(header=header, history=self.history))
        self.assertEqual("recorded_complete", out["state"])
        self.assertEqual("not_established", out["claims"]["authenticity"])

    def test_prefixes_and_truncated_tail_keep_separate_claims(self):
        for count in (0, 1, 2, len(self.records) - 1):
            out = invoke(dict(header=self.header, history="".join(self.history.splitlines(keepends=True)[:count])))
            self.assertEqual(str(count), out["records"])
            self.assertNotEqual("recorded_complete", out["state"])
        for cut in (1, 10, 100):
            out = invoke(dict(header=self.header, history=self.history[:-cut]))
            self.assertEqual("truncated", out["state"])
            self.assertFalse(out["tail"]["admitted"])
            tail = self.history[:-cut].split("\n")[-1].encode()
            self.assertEqual(str(len(tail)), out["tail"]["bytes"])
            self.assertEqual(sha(tail), out["tail"]["sha256"])

    def test_rehashed_bindings_phases_and_contradictory_outcomes_are_rejected(self):
        mutations = [
            (lambda r: r[0].update(operation_id="tree-op:" + "0" * 32), "fat_tree_operation_binding"),
            (lambda r: r[0]["payload"].update(phase="observing"), "fat_tree_operation_phase"),
            (lambda r: r[1]["payload"]["worker"].update(grant_sent=True, effects_possible=True), "fat_tree_operation_status"),
            (lambda r: r[0]["payload"]["worker"]["worker"].update(pid="1"), "fat_tree_operation_binding"),
            (lambda r: r[-1]["payload"]["worker"].update(dependencies_retained=True), "fat_tree_operation_dependencies"),
            (lambda r: r[-1]["payload"]["worker"]["outcome"].update(checkpointed_bytes="0"), "fat_tree_operation_outcome"),
            (lambda r: r[-1]["payload"]["worker"]["outcome"].update(source_writes=True), "fat_tree_operation_claim"),
            (lambda r: r[-1]["payload"]["worker"]["outcome"].update(files_complete="0"), "fat_tree_operation_outcome"),
        ]
        for mutate, error in mutations:
            rows = copy.deepcopy(self.records); mutate(rows)
            invoke(dict(header=self.header, history=rechain(rows)), error=error)
        rows = copy.deepcopy(self.records); rows.append(copy.deepcopy(rows[-1]))
        invoke(dict(header=self.header, history=rechain(rows)), error="fat_tree_operation_terminal")

    def test_header_shapes_code_review_and_process_limits_are_strict(self):
        mutations = [
            (lambda h: h.update(extra=True), "fat_tree_operation_shape"),
            (lambda h: h.update(review_digest="sha256:" + "0" * 64), "fat_tree_operation_review"),
            (lambda h: h["process_owner"].update(code_sha256="0" * 64), "fat_tree_operation_binding"),
            (lambda h: h["controller"].update(pid="18446744073709551616"), "fat_tree_operation_integer"),
            (lambda h: h["writer"].update(pid="0"), "fat_tree_operation_process"),
            (lambda h: h["files"].__setitem__(1, copy.deepcopy(h["files"][0])), "fat_tree_operation_files"),
        ]
        for mutate, error in mutations:
            header = copy.deepcopy(self.header); mutate(header)
            invoke(dict(header=header, history=self.history), error=error)
        invoke(dict(header=self.header, history=self.history.replace("\n", "\r\n", 1)),
               error="fat_tree_operation_canonical")

    def test_published_outcome_cannot_change_in_later_record(self):
        rows = copy.deepcopy(self.records)
        self.assertTrue(any(r["payload"]["phase"] == "outcome_published" for r in rows))
        row = rows[-1]["payload"]["worker"]
        row["outcome"]["status"] = "partial"
        invoke(dict(header=self.header, history=rechain(rows)), error="fat_tree_operation_binding")
        rows = copy.deepcopy(self.records)
        rows[-1]["payload"]["worker"]["outcome"] = None
        invoke(dict(header=self.header, history=rechain(rows)), error="fat_tree_operation_outcome_withdrawal")

    def test_native_torn_history_does_not_authorize_cancel_or_repair(self):
        root, inputs, _ = admission.fixture()
        admission.run(root, inputs)
        header, history = load(root)
        (root / "store" / "recursive-state.ndjson").write_bytes(history[:-5].encode())
        before = {p.name:sha(p.read_bytes()) for p in (root / "store").iterdir()}
        out = invoke(dict(operation_id=header["operation_id"], store=str(root / "store"), cancel=True))
        self.assertEqual("unknown", out["status"])
        self.assertEqual("not_admitted", out["cancellation_request"])
        self.assertEqual("truncated", out["history"]["state"])
        self.assertEqual(before, {p.name:sha(p.read_bytes()) for p in (root / "store").iterdir()})

    def test_published_completion_is_independent_of_current_running_child(self):
        root, inputs, _ = admission.fixture()
        value = dict(inputs, fixture=dict(worker_fault="outcome_hold"))
        owner = subprocess.Popen([str(admission.FAULT)], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        owner.stdin.write(canonical(value)); owner.stdin.close()
        rows = []
        published = threading.Event()
        def drain():
            for line in owner.stdout:
                row = json.loads(line); rows.append(row)
                if row["kind"] == "outcome_before_exit": published.set()
        reader = threading.Thread(target=drain, daemon=True); reader.start()
        try:
            self.assertTrue(published.wait(8))
            header, _ = load(root)
            out = invoke(dict(operation_id=header["operation_id"], store=str(root / "store")))
            self.assertEqual("observed", out["status"], out)
            self.assertEqual("recorded_outcome_pending_exit", out["history"]["state"])
            self.assertEqual("running", out["writer"]["observation"])
            self.assertEqual(0, owner.wait(timeout=20)); reader.join(timeout=5)
            self.assertFalse(reader.is_alive()); self.assertFalse(owner.stderr.read())
        finally:
            if owner.poll() is None: owner.wait(timeout=20)
            reader.join(timeout=5)

    def test_native_child_header_and_operation_mismatch_leave_artifacts_unchanged(self):
        for change in ("operation", "header", "child", "process"):
            root, inputs, _ = admission.fixture()
            admission.run(root, inputs)
            header, _ = load(root)
            if change == "header":
                header["controller_host"] = "0" * 64
                (root / "store" / "recursive-request.json").write_bytes(canonical(header))
            elif change == "child":
                cancel = root / "store" / "recursive-cancel"
                old = root / "store" / "retained-cancel"
                assert cancel.resolve().is_relative_to(root.resolve()) and old.resolve().is_relative_to(root.resolve())
                cancel.rename(old); cancel.write_bytes(b"0")
            elif change == "process":
                header["writer"] = dict(pid=str(os.getpid()), created="1")
                rows = [json.loads(line) for line in (root / "store" / "recursive-state.ndjson").read_text().splitlines()]
                for row in rows:
                    row["payload"]["worker"]["worker"].update(header["writer"])
                (root / "store" / "recursive-state.ndjson").write_text(rechain(rows), encoding="utf-8", newline="\n")
                (root / "store" / "recursive-request.json").write_bytes(canonical(header))
            before = {p.name:sha(p.read_bytes()) for p in (root / "store").iterdir()}
            op = "tree-op:" + "0" * 32 if change == "operation" else header["operation_id"]
            out = invoke(dict(operation_id=op, store=str(root / "store"), cancel=True))
            self.assertEqual("unknown", out["status"])
            self.assertEqual("not_admitted", out["cancellation_request"])
            self.assertEqual(before, {p.name:sha(p.read_bytes()) for p in (root / "store").iterdir()})

    def test_actual_live_cross_process_observation_and_cooperative_cancel(self):
        root, inputs, _ = admission.fixture()
        value = dict(inputs, wait_ms="10000", fixture=dict(worker_fault="execute_wait_cancel"))
        owner = subprocess.Popen([str(admission.FAULT)], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        owner.stdin.write(canonical(value)); owner.stdin.close()
        rows = []
        def drain():
            for line in owner.stdout:
                rows.append(json.loads(line))
        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        try:
            end = time.monotonic() + 8
            header = None
            while time.monotonic() < end:
                try:
                    header, history = load(root)
                    if (root / "output").exists() and len(history.splitlines()) >= 2:
                        break
                except (OSError, ValueError):
                    pass
                time.sleep(.01)
            self.assertTrue(header and (root / "output").exists())
            out = invoke(dict(operation_id=header["operation_id"], store=str(root / "store")))
            self.assertEqual("running", out["controller"]["observation"], out)
            self.assertEqual("running", out["writer"]["observation"], out)
            cancelled = invoke(dict(operation_id=header["operation_id"], store=str(root / "store"), cancel=True))
            self.assertEqual("requested", cancelled["cancellation_request"], cancelled)
            self.assertEqual(0, owner.wait(timeout=20)); reader.join(timeout=5)
            self.assertFalse(reader.is_alive()); self.assertFalse(owner.stderr.read())
            self.assertEqual("partial", rows[-1]["observation"]["worker"]["outcome"]["status"])
            self.assertTrue(rows[-1]["observation"]["worker"]["outcome"]["cancellation_observed"])
            final = invoke(dict(operation_id=header["operation_id"], store=str(root / "store")))
            self.assertEqual("recorded_partial", final["history"]["state"], final)
        finally:
            # The bounded owning probe retires its own job; never start a replacement.
            if owner.poll() is None:
                owner.wait(timeout=20)
            reader.join(timeout=5)


def main():
    global PROBE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--owner", type=Path, required=True)
    parser.add_argument("--fault-owner", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    PROBE = args.probe.resolve()
    admission.PROBE, admission.FAULT = args.owner.resolve(), args.fault_owner.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReconnectTests))
    args.output.write_text(json.dumps(dict(passed=result.wasSuccessful(), methods=result.testsRun,
                          cases=len(RESULTS), records=RESULTS, native_owners=admission.RESULTS), indent=2) + "\n",
                          encoding="utf-8", newline="\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
