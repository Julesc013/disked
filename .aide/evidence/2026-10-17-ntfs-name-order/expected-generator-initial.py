"""Independent joint-source layouts, traversal orders and candidate groups."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from ntfs_directory_fixture import DirectoryVolume, I30, filename, index_entry, index_root
from test_ntfs_stream import record, ref, resident
from test_ntfs_upcase_capture import MAXIMUM, TABLE, UpcaseVolume


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


IDENTITY = struct.pack("<65536H", *range(65536))
ASCII = struct.pack("<65536H", *[n - 32 if 97 <= n <= 122 else n for n in range(65536)])


class JointVolume:
    def __init__(self, kind="siblings", table=ASCII, rows=None, table_options=None, **options):
        self.directory = d = DirectoryVolume(kind=kind, **options)
        if rows is not None:
            assert kind == "leaf" and d.list_form == "none"
            d.root_rows = [index_entry(key=filename(name, namespace=ns, parent=d.reference), target=r)
                           for name, ns, r in rows] + [index_entry(end=True)]
            d.root_value, d.root_expected = index_root(d.root_rows, cluster=d.cluster, index=d.index)
            d.root_attribute = resident(d.root_value, name=I30, kind=0x90, instance=11)
            d.base_attributes = [d.root_attribute]
            d.place_record(d.number, record(d.base_attributes, number=d.number, sequence=d.sequence,
                                           flags=3, size=d.size, usa=d.usa))
            d.expected_rows = [(None, row) for row in d.root_rows]
        count = 131072 // d.cluster
        assert count * d.cluster == 131072
        kwargs = dict(table_runs=[(1, 2000), (count - 1, 2100)],
                      mft_first=d.mft_runs[0][0], mft_closure=d.mft_closure)
        kwargs.update(table_options or {})
        self.table = u = UpcaseVolume(cluster=d.cluster, size=d.size, offset=d.offset,
                                     minor=options.get("minor", 1), usa=d.usa, table=table, **kwargs)
        assert d.mft_runs == u.mft_runs
        self.input = copy.deepcopy(d.input)
        self.input.update(name_order=True, limits=copy.deepcopy(MAXIMUM))
        self.input["directory"]["reference"] = str(d.reference)
        self.initial_reads = d.initial_reads + u.initial_reads[len(u.bootstrap_reads):]
        # Add only FILE10/list/table bytes. Keep the directory's boot/index profile.
        for at, size in u.initial_reads[len(u.bootstrap_reads):]:
            self.input["regions"].append(dict(offset=str(at), hex=u.bytes(at, size).hex()))

    def regions(self):
        from test_ntfs_capture import bytes_at
        return [dict(offset=str(at), bytes=str(n), sha256=sha(bytes_at(self.input, at, n)))
                for at, n in self.initial_reads]

    def expected(self):
        nodes = {}
        for header, (node, (_, row)) in enumerate(self.directory.expected_rows, 1):
            nodes.setdefault(node, []).append((header, row))
        ordered = []

        def visit(node):
            for header, row in nodes[node]:
                if row["has_child"]:
                    visit(int(row["child_vbn"]))
                if not row["end_marker"]:
                    name = row["filename"]
                    units = struct.unpack("<" + "H" * name["name_length"], bytes.fromhex(name["name_hex"]))
                    ordered.append(dict(header=header, node=node, reference=int(row["segment_reference"]),
                                        namespace=name["namespace"], units=units))
        visit(None)
        mapping = struct.unpack("<65536H", self.table.table)
        fold = lambda key: tuple(mapping[n] for n in key["units"])
        sign = lambda a, b: (a > b) - (a < b)
        adjacent = [dict(left_header=str(a["header"]), right_header=str(b["header"]),
                         raw_order=str(sign(a["units"], b["units"])),
                         upcase_order=str(sign(fold(a), fold(b)))) for a, b in zip(ordered, ordered[1:])]
        references, mapped = {}, {}
        for key in ordered:
            references.setdefault(key["reference"], []).append(key)
            mapped.setdefault(fold(key), []).append(key)
        headers = lambda keys: [str(k["header"]) for k in keys]
        return dict(
            order=[dict(position=str(i), header_number=str(k["header"]),
                        index_vbn=None if k["node"] is None else str(k["node"])) for i, k in enumerate(ordered)],
            adjacent=adjacent,
            reference_groups=[dict(reference=str(r), headers=headers(keys),
                                   namespace_codes=[str(n) for n in sorted({k["namespace"] for k in keys})])
                              for r, keys in sorted(references.items()) if len(keys) > 1],
            mapped_groups=[dict(headers=headers(keys), distinct_references=str(len({k["reference"] for k in keys})),
                                raw_equal=len({k["units"] for k in keys}) == 1)
                           for _, keys in sorted(mapped.items()) if len(keys) > 1],
            key_count=str(len(ordered)), mapped_nondecreasing=all(int(r["upcase_order"]) <= 0 for r in adjacent))


def cases():
    def case(label, volume, diagnostic=None, *, request=None, refusal=""):
        expected = volume.expected()
        diagnostic = ("" if expected["mapped_nondecreasing"] else "ntfs_name_order_mapped_descent") if diagnostic is None else diagnostic
        return label, volume, copy.deepcopy(volume.input if request is None else request), diagnostic, refusal

    for minor in (0, 1):
        for kind in ("empty", "leaf", "siblings", "deep", "single"):
            yield case(f"profile-{minor}-{kind}", JointVolume(kind=kind, minor=minor))
    for label, options in [
        ("small-cluster", dict(cluster=512)),
        ("large-cluster", dict(cluster=8192)),
        ("large-record", dict(size=4096)),
        ("old-record", dict(usa=42)),
        ("high-window", dict(offset=(1 << 32) + 512)),
        ("small-index", dict(index=512)),
        ("fragmented-directory", dict(fragmented_allocation=True)),
        ("nonresident-bitmap", dict(bitmap_form="nonresident")),
        ("directory-list", dict(list_form="nonresident", reverse_list=True)),
        ("mft-volume-closure", dict(mft_closure=True)),
        ("named-directory", dict(number=7, sequence=9)),
    ]:
        yield case(label, JointVolume(**options))
    for label, options in [
        ("table-resident-list", dict(list_form="resident", split=True, reverse=True)),
        ("table-nonresident-list", dict(list_form="nonresident", split=True)),
        ("table-extension-only", dict(list_form="nonresident", extension_only=True)),
    ]:
        yield case(label, JointVolume(table_options=options))
    for label, table in [("identity", IDENTITY), ("non-idempotent", TABLE)]:
        yield case(label, JointVolume(table=table))
    r, other = ref(14, 9), ref(15, 9)
    samples = [
        ("ascending", [(b"A\0", 1, r), (b"B\0", 1, other)]),
        ("descending", [(b"Z\0", 1, r), (b"A\0", 1, other)]),
        ("folded-raw-forward", [(b"A\0", 1, r), (b"a\0", 1, other)]),
        ("folded-raw-reverse", [(b"a\0", 1, r), (b"A\0", 1, other)]),
        ("same-raw-reference", [(b"A\0", 1, r), (b"A\0", 1, r)]),
        ("same-raw-targets", [(b"A\0", 1, r), (b"A\0", 1, other)]),
        ("same-number-new-sequence", [(b"A\0", 1, r), (b"a\0", 1, ref(14, 10))]),
        ("namespace-candidates", [(b"A\0", n, r) for n in (3, 2, 1, 0)]),
        ("sequence-reference-extremes", [(b"A\0", 0, ref((1 << 48) - 1, 65535)), (b"a\0", 2, ref(0, 1))]),
        ("surrogate-units", [(struct.pack("<4H", 0, 27, 0xd800, 0xffff), 0, r),
                             (struct.pack("<4H", 0, 27, 0xdfff, 0xffff), 0, other)]),
        ("max-name", [(b"A\0" * 254 + b"B\0", 0, r), (b"a\0" * 254 + b"b\0", 0, other)]),
    ]
    for label, rows in samples:
        yield case(label, JointVolume(kind="leaf", rows=rows, size=4096))
    strange = list(struct.unpack("<65536H", IDENTITY))
    strange[ord("A")], strange[ord("Z")] = ord("Z"), ord("A")
    yield case("supplied-ascii-reversal", JointVolume(kind="leaf", table=struct.pack("<65536H", *strange),
                                                    rows=samples[0][1]))
    rows = [(struct.pack("<2H", n, 0xffff), n % 4, ref(n + 14, 1 + n % 17)) for n in range(320)]
    yield case("large-order", JointVolume(kind="leaf", rows=rows, size=65536, table=IDENTITY))
    baseline = JointVolume()
    n = len(baseline.initial_reads)
    for mode, diagnostic in [("null", "ntfs_read_length"), ("short", "ntfs_read_length"),
                             ("oversize", "ntfs_read_length"), ("throw", "ntfs_reader_failure")]:
        for call in range(1, 2 * n + 1):
            request = copy.deepcopy(baseline.input)
            request["fault"] = dict(mode=mode, call=str(call))
            yield case(f"{mode}-{call}", baseline, diagnostic, request=request)
    for call in range(n + 1, 2 * n + 1):
        request = copy.deepcopy(baseline.input)
        request["fault"] = dict(mode="change", call=str(call))
        yield case(f"reread-change-{call}", baseline, "ntfs_source_changed", request=request)
    request = copy.deepcopy(baseline.input)
    request["fault"] = dict(mode="mutate-controls", call="1")
    yield case("controls-and-reader-owned", baseline, request=request)
    total = sum(size for _, size in baseline.initial_reads)
    for key, exact, diagnostic in [("read_requests", n * 2, "ntfs_read_budget"),
                                    ("read_bytes", total * 2, "ntfs_read_budget"),
                                    ("retained_bytes", total, "ntfs_retained_budget")]:
        for delta in (0, -1):
            request = copy.deepcopy(baseline.input)
            request["limits"][key] = str(exact + delta)
            yield case(f"quota-{key}-{delta}", baseline, "" if delta == 0 else diagnostic, request=request)
    request = copy.deepcopy(baseline.input)
    request["limits"]["output_bytes"] = "200000"
    yield case("output-before-table", baseline, "ntfs_output_budget", request=request)
    for key, value, refusal in [("epoch", "0", "ntfs_capture_inputs"),
                                 ("major", "99", "ntfs_capture_inputs"),
                                 ("minor", "2", "ntfs_capture_inputs"),
                                 ("source_id", "", "ntfs_capture_inputs"),
                                 ("source_bytes", "1", "ntfs_capture_window")]:
        request = copy.deepcopy(baseline.input)
        request[key] = value
        yield case("invalid-" + key, baseline, request=request, refusal=refusal)
    request = copy.deepcopy(baseline.input)
    request["directory"]["reference"] = "5"
    yield case("invalid-full-reference", baseline, request=request, refusal="ntfs_directory_reference")
    for key, value in [("entries", "0"), ("entries", "4097"), ("blocks", "0"), ("bitmap_bytes", "65537")]:
        request = copy.deepcopy(baseline.input)
        request["directory"]["limits"] = {key: value}
        yield case("invalid-directory-" + key + "-" + value, baseline, request=request, refusal="ntfs_directory_limits")
    request = copy.deepcopy(baseline.input)
    request["empty_reader"] = True
    yield case("invalid-reader", baseline, request=request, refusal="ntfs_capture_reader")


def expected_cases():
    return [dict(case=name, request_sha256=sha(canonical([request])), diagnostic=diagnostic,
                 refusal=refusal, initial_reads=[dict(offset=str(at), bytes=str(n)) for at, n in v.initial_reads],
                 regions=v.regions(), table_sha256=sha(v.table.table), expected=v.expected())
            for name, v, request, diagnostic, refusal in cases()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    expected = expected_cases()
    summary = dict(status="expected-only", count=len(expected), expected_cases_sha256=sha(canonical(expected)),
                   recipe_sha256=sha(Path(__file__).read_bytes()), cases=[])

    def save():
        args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")

    save()
    if args.probe is None:
        summary["expected"] = expected
        save()
        return
    try:
        for wanted, (name, v, request, diagnostic, refusal) in zip(expected, cases()):
            payload = canonical([request])
            p = subprocess.run([str(args.probe.resolve())], input=payload, capture_output=True, timeout=30)
            raw = args.output.with_name(args.output.stem + "-response-" + str(len(summary["cases"])) + ".json")
            raw.write_bytes(p.stdout)
            row = dict(case=name, request_sha256=sha(payload), response_sha256=sha(p.stdout),
                       raw_output=str(raw.resolve()), passed=False)
            summary["cases"].append(row)
            save()
            assert p.returncode == 0 and not p.stderr, (name, p.returncode, p.stderr)
            values = json.loads(p.stdout)
            assert len(values) == 1
            result = values[0]
            assert result["source_unchanged"] and result["refusal"] == refusal, (name, result)
            if refusal:
                assert result["report"] is None and result["requests"] == []
            else:
                report = result["report"]
                assert report["schema"] == "org.disked.ntfs-name-order-observation-prototype/1"
                assert report["diagnostic"] == diagnostic, (name, diagnostic, report["diagnostic"])
                completed = diagnostic in ("", "ntfs_name_order_mapped_descent")
                assert report["complete"] == completed and report["reread_equal"] == completed
                assert report["applicable"] == (not diagnostic)
                assert not any(report[k] for k in ("atomic_snapshot", "current_source_authority", "effects_authorized"))
                reads = wanted["initial_reads"] * 2
                assert result["requests"] == reads[:len(result["requests"])], (name, result["requests"], reads)
                assert report["read_requests"] == str(len(result["requests"]))
                assert report["read_bytes"] == str(sum(int(r["bytes"]) for r in result["requests"]))
                assert report["regions"] == wanted["regions"][:len(report["regions"])]
                assert report["retained_bytes"] == str(sum(int(r["bytes"]) for r in report["regions"]))
                assert len(canonical(report)) <= int(request["limits"]["output_bytes"])
                audit = report["name_order"]
                if completed or name.startswith("reread-change-"):
                    assert audit["complete"]
                    for key, value in wanted["expected"].items():
                        assert audit[key] == value, (name, key, audit[key], value)
                    assert audit["schema"] == "org.disked.ntfs-directory-name-order/1"
                    assert audit["policy"] == "supplied-table-key-observations/1" and audit["case_policy"] == "unobserved"
                    assert not any(audit[k] for k in ("namespace_verified", "collation_verified", "target_membership_verified",
                                                       "alias_resolution_admitted", "lookup_admitted"))
                    for key in ("source_id", "epoch"):
                        assert audit[key] == v.input[key]
                    assert audit["volume_offset"] == v.input["offset"] and audit["volume_bytes"] == v.input["length"]
                    assert audit["directory_reference"] == str(v.directory.reference)
                    assert audit["table_sha256"] == wanted["table_sha256"] == report["upcase"]["table_sha256"]
                    assert report["upcase"]["table_hex"] == v.table.table.hex()
                    assert audit["directory_sha256"] == sha(canonical(report["directory"]))
                    for counter, array in [("keys_returned", "order"), ("adjacent_returned", "adjacent"),
                                           ("reference_groups_returned", "reference_groups"), ("mapped_groups_returned", "mapped_groups")]:
                        assert audit[counter] == str(len(audit[array]))
                if name == "output-before-table":
                    assert audit is None
                    assert len(result["requests"]) <= len(v.initial_reads) - len(v.table.table_reads)
                if name.startswith("reread-change-"):
                    assert report["upcase"]["complete"] and report["directory"]["index_complete"]
            row["passed"] = True
            save()
    except BaseException as error:
        summary.update(status="fail", error=repr(error))
        save()
        raise
    summary["status"] = "pass"
    save()


if __name__ == "__main__":
    main()
