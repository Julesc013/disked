"""Metadata mapping of owned latest-page records, using actual ordinary files."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_fat_traversal import Tree, files, short, slots
from test_fat_tree_file import write

PROBE = None
FAULT = None
RESULTS = []


def run(tree, extra=None, fault=False):
    folder = Path(tempfile.mkdtemp(prefix="disked-tree-metadata-"))
    path = folder / "source.img"
    write(tree, path)
    source = path.read_bytes()
    before = hashlib.sha256(source).hexdigest()
    request = {"path": str(path), "offset": str(tree.offset), "length": str(tree.length),
               "copy": str(tree.fat_copy), "metadata_only": True, **(extra or {})}
    completed = subprocess.run([str(FAULT if fault else PROBE)], input=json.dumps(request).encode(),
                               capture_output=True, timeout=120)
    assert completed.returncode == 0 and not completed.stderr, completed.stderr.decode()
    rows = [json.loads(line) for line in completed.stdout.splitlines()]
    assert rows[-1]["kind"] == "summary"
    trees = [row["frame"] for row in rows if row["kind"] == "tree"]
    records = {event["key"]: event for frame in trees for event in frame["page"]["events"]
               if event["type"] == "record"}
    context = trees[0]["context"]
    binding = trees[0]["page"]["binding"]
    metadata = [row["frame"] for row in rows if row["kind"] == "metadata"]
    for frame in metadata:
        assert frame["schema"] == "org.disked.fat-tree-metadata-frame/1"
        assert frame["directory_membership"] == "held-source-traversal"
        assert frame["context"] == context and frame["binding"] == binding
        assert frame["source_before"] == frame["source_after"] == trees[0]["source_before"]
        entry = frame["record"]
        assert entry == records[entry["key"]]
        at = int(entry["source_offset"])
        parent, raw = tree.expected[at]
        assert entry["directory"] == parent
        assert bytes.fromhex(entry["raw"]) == raw == source[at:at + 32]
        mapped = frame["mapping"]
        assert mapped["original"]["raw_record"] == entry["raw"]
        assert mapped["original"]["source_offset"] == entry["source_offset"]
        assert not mapped["authorizes_effects"] and not frame["authorizes_effects"]
        assert len(frame["regions"]) == 1 + len(entry.get("long_name", {}).get("source_offsets", []))
        for region in frame["regions"]:
            at = int(region["offset"])
            assert region["requested"] == "32" and region["matches"]
            assert region["read_error"] == region["reread_error"] == "0"
            assert region["bytes"] == region["reread_bytes"] == source[at:at + 32].hex()
        if "long_name" in entry:
            assert mapped["original"]["raw_long_slots"] == entry["long_name"]["raw_slots"]
            assert mapped["original"]["long_units"] == entry["long_name"]["units"]
        for check in frame["checks"]:
            assert check["applicable"] and check["read_consistent"] and not check["cancelled"]
            assert check["code"] is None and check["metadata"] == frame["source_before"]
        if mapped["status"] == "candidate":
            assert not mapped["native_metadata_applied"] and not mapped["native_collision_checked"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert list(folder.iterdir()) == [path], "preparation created output"
    RESULTS.append({"bits": tree.bits, "extra": extra, "fault": fault, "metadata": len(metadata),
                    "source_sha256": before, "input_sha256": hashlib.sha256(json.dumps(request).encode()).hexdigest(),
                    "output_sha256": hashlib.sha256(completed.stdout).hexdigest(), "exit_code": completed.returncode})
    return metadata, rows


class TreeMetadataTests(unittest.TestCase):
    def test_more_than_old_capture_limit_and_latest_page_membership(self):
        for bits in (12, 16, 32):
            tree = Tree(bits, offset=4096)
            if bits == 32:
                chain = [2] + list(range(10, 29))
                tree.chain(chain)
                tree.directory(files(300), clusters=chain)
            else:
                tree.directory(files(300))
            metadata, rows = run(tree)
            self.assertEqual(300, len(metadata))
            self.assertEqual("complete", [r for r in rows if r["kind"] == "tree"][-1]["frame"]["page"]["status"])
            for number, frame in enumerate(metadata):
                self.assertEqual(f"{number:08d}.BIN", frame["mapping"]["name"]["utf8"])

    def test_deep_directory_parent_identities(self):
        tree = Tree(16)
        tree.directory([short(name=b"ROOT       ", attributes=16, cluster=10)])
        parent = "entry:" + str(tree.root)
        for cluster in range(10, 24):
            tree.chain([cluster])
            raw = short(name=f"DIR{cluster:05d}".encode() + b"   ", attributes=16, cluster=cluster + 1)
            tree.directory([short(name=b".          ", attributes=16, cluster=cluster), raw],
                           parent=parent, clusters=[cluster])
            parent = "entry:" + str(tree.cluster(cluster) + 32)
        tree.chain([24])
        tree.directory([short(name=b"LEAF    TXT")], parent=parent, clusters=[24])
        metadata, _ = run(tree, {"small_pages": True})
        self.assertEqual(16, len(metadata))
        self.assertEqual("LEAF.TXT", metadata[-1]["mapping"]["name"]["utf8"])

    def test_long_slots_across_pages_and_sector_boundary(self):
        for units in ([ord(c) for c in "e\u0301-long-name.txt"], [0xd800, ord("x")]):
            tree = Tree(12)
            raw = short(name=b"LONGNAMETXT")
            long, _ = slots(units, raw)
            tree.directory(files(15) + [long[i:i + 32] for i in range(0, len(long), 32)] + [raw])
            metadata, _ = run(tree, {"small_pages": True})
            value = metadata[-1]["mapping"]
            if units[0] == 0xd800:
                self.assertEqual("refused", value["status"])
            else:
                self.assertEqual("e\u0301-long-name.txt", value["name"]["utf8"])
            self.assertEqual(long.hex(), value["original"]["raw_long_slots"])
            metadata, _ = run(tree, {"small_pages": True, "identity_names": True})
            for frame in metadata:
                self.assertEqual("entry_" + frame["record"]["source_offset"],
                                 frame["mapping"]["name"]["utf8"])
                self.assertFalse(frame["mapping"]["name"]["matches_selected_original_name"])

    def test_cancellation_has_no_mapping_or_output_effects(self):
        tree = Tree(12)
        tree.directory(files(3))
        metadata, rows = run(tree, {"cancel_metadata": True})
        self.assertFalse(metadata)
        refusals = [row for row in rows if row["kind"] == "metadata_refused"]
        self.assertEqual(3, len(refusals))
        self.assertTrue(all(row["code"] == "fat_tree_metadata_cancelled" for row in refusals))

    def test_source_faults_cannot_admit_mapping(self):
        tree = Tree(12)
        tree.directory(files(3))
        for fault in ("verify_changed", "metadata_changed", "short_read"):
            metadata, _ = run(tree, {"fixture": {"file_fault": fault}}, True)
            self.assertFalse(metadata)


def main():
    global PROBE, FAULT
    parser = argparse.ArgumentParser()
    for name in ("probe", "fault", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    PROBE, FAULT = args.probe.resolve(), args.fault.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TreeMetadataTests))
    args.output.write_text(json.dumps({"passed": result.wasSuccessful(), "methods": result.testsRun,
                                      "cases": len(RESULTS), "records": RESULTS}, indent=2) + "\n",
                           encoding="utf-8", newline="\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
