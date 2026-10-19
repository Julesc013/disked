"""Independent bytes, ledger, native metadata and actual-exit extraction oracles."""
import argparse
import ctypes
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from test_fat_traversal import Tree, short, slots
from test_fat_tree_file import write
from test_fat_tree_content import image
from test_fat_content_stream import fixture
from test_fat_walk import pack

PROBE = None
RESULTS = []


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


def date(year, month, day):
    return ((year - 1980) << 9) | (month << 5) | day


def stamp(raw):
    raw[13] = 123
    struct.pack_into("<HHH", raw, 14, (13 << 11) | (24 << 5) | 5,
                     date(2026, 10, 14), date(2025, 6, 3))
    struct.pack_into("<HH", raw, 22, (14 << 11) | (12 << 5) | 4, date(2000, 2, 29))
    return raw


def ticks(value, offset=0):
    delta = value.replace(tzinfo=timezone.utc) - timedelta(minutes=offset) - datetime(1601, 1, 1, tzinfo=timezone.utc)
    return (delta.days * 86400 + delta.seconds) * 10000000 + delta.microseconds * 10


class Basic(ctypes.Structure):
    _fields_ = [(name, ctypes.c_longlong) for name in ("creation", "access", "write", "change")] + [("attributes", ctypes.c_ulong)]


def native_metadata(path):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p,
                                  ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.GetFileInformationByHandleEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.CreateFileW(str(path), 0x80, 7, None, 3, 0x02200000, None)
    assert handle != ctypes.c_void_p(-1).value, ctypes.get_last_error()
    try:
        value = Basic()
        assert kernel.GetFileInformationByHandleEx(handle, 0, ctypes.byref(value), ctypes.sizeof(value)), ctypes.get_last_error()
        return {name: getattr(value, name) for name, _ in value._fields_}
    finally:
        kernel.CloseHandle(handle)


def ledger_records(path, definition, digest, complete=False):
    if not path.exists():
        return []
    records = []
    previous = "sha256:" + "0" * 64
    for number, line in enumerate(path.read_bytes().splitlines(keepends=True)):
        assert line.endswith(b"\n"), "incomplete record is not admitted"
        value = json.loads(line)
        assert line == encoded(value) + b"\n"
        assert value["sequence"] == str(number) and value["previous"] == previous
        assert value["definition_digest"] == digest
        assert value["schema"] == "org.disked.fat-tree-extraction-record-prototype/1"
        previous = sha(line)
        records.append(value)
    if records:
        assert records[0]["kind"] == "definition" and records[0]["payload"] == definition
    if complete:
        assert records[-1]["kind"] == "outcome" and records[-1]["payload"]["status"] == "complete"
        assert records[-1]["payload"]["ledger_records_before_outcome"] == str(len(records) - 1)
        assert records[-1]["payload"]["last_digest_before_outcome"] == records[-1]["previous"]
    return records


def run(tree=None, request=None, extra=None, existing=None, timeout=180):
    if timeout not in (180,360):raise ValueError('Undeclared native fixture timeout')
    if os.environ.get('DISKED_TEST_TRACE_FAT_HISTORY')=='1':
        print('WRITER_INPUT',sorted((extra or {}).keys()),'existing',existing,flush=True)
    folder = Path(tempfile.mkdtemp(prefix="disked-recursive-extraction-"))
    source, destination, ledger = folder/"source.img", folder/"output", folder/"metadata.ndjson"
    if tree is not None:
        write(tree, source)
        request = tree.request()
    else:
        image(request, source)
    original = source.read_bytes()
    if existing == "destination":
        destination.mkdir()
        (destination/"marker.txt").write_bytes(b"retained existing resource")
    if existing == "ledger":
        ledger.write_bytes(b"retained existing resource")
    value = {"source": str(source), "offset": request["offset"], "length": request["length"],
             "copy": request["copy"], "destination": str(destination), "ledger": str(ledger), **(extra or {})}
    if value.get("alias") == "source":
        value["ledger"] = str(source)
    if value.get("alias") == "destination":
        value["ledger"] = str(destination).upper()
    if os.environ.get('DISKED_TEST_TRACE_FAT_HISTORY')=='1':
        import time
        started=time.monotonic()
        print('WRITER_PROCESS_START',flush=True)
    completed = subprocess.run([str(PROBE)], input=encoded(value), capture_output=True, timeout=timeout)
    if os.environ.get('DISKED_TEST_TRACE_FAT_HISTORY')=='1':
        print('WRITER_PROCESS_SECONDS',round(time.monotonic()-started,6),flush=True)
    assert completed.returncode in (0, 93) and not completed.stderr, (completed.returncode, completed.stderr.decode())
    rows = [json.loads(line) for line in completed.stdout.splitlines()]
    assert rows
    prepared = next((row for row in rows if row["kind"] == "prepared"), None)
    records = []
    if prepared:
        definition, digest = prepared["definition"], prepared["digest"]
        assert sha(b"disked:fat-tree-extraction-plan:1\n" + encoded(definition)) == digest
        assert set(definition["resources"]) == {"source", "destination_tree", "metadata_ledger", "executable", "provider", "host"}
        for resource in definition["resources"].values():
            assert resource["identity"] in resource["aliases"] and resource["epoch"].startswith("sha256:")
            assert resource["access"] and resource["footprint"]["kind"] and resource["verification"]
        assert definition["scratch_resources"] == definition["recovery_resources"] == []
        if not existing and value.get("alias") != "source":
            records = ledger_records(ledger, definition, digest,
                                     rows[-1]["kind"] == "outcome" and rows[-1]["value"]["status"] == "complete")
        if rows[-1]["kind"] == "outcome":
            outcome = rows[-1]["value"]
            assert int(outcome["ledger_records"]) == len(records)
            assert outcome["ledger_bytes"] == str(ledger.stat().st_size)
            assert outcome["last_record_digest"] == sha(encoded(records[-1]) + b"\n")
            assert int(outcome["verified_bytes"]) >= int(outcome["checkpointed_bytes"])
            assert not outcome["source_writes"] and not outcome["atomic_snapshot"]
            assert not outcome["contained_worker_qualified"] and not outcome["owner_accepted"]
    assert source.read_bytes() == original
    RESULTS.append({"extra": extra, "existing": existing, "exit_code": completed.returncode, "timeout_seconds": timeout,
                    "last": rows[-1], "records": len(records), "source_sha256": sha(original),
                    "stdout_sha256": sha(completed.stdout), "folder": str(folder)})
    return folder, rows, records, original


