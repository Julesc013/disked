"""Independent immutable-effect identities and actual native capture separation."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_fat_tree_extraction import collection
from test_fat_tree_file import write

PROBE = None
WORKER = None
RESULTS = []
NATIVE = []


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def resource(observed, access, footprint, verification, failure="supplied-fixture-domain"):
    d = sha(canonical(observed))
    ids = ["observed:" + d]
    if "file" in observed:
        ids.append("file:" + sha(canonical({k: observed["file"][k] for k in ("volume_id", "file_id")})))
    return dict(identity=ids[0], epoch=d, observed=observed, access=access,
                footprint=footprint, verification=verification, aliases=ids, failure_domain=failure)


def rebind(value):
    out = resource(value["observed"], value["access"], value["footprint"],
                   value["verification"], value["failure_domain"])
    value.update(out)


def operation_store():
    generation = dict(created="100", file_id="f" * 32, volume_id="123")
    parent = dict(created="1", file_id="a" * 32, volume_id="123")
    # Deliberately unopened supplied data: validity is not native authentication.
    return resource(dict(file=generation, parents=[parent], path="unopened-operation-store"),
                    "create-operation-state",
                    dict(kind="finite-control-files", children=["recursive-request.json", "recursive-cancel",
                        "recursive-state.ndjson"], record_bytes="16384", total_bytes="1048576", records="64"),
                    "identity-epoch-and-ordered-state-history")


def projection(process, store):
    backend = copy.deepcopy(process)
    backend["schema"] = "org.disked.fat-tree-effects-prototype/1"
    del backend["owner_accepted"]
    del backend["selection"]["preparation_binding"]
    del backend["selection"]["preparation_context"]
    del backend["prepared_input"]["fixture"]
    return dict(schema="org.disked.fat-tree-extraction-review-prototype/1",
                backend=backend, operation_store=store)


def invoke(value, error=None):
    result = subprocess.run([str(PROBE)], input=canonical(value), capture_output=True, timeout=20)
    assert not result.stderr, result.stderr
    out = json.loads(result.stdout)
    if error is None:
        assert result.returncode == 0 and "error" not in out, (result.returncode, out)
        expected = value.get("review") or projection(value["process_definition"], value["operation_store"])
        assert out["definition"] == expected
        assert out["digest"] == sha(b"disked:fat-tree-extraction-review:1\n" + canonical(expected))
        assert not out["authorizes_effects"]
    else:
        assert result.returncode == 20 and out.get("error") == error, out
    RESULTS.append(dict(input_sha256=sha(canonical(value)), exit_code=result.returncode, result=out))
    return out


def prepare(source, destination, ledger, tree):
    request = dict(source=str(source), destination=str(destination), ledger=str(ledger),
                   offset=str(tree.offset), length=str(tree.length), mode="prepare_only")
    original = sha(source.read_bytes())
    r = subprocess.run([str(WORKER)], input=canonical(request), capture_output=True, timeout=30)
    assert r.returncode == 0 and not r.stderr, (r.returncode, r.stderr)
    rows = [json.loads(line) for line in r.stdout.splitlines()]
    assert rows[-1]["kind"] == "finished"
    state = rows[-1]["value"]
    assert state["worker"]["observation"] == "exited" and not state["dependencies_retained"]
    assert not state["grant_sent"] and rows[-1]["retained"] == "0"
    p = next(x for x in rows if x["kind"] == "prepared")
    assert p["definition"]["selection"]["preparation_context"]["process_id"] == state["worker"]["pid"]
    assert not destination.exists() and not ledger.exists() and sha(source.read_bytes()) == original
    NATIVE.append(dict(folder=str(source.parent), source_sha256=original,
                       prepared=p, final=rows[-1], stdout_sha256=sha(r.stdout)))
    return p


class ReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = Path(tempfile.mkdtemp(prefix="disked-recursive-review-"))
        cls.tree, _ = collection(16, count=150)
        source = cls.folder / "source.img"
        write(cls.tree, source)
        cls.a = prepare(source, cls.folder / "output", cls.folder / "ledger.ndjson", cls.tree)
        cls.b = prepare(source, cls.folder / "output", cls.folder / "ledger.ndjson", cls.tree)
        cls.store = operation_store()
        cls.process = cls.a["definition"]
        cls.review = projection(cls.process, cls.store)

    def test_real_process_receipts_change_without_changing_intended_effects(self):
        self.assertNotEqual(self.a["digest"], self.b["digest"])
        self.assertNotEqual(self.a["definition"]["selection"]["preparation_context"],
                            self.b["definition"]["selection"]["preparation_context"])
        a = invoke(dict(process_definition=self.process, operation_store=self.store,
                        fresh_process_definition=self.b["definition"], fresh_operation_store=self.store))
        self.assertTrue(a["matches"])
        b = invoke(dict(process_definition=self.b["definition"], operation_store=self.store))
        self.assertEqual(a["digest"], b["digest"])
        self.assertNotIn("preparation_context", a["definition"]["backend"]["selection"])
        self.assertNotIn("preparation_binding", a["definition"]["backend"]["selection"])

    def test_independent_hash_and_supplied_validation_grants_no_authority(self):
        a = invoke(dict(process_definition=self.process, operation_store=self.store))
        b = invoke(dict(review=self.review))
        self.assertEqual(a, b)
        grant = dict(review_digest=a["digest"], source_read=True, destination_write=True,
                     ledger_write=True, operation_write=True, host_effects=True)
        out = invoke(dict(review=self.review, grant=grant))
        self.assertTrue(out["grant_shape_valid"])
        self.assertFalse(out["authorizes_effects"])
        for key in ("source_read", "destination_write", "ledger_write", "operation_write", "host_effects"):
            bad = dict(grant, **{key: False})
            invoke(dict(review=self.review, grant=bad), error="fat_tree_review_grant")
        invoke(dict(review=self.review, grant=dict(grant, review_digest="sha256:" + "0" * 64)),
               error="fat_tree_review_grant")

    def test_process_capture_only_changes_leave_effect_identity_stable(self):
        process = copy.deepcopy(self.process)
        process["selection"]["preparation_context"].update(process_id="1", process_created="1", capture_sequence="99")
        process["selection"]["preparation_binding"]["capture_id"] = "sha256:" + "f" * 64
        out = invoke(dict(process_definition=process, operation_store=self.store,
                          fresh_process_definition=self.process, fresh_operation_store=self.store))
        self.assertTrue(out["matches"])
        process["selection"]["preparation_binding"]["capture_epoch"] = "99"
        invoke(dict(process_definition=process, operation_store=self.store),
               error="fat_tree_review_process_binding")

    def test_each_declared_effect_change_withdraws_the_match(self):
        def mutate_code(p):
            r = p["resources"]
            r["executable"]["observed"]["sha256"] = "sha256:" + "1" * 64
            r["provider"]["observed"]["code_sha256"] = "sha256:" + "1" * 64
            rebind(r["executable"]); rebind(r["provider"])
        def mutate_source(p):
            f = p["resources"]["source"]["observed"]["file"]
            f["written"] = str(int(f["written"]) + 1)
            p["prepared_input"]["expected_source"] = copy.deepcopy(f)
            rebind(p["resources"]["source"])
        def mutate_output(p, role, key, name):
            old = p["paths"][key]
            p["paths"][key] = old[:old.rfind("\\") + 1] + name
            p["resources"][role]["observed"]["location"]["leaf"] = name
            rebind(p["resources"][role])
        mutations = [
            lambda p: p["selection"].update(tree_digest="sha256:" + "1" * 64),
            lambda p: p["metadata_policy"].update(oem_code_page="850"),
            lambda p: p["metadata_policy"].update(name_selection="identity"),
            lambda p: p["metadata_policy"].update(time_interpretation="fixed_offset", utc_offset_minutes="-330"),
            lambda p: mutate_output(p, "destination_tree", "destination", "other-output"),
            lambda p: mutate_output(p, "metadata_ledger", "ledger", "other-ledger"),
            lambda p: p["budgets"].update(entries="65535"),
            mutate_code, mutate_source,
        ]
        for mutate in mutations:
            process = copy.deepcopy(self.process)
            mutate(process)
            out = invoke(dict(review=self.review, fresh_process_definition=process, fresh_operation_store=self.store))
            self.assertFalse(out["matches"])
        for key, value in (("path", "other-store"), ("file", dict(created="101", file_id="e" * 32, volume_id="123"))):
            store = copy.deepcopy(self.store)
            store["observed"][key] = value
            rebind(store)
            self.assertFalse(invoke(dict(review=self.review, fresh_process_definition=self.process,
                                         fresh_operation_store=store))["matches"])

    def test_rehashed_mutation_critical_shapes_and_claims_are_rejected(self):
        mutations = [
            (lambda v: v.update(status="admitted"), "fat_tree_review_shape"),
            (lambda v: v["backend"].update(owner_accepted=True), "fat_tree_review_shape"),
            (lambda v: v["backend"].update(effects="overwrite"), "fat_tree_review_effects"),
            (lambda v: v["backend"]["selection"].update(preparation_context={}), "fat_tree_review_shape"),
            (lambda v: v["backend"]["budgets"].update(entries="18446744073709551616"), "fat_tree_review_integer"),
            (lambda v: v["backend"]["budgets"].update(entries="0"), "fat_tree_review_range"),
            (lambda v: v["backend"]["metadata_policy"].update(oem_code_page="0"), "fat_tree_review_policy"),
            (lambda v: v["backend"]["metadata_policy"].update(utc_offset_minutes="841"), "fat_tree_review_policy"),
            (lambda v: v["backend"]["metadata_policy"].update(utc_offset_minutes="-0"), "fat_tree_review_policy"),
            (lambda v: v["backend"]["scratch_resources"].append("implicit scratch"), "fat_tree_review_undeclared_resources"),
            (lambda v: v["backend"]["resources"]["source"].update(access="write"), "fat_tree_review_resource"),
            (lambda v: v["backend"]["resources"]["source"]["aliases"].append("external-claim"), "fat_tree_review_alias"),
            (lambda v: v["backend"]["prepared_input"]["page"].update(output_bytes="65537"), "fat_tree_review_range"),
            (lambda v: v["backend"]["prepared_input"]["page"].update(events="513"), "fat_tree_review_range"),
            (lambda v: v["operation_store"]["footprint"]["children"].append("extra-state"), "fat_tree_review_store"),
            (lambda v: v["operation_store"]["footprint"].update(records="65"), "fat_tree_review_store"),
        ]
        for mutate, error in mutations:
            value = copy.deepcopy(self.review)
            mutate(value)
            invoke(dict(review=value), error=error)
        value = copy.deepcopy(self.review)
        value["operation_store"]["observed"]["file"] = copy.deepcopy(value["backend"]["resources"]["source"]["observed"]["file"])
        value["operation_store"]["observed"]["file"] = {k:value["operation_store"]["observed"]["file"][k] for k in ("created","file_id","volume_id")}
        rebind(value["operation_store"])
        invoke(dict(review=value), error="fat_tree_review_alias")

    def test_fixtures_and_broken_process_receipts_are_not_effect_definitions(self):
        process = copy.deepcopy(self.process)
        process["prepared_input"]["fixture"] = {"mode": "untrusted"}
        invoke(dict(process_definition=process, operation_store=self.store), error="fat_tree_review_fixture")
        for value in ("0", "18446744073709551616"):
            process = copy.deepcopy(self.process)
            process["selection"]["preparation_context"]["process_id"] = value
            invoke(dict(process_definition=process, operation_store=self.store),
                   error="fat_tree_review_range" if value == "0" else "fat_tree_review_integer")
        process = copy.deepcopy(self.process)
        process["owner_accepted"] = True
        invoke(dict(process_definition=process, operation_store=self.store), error="fat_tree_review_process_definition")


def main():
    global PROBE, WORKER
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    PROBE, WORKER = args.probe.resolve(), args.worker.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReviewTests))
    args.output.write_text(json.dumps(dict(passed=result.wasSuccessful(), methods=result.testsRun,
                           cases=len(RESULTS), records=RESULTS, native=NATIVE), indent=2) + "\n",
                           encoding="utf-8", newline="\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
