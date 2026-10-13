"""Independent hash/framing and semantic oracles for source-free ledger inspection."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "images"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
import test_fat_tree_extraction as writer
import test_fat_tree_extraction_worker as owned
from test_fat_tree_file import Tree, short
from test_fat_content_stream import fixture

PROBE = None
RESULTS = []


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def rechained(records):
    previous = "sha256:" + "0" * 64
    out = bytearray()
    for number, row in enumerate(records):
        row["sequence"], row["previous"] = str(number), previous
        line = canonical(row) + b"\n"
        previous = sha(line)
        out.extend(line)
    return bytes(out)


def inspect(data, options=(), error=None):
    result = subprocess.run([str(PROBE), *options], input=data, capture_output=True, timeout=30)
    assert not result.stderr, result.stderr
    value = json.loads(result.stdout)
    if error is None:
        assert result.returncode == 0 and "error" not in value, (result.returncode, value)
        lines = data.splitlines(keepends=True)
        complete = [line for line in lines if line.endswith(b"\n")]
        tail = lines[-1] if lines and not lines[-1].endswith(b"\n") else b""
        assert value["records"] == str(len(complete))
        assert value["admitted_bytes"] == str(sum(map(len, complete)))
        assert value["input_bytes"] == str(len(data))
        assert value["last_record_digest"] == (sha(complete[-1]) if complete else None)
        assert value["tail"] == {"admitted": False, "bytes": str(len(tail)), "sha256": sha(tail)}
        assert value["claims"]["authenticity"] == "not_established"
        assert value["claims"]["current_destination_verification"] == "not_performed"
        assert value["claims"]["worker_exit"] == "not_observed"
        assert all(not value["claims"][key] for key in
                   ("mutation_authority", "replay_authority", "physical_admission", "owner_accepted"))
    else:
        assert result.returncode == 20 and value.get("error", "").startswith(error), value
    RESULTS.append({"input_bytes": len(data), "input_sha256": sha(data),
                    "options": list(options), "exit_code": result.returncode, "result": value})
    return value


class HistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree, cls.expected = writer.collection(12, count=150)
        cls.folder, cls.rows, cls.records, original = writer.run(tree)
        cls.raw = (cls.folder / "metadata.ndjson").read_bytes()
        assert original == (cls.folder / "source.img").read_bytes()
        # Withdraw the sole recorded source path without deleting any fixture.
        source = cls.folder / "source.img"
        withdrawn = cls.folder / "withdrawn-source.img"
        assert source.parent.resolve() == withdrawn.parent.resolve()
        source.rename(withdrawn)
        assert not source.exists() and withdrawn.read_bytes() == original

    def test_complete_original_native_history_without_source(self):
        value = inspect(self.raw)
        self.assertEqual("recorded_complete", value["state"])
        self.assertEqual("150", value["tree_entries_observed"])
        self.assertEqual("150", value["files_complete_recorded"])
        self.assertEqual(str(sum(len(data) for data, _ in self.expected.values())),
                         value["checkpointed_bytes_recorded"])
        self.assertEqual("150", value["metadata_fields_applied_recorded"])
        self.assertEqual("450", value["metadata_fields_unapplied_recorded"])
        for name, (expected, _) in self.expected.items():
            self.assertEqual(expected, (self.folder / "output" / name).read_bytes())

    def test_partition_invariance(self):
        expected = inspect(self.raw)
        for size in (1, 31, 512, 8192, 65536, 262144):
            self.assertEqual(expected, inspect(self.raw, ("--chunk", str(size))))

    def test_other_fat_variants_and_native_times(self):
        for bits in (16, 32):
            tree, expected = writer.collection(bits, count=150)
            folder, _, _, _ = writer.run(tree, extra={"time_interpretation": "fixed_offset",
                                                     "utc_offset_minutes": "330"})
            value = inspect((folder / "metadata.ndjson").read_bytes())
            self.assertEqual("recorded_complete", value["state"])
            self.assertEqual("600", value["metadata_fields_applied_recorded"])
            self.assertEqual("0", value["metadata_fields_unapplied_recorded"])
            for name, (data, _) in expected.items():
                self.assertEqual(data, (folder / "output" / name).read_bytes())

    def test_large_noncontiguous_content(self):
        nodes = [n + shift for n in range(3, 33003, 3) for shift in (2, 0, 1)]
        request, expected, _, _ = fixture(16, 40000, nodes=nodes)
        folder, _, records, _ = writer.run(request=request)
        self.assertGreater(sum(r["kind"] == "checkpoint" for r in records), 128)
        value = inspect((folder / "metadata.ndjson").read_bytes())
        self.assertEqual("recorded_complete", value["state"])
        self.assertEqual(str(len(expected)), value["checkpointed_bytes_recorded"])
        self.assertEqual(expected, (folder / "output" / "CONTENT.BIN").read_bytes())

    def test_directory_deferred_results(self):
        tree = Tree(16)
        tree.directory([writer.stamp(short(name=b"ROOT       ", attributes=16, cluster=10))])
        parent = "entry:" + str(tree.root)
        for cluster in range(10, 22):
            tree.chain([cluster])
            tree.directory([writer.stamp(short(name=f"D{cluster:02d}".encode().ljust(11, b" "),
                                                attributes=16, cluster=cluster + 1))],
                           parent=parent, clusters=[cluster])
            parent = "entry:" + str(tree.cluster(cluster))
        tree.chain([22])
        tree.directory([short(name=b"LEAF    TXT")], parent=parent, clusters=[22])
        folder, _, _, _ = writer.run(tree)
        value = inspect((folder / "metadata.ndjson").read_bytes())
        self.assertEqual("recorded_complete", value["state"])
        self.assertEqual("13", value["directory_create_intents"])
        self.assertEqual("1", value["files_complete_recorded"])

    def test_actual_cancellation_and_abrupt_exit_histories(self):
        for boundary in ("root_created", "file_created", "chunk_written", "chunk_verified", "metadata_applied"):
            for mode in ("cancel_boundary", "exit_boundary"):
                tree, _ = writer.collection(count=2)
                folder, _, records, _ = writer.run(tree, extra={mode: boundary})
                value = inspect((folder / "metadata.ndjson").read_bytes())
                self.assertEqual("recorded_partial" if mode == "cancel_boundary" else "unresolved", value["state"])
                if mode == "exit_boundary":
                    self.assertTrue(not records or records[-1]["kind"] != "outcome")
                self.assertTrue((folder / "output").exists())
        tree, _ = writer.collection(count=2)
        folder, _, _, _ = writer.run(tree, extra={"exit_boundary": "complete_flushed"})
        self.assertEqual("recorded_complete", inspect((folder / "metadata.ndjson").read_bytes())["state"])

    def test_actual_owned_worker_histories(self):
        for extra, expected in (({}, "recorded_complete"),
                                ({"fixture": {"worker_fault": "exit_after_root"}}, "unresolved"),
                                ({"fixture": {"worker_fault": "exit_after_completion"}}, "recorded_complete")):
            tree, _ = writer.collection(count=2)
            folder, rows, _ = owned.run(tree, extra=extra, fault=bool(extra))
            self.assertEqual("exited", rows[-1]["value"]["worker"]["observation"])
            self.assertEqual(expected, inspect((folder / "metadata.ndjson").read_bytes())["state"])

    def test_empty_prefix_and_incomplete_tail(self):
        self.assertEqual("empty", inspect(b"")["state"])
        lines = self.raw.splitlines(keepends=True)
        for count in (1, 2, 3, 9, len(lines) - 1):
            self.assertEqual("unresolved", inspect(b"".join(lines[:count]))["state"])
        for cut in (1, 10, len(lines[-1]) - 1):
            data = self.raw[:-cut]
            self.assertEqual("truncated", inspect(data)["state"])
        self.assertEqual("truncated", inspect(self.raw + b'{"not":"admitted"')["state"])

    def test_hash_canonical_and_version_errors(self):
        for data in (self.raw.replace(b'"sequence":"0"', b'"sequence":"1"', 1),
                     self.raw.replace(b'"previous":"sha256:', b'"previous":"sha257:', 1),
                     self.raw.replace(b'"schema":"org.disked.fat-tree-extraction-record-prototype/1"',
                                      b'"schema":"org.disked.fat-tree-extraction-record-prototype/2"', 1),
                     self.raw.replace(b'":', b'": ', 1), self.raw.replace(b"\n", b"\r\n", 1),
                     b'{"sequence":"0","sequence":"0"}\n', self.raw + b"\n"):
            inspect(data, error="")

    def test_rehashed_cross_record_contradictions(self):
        mutations = [
            ("checkpoint", lambda p: p.update(bytes=str(int(p["bytes"]) + 1))),
            ("checkpoint", lambda p: p.update(offset="1")),
            ("checkpoint", lambda p: p.update(sha256="sha256:" + "0" * 64)),
            ("intent", lambda p: p.update(path="unrelated-root")),
            ("original-metadata", lambda p: p["mapping"].update(native_metadata_applied=True)),
            ("original-metadata", lambda p: p["mapping"]["policy"].update(oem_code_page="850")),
            ("original-metadata", lambda p: p["record"].update(source_offset="1")),
            ("content-observation", lambda p: p["page"].update(file_bytes="99999")),
            ("content-observation", lambda p: p["page"].update(sequence="2")),
            ("content-observation", lambda p: p["page"]["selection"].update(capture_epoch="1")),
            ("metadata-result", lambda p: p["fields"]["creation"].update(status="applied_verified")),
            ("file-complete", lambda p: p.update(bytes="1")),
            ("file-complete", lambda p: p["identity"].update(file_id="0" * 32)),
            ("outcome", lambda p: p.update(files_complete="149")),
            ("outcome", lambda p: p.update(checkpointed_bytes="0")),
            ("outcome", lambda p: p.update(verified_bytes="0")),
            ("outcome", lambda p: p.update(directories_created="0")),
            ("outcome", lambda p: p.update(owner_accepted=True)),
            ("outcome", lambda p: p.update(source_writes=True)),
            ("outcome", lambda p: p.update(ledger_bytes_before_outcome="0")),
        ]
        expected_errors = (
            "checkpoint", "checkpoint", "checkpoint", "root", "metadata", "policy", "metadata",
            "content", "content", "content_binding", "metadata_result", "file_complete",
            "file_complete", "outcome", "outcome", "outcome", "outcome", "claim", "claim", "outcome")
        for (kind, mutate), expected_error in zip(mutations, expected_errors, strict=True):
            rows = copy.deepcopy(self.records)
            target = next(r for r in rows if r["kind"] == kind)
            mutate(target["payload"])
            inspect(rechained(rows), error="fat_tree_history_" + expected_error)
        for field, value in (("attempt_id", "another-attempt"),
                             ("definition_digest", "sha256:" + "0" * 64)):
            rows = copy.deepcopy(self.records)
            rows[3][field] = value
            inspect(rechained(rows), error="fat_tree_history_binding")

    def test_rehashed_definition_and_completion_requirements(self):
        rows = copy.deepcopy(self.records)
        rows[0]["payload"]["paths"]["source"] = "changed-declaration"
        inspect(rechained(rows), error="fat_tree_history_definition_digest")
        # A newly hashed definition must still obey declared safety/limits.
        for field, value in (("owner_accepted", True), ("effects", "overwrite")):
            rows = copy.deepcopy(self.records)
            rows[0]["payload"][field] = value
            d = sha(b"disked:fat-tree-extraction-plan:1\n" + canonical(rows[0]["payload"]))
            for row in rows:
                row["definition_digest"] = d
            inspect(rechained(rows), error="fat_tree_history_definition")
        rows = copy.deepcopy(self.records)
        index = next(i for i, r in enumerate(rows) if r["kind"] == "checkpoint")
        del rows[index]
        inspect(rechained(rows), error="")
        rows = copy.deepcopy(self.records)
        rows.insert(3, copy.deepcopy(rows[2]))
        inspect(rechained(rows), error="")
        rows = copy.deepcopy(self.records)
        rows.append(copy.deepcopy(rows[-1]))
        inspect(rechained(rows), error="fat_tree_history_after_outcome")

    def test_rehashed_identity_alias_and_empty_content(self):
        rows = copy.deepcopy(self.records)
        root_identity = next(r["payload"]["identity"] for r in rows if r["kind"] == "root-created")
        row = next(r for r in rows if r["kind"] == "metadata-result")
        row["payload"]["identity"] = root_identity
        inspect(rechained(rows), error="fat_tree_history_identity_alias")
        rows = copy.deepcopy(self.records)
        row = next(r for r in rows if r["kind"] == "content-observation")
        self.assertEqual("0", row["payload"]["page"]["returned_bytes"])
        row["payload"]["page"]["data_sha256"] = "sha256:" + "0" * 64
        inspect(rechained(rows), error="fat_tree_history_content")

    def test_finite_budgets_and_integer_bounds(self):
        inspect(self.raw, ("--bytes", str(len(self.raw) - 1)), error="fat_tree_history_budget")
        inspect(self.raw, ("--entries", "149"), error="fat_tree_history_budget")
        inspect(self.raw, ("--records", "1"), error="")
        inspect(b"x" * 262145, error="fat_tree_history_record_budget")
        rows = copy.deepcopy(self.records)
        rows[0]["sequence"] = "18446744073709551616"
        inspect(rechained(rows).replace(b'"sequence":"0"', b'"sequence":"18446744073709551616"', 1),
                error="fat_tree_history_integer")


def main():
    global PROBE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--writer", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--worker-fault", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    PROBE, writer.PROBE = args.probe.resolve(), args.writer.resolve()
    owned.PROBE, owned.FAULT = args.worker.resolve(), args.worker_fault.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HistoryTests))
    args.output.write_text(json.dumps({"passed": result.wasSuccessful(), "methods": result.testsRun,
                                      "cases": len(RESULTS), "records": RESULTS,
                                      "native_histories": writer.RESULTS,
                                      "owned_histories": owned.RESULTS}, indent=2) + "\n",
                           encoding="utf-8", newline="\n")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