def collection(bits=12, count=300):
    tree = Tree(bits, offset=4096)
    records, expected = [], {}
    for number in range(count):
        size = 0 if number % 9 == 0 else (number * 31) % 511 + 1
        cluster = 100 + number * 2 if size else 0
        raw = stamp(short(name=f"{number:08d}".encode() + b"BIN", cluster=cluster, size=size,
                          attributes=(0, 1, 2, 4, 32, 39)[number % 6]))
        records.append(raw)
        data = bytes((number * 43 + at * 11) & 255 for at in range(size))
        expected[f"{number:08d}.BIN"] = (data, raw[11])
        if cluster:
            tree.chain([cluster])
            tree.regions[tree.cluster(cluster)] = data + b"\xab" * (512 - len(data))
    if bits == 32:
        root = [2] + list(range(3000, 3000 + (count * 32) // 512))
        tree.chain(root)
        tree.directory(records, clusters=root)
    else:
        tree.directory(records)
    return tree, expected


class ExtractionTests(unittest.TestCase):
    def test_complete_variants_bytes_metadata_and_fresh_capture(self):
        for bits in (12, 16, 32):
            tree, expected = collection(bits)
            folder, rows, records, original = run(tree, extra={"time_interpretation": "fixed_offset", "utc_offset_minutes": "330"}, timeout=360)
            self.assertEqual("complete", rows[-1]["value"]["status"], rows[-1])
            self.assertEqual("300", rows[-1]["value"]["files_complete"])
            self.assertEqual(300, len(list((folder/"output").iterdir())))
            for name, (data, attributes) in expected.items():
                path = folder/"output"/name
                native = native_metadata(path)
                self.assertEqual(ticks(datetime(2026, 10, 14, 13, 24, 11, 230000), 330), native["creation"])
                self.assertEqual(ticks(datetime(2025, 6, 3), 330), native["access"])
                self.assertEqual(ticks(datetime(2000, 2, 29, 14, 12, 8), 330), native["write"])
                self.assertEqual(attributes & 39, native["attributes"] & 39)
                self.assertEqual(data, path.read_bytes())
            mappings = [r["payload"] for r in records if r["kind"] == "original-metadata"]
            self.assertEqual(300, len(mappings))
            preparation = rows[0]["definition"]["selection"]["preparation_binding"]["capture_id"]
            self.assertTrue(all(frame["binding"]["capture_id"] != preparation for frame in mappings))
            for frame in mappings:
                at = int(frame["record"]["source_offset"])
                self.assertEqual(original[at:at+32].hex(), frame["mapping"]["original"]["raw_record"])
            for record in records:
                if record["kind"] == "metadata-result":
                    self.assertTrue(all(field["status"] == "applied_verified" for field in record["payload"]["fields"].values()))

    def test_large_noncontiguous_file_and_no_slack(self):
        nodes = [number + shift for number in range(3, 33003, 3) for shift in (2, 0, 1)]
        request, expected, _, _ = fixture(16, 40000, nodes=nodes)
        folder, rows, records, _ = run(request=request)
        self.assertEqual("complete", rows[-1]["value"]["status"], rows[-1])
        self.assertEqual(expected, (folder/"output/CONTENT.BIN").read_bytes())
        self.assertGreater(sum(r["kind"] == "checkpoint" for r in records), 128)
        self.assertEqual(len(expected), int(rows[-1]["value"]["checkpointed_bytes"]))

    def test_deep_directories_and_deferred_metadata(self):
        tree = Tree(16)
        tree.directory([stamp(short(name=b"ROOT       ", attributes=16, cluster=10))])
        parent, relative = "entry:" + str(tree.root), Path("ROOT")
        for cluster in range(10, 22):
            tree.chain([cluster])
            name = f"D{cluster:02d}"
            tree.directory([stamp(short(name=name.encode().ljust(11, b" "), attributes=16, cluster=cluster+1))],
                           parent=parent, clusters=[cluster])
            parent = "entry:" + str(tree.cluster(cluster))
            relative /= name
        tree.chain([22])
        tree.directory([short(name=b"LEAF    TXT")], parent=parent, clusters=[22])
        folder, rows, records, _ = run(tree, extra={"time_interpretation": "fixed_offset"})
        self.assertEqual("complete", rows[-1]["value"]["status"], rows[-1])
        self.assertEqual(b"", (folder/"output"/relative/"LEAF.TXT").read_bytes())
        self.assertEqual(ticks(datetime(2026, 10, 14, 13, 24, 11, 230000)), native_metadata(folder/"output/ROOT")["creation"])
        directory_results = [r for r in records if r["kind"] == "metadata-result" and r["payload"]["key"] !=
                             next(x["payload"]["key"] for x in records if x["kind"] == "file-complete")]
        self.assertEqual(13, len(directory_results))

    def test_prepare_missing_grants_aliases_and_existing_are_effect_free(self):
        tree, _ = collection(count=1)
        for extra in ({"mode": "prepare"}, {"wrong_digest": "yes"},
                      *({"missing_grant": role} for role in ("source", "destination", "ledger", "host")),
                      {"alias": "source"}, {"alias": "destination"}, {"race": "destination"}):
            folder, rows, _, _ = run(tree, extra=extra)
            self.assertFalse((folder/"metadata.ndjson").exists())
            if extra.get("race") != "destination":
                self.assertFalse((folder/"output").exists())
            if extra.get("mode") != "prepare":
                self.assertEqual("error", rows[-1]["kind"])
        for existing in ("destination", "ledger"):
            folder, rows, _, _ = run(tree, existing=existing)
            self.assertEqual("error", rows[-1]["kind"])
            marker = folder/"metadata.ndjson" if existing == "ledger" else folder/"output/marker.txt"
            self.assertEqual(b"retained existing resource", marker.read_bytes())

    def test_name_collision_invalid_mapping_and_identity_policy(self):
        tree = Tree(12)
        tree.directory([short(name=b"SAME    TXT"), short(name=b"same    TXT")])
        folder, rows, _, _ = run(tree)
        self.assertEqual("fat_tree_extract_name_collision", rows[-1]["code"])
        self.assertFalse((folder/"metadata.ndjson").exists())
        raw = short(name=b"LONGNAMETXT")
        long, _ = slots([0xd800, ord("x")], raw)
        tree.directory([long[i:i+32] for i in range(0, len(long), 32)] + [raw])
        folder, rows, _, _ = run(tree)
        self.assertEqual("fat_tree_extract_metadata_refused", rows[-1]["code"])
        self.assertFalse((folder/"output").exists())
        folder, rows, records, _ = run(tree, extra={"unrepresentable_name": "identity"})
        self.assertEqual("complete", rows[-1]["value"]["status"])
        mapping = next(r["payload"]["mapping"] for r in records if r["kind"] == "original-metadata")
        self.assertEqual(long.hex(), mapping["original"]["raw_long_slots"])
        self.assertFalse(mapping["name"]["matches_selected_original_name"])
        self.assertEqual([mapping["name"]["utf8"]], [p.name for p in (folder/"output").iterdir()])

    def test_unicode_names_preserve_distinct_original_forms(self):
        tree = Tree(12)
        records = []
        for number, name in enumerate(("é.txt", "e\u0301.txt", "😀.txt")):
            raw = short(name=f"NAME{number:04d}".encode() + b"TXT")
            units = list(struct.unpack("<" + "H" * (len(name.encode("utf-16-le")) // 2), name.encode("utf-16-le")))
            long, _ = slots(units, raw)
            records.extend([long[i:i+32] for i in range(0, len(long), 32)] + [raw])
        tree.directory(records)
        folder, rows, _, _ = run(tree)
        self.assertEqual("complete", rows[-1]["value"]["status"])
        self.assertEqual({"é.txt", "e\u0301.txt", "😀.txt"}, {p.name for p in (folder/"output").iterdir()})

    def test_partial_cancel_fault_and_child_collision_preserve_resources(self):
        tree, _ = collection(count=2)
        for field in ("cancel_boundary", "throw_boundary"):
            for boundary in ("root_created", "file_created", "chunk_written", "chunk_verified", "metadata_applied"):
                folder, rows, records, _ = run(tree, extra={field: boundary})
                self.assertTrue(rows[-1]["value"]["status"].startswith("partial"), rows[-1])
                self.assertTrue((folder/"output").exists() and records)
                self.assertEqual("outcome", records[-1]["kind"])
        folder, rows, _, _ = run(tree, extra={"race": "child"})
        self.assertEqual("partial", rows[-1]["value"]["status"])
        self.assertEqual(b"external-fixture-marker", (folder/"output/00000000.BIN").read_bytes())

    def test_actual_process_exits_keep_intentions_and_partial_effects(self):
        tree, _ = collection(count=2)
        for boundary in ("ledger_created", "root_created", "file_created", "chunk_written", "chunk_verified", "metadata_applied"):
            folder, rows, records, _ = run(tree, extra={"exit_boundary": boundary})
            self.assertEqual("prepared", rows[-1]["kind"])
            self.assertTrue((folder/"metadata.ndjson").exists())
            self.assertTrue(not records or records[-1]["kind"] != "outcome")

    def test_durable_completion_survives_notification_failure_or_actual_exit(self):
        tree, _ = collection(count=1)
        folder, rows, records, _ = run(tree, extra={"throw_boundary": "complete_flushed"})
        self.assertEqual("complete", rows[-1]["value"]["status"])
        self.assertEqual("fixture-effect-fault", rows[-1]["value"]["notification_diagnostic"])
        self.assertEqual(1, sum(record["kind"] == "outcome" for record in records))
        folder, rows, records, _ = run(tree, extra={"exit_boundary": "complete_flushed"})
        self.assertEqual("prepared", rows[-1]["kind"])
        self.assertEqual("complete", records[-1]["payload"]["status"])
        self.assertTrue((folder/"output/00000000.BIN").exists())

    def test_entry_directory_content_and_metadata_budgets_refuse_before_outputs(self):
        tree, _ = collection(count=20)
        for extra in ({"entries": "1"}, {"content_bytes": "1"}, {"metadata_bytes": "16384"}, {"pages": "0"}):
            folder, rows, _, _ = run(tree, extra=extra)
            self.assertEqual("error", rows[-1]["kind"])
            self.assertFalse((folder/"output").exists() or (folder/"metadata.ndjson").exists())
        tree = Tree(12)
        tree.directory([short(name=b"DIR        ", attributes=16, cluster=10)])
        tree.chain([10])
        tree.directory([], parent="entry:" + str(tree.root), clusters=[10])
        folder, rows, _, _ = run(tree, extra={"directories": "1"})
        self.assertEqual("fat_tree_extract_directory_budget", rows[-1]["code"])
        self.assertFalse((folder/"output").exists() or (folder/"metadata.ndjson").exists())

    def test_selected_copy_and_invalid_time_remain_explicit(self):
        tree, expected = collection(16, count=2)
        tree.fat_copy = 1
        broken = dict(tree.mapping)
        broken[102] = 0
        # image() writes explicit regions after patterns; replace copy zero only.
        request = tree.request()
        for region in request["regions"]:
            if int(region["offset"]) == tree.offset + tree.g["reserved"] * tree.unit:
                region["hex"] = pack(16, broken).hex()
        request["patterns"] = []
        folder, rows, _, _ = run(request=request)
        self.assertEqual("complete", rows[-1]["value"]["status"])
        self.assertEqual(expected["00000001.BIN"][0], (folder/"output/00000001.BIN").read_bytes())
        tree = Tree(12)
        raw = stamp(short())
        struct.pack_into("<H", raw, 16, date(2100, 2, 29))
        tree.directory([raw])
        folder, rows, records, _ = run(tree, extra={"time_interpretation": "fixed_offset"})
        self.assertEqual("complete", rows[-1]["value"]["status"])
        result = next(r["payload"]["fields"] for r in records if r["kind"] == "metadata-result")
        self.assertEqual("unapplied", result["creation"]["status"])
        self.assertEqual("invalid", result["creation"]["candidate"]["reason"])
        self.assertEqual("applied_verified", result["write"]["status"])


def main():
    global PROBE
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    PROBE = args.probe.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ExtractionTests))
    args.output.write_text(json.dumps({"passed": result.wasSuccessful(), "methods": result.testsRun,
                                      "cases": len(RESULTS), "records": RESULTS}, indent=2) + "\n",
                           encoding="utf-8", newline="\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
