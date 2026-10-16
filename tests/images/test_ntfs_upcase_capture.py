"""Independent sparse FILE10/table layouts, exact reads, digests and failures."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from ntfs_closure_fixture import ClosureVolume, parts
from test_ntfs_capture import Volume, bytes_at
from test_ntfs_stream import entry, nonresident, record, ref, resident

TABLE = struct.pack("<65536H", *[(n * 40503 + 257) % 65536 for n in range(65536)])
MAXIMUM = dict(read_requests="512", read_bytes="2097152", retained_bytes="524288",
               attributes="4096", runs="4096", output_bytes="1048576")


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


class UpcaseVolume:
    def __init__(self, cluster=4096, size=1024, offset=0, minor=1, usa=48,
                 mft_closure=False, mft_first=None, mft_records=64, table=TABLE, data_length=131072,
                 initialized=None, table_runs=None, list_form="none", split=False,
                 reverse=False, extension_only=False, attributes=None, base_options=None,
                 extension_options=None, place_data=True, list_lcn=1400, place_list=True):
        self.cluster, self.size, self.offset = cluster, size, offset
        self.reference, self.extension_reference = ref(10, 17), ref(20, 23)
        self.table = table
        if mft_closure:
            v = ClosureVolume(cluster=cluster, size=size, offset=offset, minor=minor,
                              nonresident_list=True, volume_nonresident=True, usa=usa)
            self.mft_runs = v.full_runs
        else:
            count = max(2, (64 * size + cluster - 1) // cluster)
            first = mft_first if mft_first is not None else min(count - 1, max((size + cluster - 1) // cluster, 7 * 512 // cluster))
            self.mft_runs = [(first, 8), (count - first, 100)]
            payload = nonresident(runs=self.mft_runs, high=count - 1, allocated=count * cluster,
                                  data=mft_records * size, initialized=mft_records * size)
            v = Volume(spc=cluster // 512, size=size, offset=offset, minor=minor,
                       runs=self.mft_runs, data_payload=payload, usa=usa)
        self.input = copy.deepcopy(v.input)
        self.input.update(upcase=True, limits=copy.deepcopy(MAXIMUM))
        self.initial_reads = list(v.initial_reads)
        self.bootstrap_reads = list(v.initial_reads)
        initialized = data_length if initialized is None else initialized
        count = max(1, (data_length + cluster - 1) // cluster)
        self.table_runs = table_runs if table_runs is not None else (
            [(1, 1000), (count - 1, 2000)] if count > 1 else [(1, 1000)])
        full = nonresident(runs=self.table_runs, allocated=count * cluster, data=data_length,
                           initialized=initialized, instance=11, high=count - 1)
        selected = [full]
        extension = []
        descriptors = []
        if extension_only:
            assert list_form != "none"
            selected = []
            extension = [nonresident(runs=self.table_runs, allocated=count * cluster,
                                     data=data_length, initialized=initialized, instance=13,
                                     high=count - 1)]
            descriptors = [entry(self.extension_reference, 13)]
        elif split:
            assert list_form != "none" and count > 1 and len(self.table_runs) > 1
            first = self.table_runs[0][0]
            selected = [nonresident(runs=self.table_runs[:1], allocated=count * cluster,
                                    data=data_length, initialized=initialized, instance=11,
                                    high=first - 1)]
            extension = [nonresident(low=first, runs=self.table_runs[1:], high=count - 1,
                                     allocated=(1 << 64) - 1, data=(1 << 64) - 1,
                                     initialized=(1 << 64) - 1, instance=13)]
            descriptors = [entry(self.reference, 11), entry(self.extension_reference, 13, first)]
        elif list_form != "none":
            descriptors = [entry(self.reference, 11)]
        self.list_reads = []
        if descriptors:
            if reverse:
                descriptors.reverse()
            value = b"".join(descriptors)
            if list_form == "resident":
                selected.append(resident(value, kind=0x20, instance=7))
            else:
                selected.append(nonresident(runs=[(1, list_lcn)], allocated=cluster,
                                             data=len(value), initialized=len(value),
                                             kind=0x20, instance=7, high=0))
                self.list_reads = [(offset + at, n) for at, n in parts([(1, list_lcn)], cluster, 0, len(value))]
                if place_list:
                    self.place_logical([(1, list_lcn)], 0, value)
        self.base_attributes = [bytes(a) for a in (selected if attributes is None else attributes)]
        self.base_options = dict(base_options or {})
        options = dict(number=10, sequence=17, size=size, usa=usa)
        options.update(self.base_options)
        self.base_raw = record(self.base_attributes, **options)
        self.record_regions = {10: self.place_record(10, self.base_raw)}
        self.initial_reads += self.record_regions[10] + self.list_reads
        if extension:
            options = dict(number=20, sequence=23, base=self.reference, size=size, usa=usa)
            options.update(extension_options or {})
            self.extension_raw = record(extension, **options)
            self.record_regions[20] = self.place_record(20, self.extension_raw)
            self.initial_reads += self.record_regions[20]
        self.table_reads = [(offset + at, n) for at, n in parts(self.table_runs, cluster, 0, min(len(table), data_length))] if all(lcn is not None for _, lcn in self.table_runs) else []
        if place_data and all(lcn is not None for _, lcn in self.table_runs):
            self.place_logical(self.table_runs, 0, table[:data_length])
        self.initial_reads += self.table_reads

    def place_logical(self, runs, start, value):
        done = 0
        rows = []
        for at, n in parts(runs, self.cluster, start, len(value)):
            self.input["regions"].append(dict(offset=str(self.offset + at), hex=bytes(value[done:done + n]).hex()))
            rows.append((self.offset + at, n))
            done += n
        return rows

    def place_record(self, number, raw):
        return self.place_logical(self.mft_runs, number * self.size, raw)

    def regions(self):
        return [dict(offset=str(at), bytes=str(n), sha256=sha(bytes_at(self.input, at, n)))
                for at, n in self.initial_reads]

    def mutate(self, absolute, value):
        for item in self.input["regions"]:
            first = int(item["offset"])
            raw = bytearray.fromhex(item["hex"])
            if first <= absolute < first + len(raw):
                raw[absolute - first] = value
                item["hex"] = raw.hex()


def cases():
    def case(name, volume=None, diagnostic="", controls=None, refusal=""):
        v = volume or UpcaseVolume()
        request = copy.deepcopy(v.input)
        for key, value in (controls or {}).items():
            if key == "limits":
                request["limits"].update(value)
            else:
                request[key] = value
        return name, v, request, diagnostic, refusal

    for minor in (0, 1):
        for cluster, size in ((512, 512), (512, 1024), (4096, 1024), (4096, 4096),
                              (65536, 1024), (4096, 32768)):
            yield case(f"geometry-{minor}-{cluster}-{size}", UpcaseVolume(cluster=cluster, size=size, minor=minor))
    yield case("above4GiB", UpcaseVolume(offset=(1 << 32) + 4096))
    yield case("old-header", UpcaseVolume(usa=42, minor=0))
    yield case("exact-MFT-initialized-boundary", UpcaseVolume(mft_records=11))
    yield case("FILE10-outside-initialized-MFT", UpcaseVolume(mft_records=10), "ntfs_upcase_reference_bounds")
    yield case("base-across-MFT-run-boundary", UpcaseVolume(cluster=512, mft_first=21))
    yield case("negative-table-LCN-delta", UpcaseVolume(table_runs=[(1, 3000), (31, 1000)]))
    for form in ("resident", "nonresident"):
        for split, extension_only, reverse in ((False, False, False), (True, False, False),
                                               (True, False, True), (False, True, False)):
            yield case(f"list-{form}-{split}-{extension_only}-{reverse}",
                       UpcaseVolume(list_form=form, split=split, extension_only=extension_only, reverse=reverse))
    yield case("MFT-and-Volume-and-UpCase-nonresident-list-closure",
               UpcaseVolume(mft_closure=True, list_form="nonresident", split=True, reverse=True))
    for n in (131071, 131073, 0):
        yield case(f"table-data-length-{n}", UpcaseVolume(data_length=n, place_data=False), "ntfs_upcase_stream_size")
    yield case("uninitialized-table-suffix", UpcaseVolume(initialized=131071), "ntfs_upcase_stream_size")
    yield case("resident-table", UpcaseVolume(attributes=[resident(b"A\0")]), "ntfs_upcase_stream_form")
    named = nonresident(runs=[(32, 1000)], allocated=131072, data=131072, initialized=131072, name=b"x\0")
    yield case("named-stream-cannot-replace-unnamed", UpcaseVolume(attributes=[named]), "ntfs_upcase_join_attribute_missing")
    for flags in (1, 0x4000, 0x8000):
        a = nonresident(runs=[(32, 1000)], allocated=131072, data=131072, initialized=131072, flags=flags)
        yield case(f"unsupported-stream-flags-{flags}", UpcaseVolume(attributes=[a]), "ntfs_upcase_join_feature_unsupported")
    for options, name in [({"flags": 3}, "directory"), ({"flags": 0}, "unused-record"),
                           ({"flags": 5}, "unknown-record-flags"), ({"sequence": 0}, "zero-sequence"),
                           ({"number": 11}, "wrong-header-number"), ({"base": ref(9, 3)}, "extension-as-base")]:
        yield case(name, UpcaseVolume(base_options=options), "ntfs_upcase_record")
    for at, value, name in ((0, 0, "bad-signature"), (510, 0, "torn-FILE10")):
        v = UpcaseVolume()
        v.mutate(v.record_regions[10][0][0] + at, value)
        yield case(name, v, "ntfs_upcase_record")
    for field, wrong in (("sequence", 24), ("base", ref(10, 18)), ("number", 21)):
        yield case("wrong-extension-" + field, UpcaseVolume(list_form="resident", split=True,
                   extension_options={field: wrong}), "ntfs_upcase_extension_record")
    for lcn, code in ((0, "ntfs_metadata_physical_alias"), (5000, "ntfs_metadata_physical_alias"),
                      (8, "ntfs_upcase_physical_alias"), (100, "ntfs_upcase_physical_alias")):
        yield case("table-alias-" + str(lcn), UpcaseVolume(table_runs=[(32, lcn)], place_data=False), code)
    yield case("table-own-list-alias", UpcaseVolume(list_form="nonresident", list_lcn=1000, place_data=False), "ntfs_upcase_physical_alias")
    yield case("list-MFT-alias-before-value-read", UpcaseVolume(list_form="nonresident", list_lcn=8, place_list=False), "ntfs_list_physical_alias")
    for lcn in (300, 700):
        yield case("UpCase-list-other-list-alias-" + str(lcn),
                   UpcaseVolume(mft_closure=True, list_form="nonresident", list_lcn=lcn,
                                place_list=False), "ntfs_list_physical_alias")
        yield case("table-other-list-alias-" + str(lcn),
                   UpcaseVolume(mft_closure=True, table_runs=[(32, lcn)], place_data=False),
                   "ntfs_upcase_physical_alias")
    yield case("self-overlapping-table-mapping", UpcaseVolume(table_runs=[(1, 1000), (31, 1000)],
                                                             place_data=False), "ntfs_upcase_join_physical_overlap")
    yield case("table-run-outside-volume", UpcaseVolume(table_runs=[(32, 9990)], place_data=False),
               "ntfs_upcase_mapping")
    yield case("extension-outside-initialized-MFT", UpcaseVolume(mft_records=11, list_form="resident", split=True),
               "ntfs_upcase_reference_bounds")
    v = UpcaseVolume()
    v.mutate(v.offset + 5000 * v.cluster + 18, 2)
    yield case("mirror-disagreement-before-FILE10", v, "ntfs_mirror_disagreement")
    yield case("version-disagreement-before-FILE10", UpcaseVolume(minor=0), "ntfs_volume_version", {"minor": "1"})
    v = UpcaseVolume()
    count, total = len(v.initial_reads), sum(n for _, n in v.initial_reads)
    yield case("exact-read-and-retained-quotas", v, controls={"limits": dict(read_requests=str(2 * count), read_bytes=str(2 * total), retained_bytes=str(total))})
    yield case("exact-attribute-run-quotas", v, controls={"limits": dict(attributes="4", runs="6")})
    for name, limits, code in [
        ("one-short-request", {"read_requests": str(2 * count - 1)}, "ntfs_read_budget"),
        ("one-short-byte", {"read_bytes": str(2 * total - 1)}, "ntfs_read_budget"),
        ("one-short-retained", {"retained_bytes": str(total - 1)}, "ntfs_retained_budget"),
        ("small-output-before-table", {"output_bytes": "16384"}, "ntfs_output_budget"),
        ("attribute-quota", {"attributes": "3"}, "ntfs_attribute_budget"),
        ("run-quota", {"runs": "5"}, "ntfs_run_budget")]:
        yield case(name, v, code, {"limits": limits})
    for n in range(1, 2 * count + 1):
        for mode in ("short", "null", "oversize", "throw"):
            yield case(f"{mode}-callback-{n}", v, "ntfs_reader_failure" if mode == "throw" else "ntfs_read_length",
                       {"fault": dict(mode=mode, call=str(n))})
        if n > count:
            yield case(f"changed-reread-{n}", v, "ntfs_source_changed", {"fault": dict(mode="change", call=str(n))})
    yield case("request-and-reader-owned-before-first-callback", v, controls={"fault": dict(mode="mutate-controls", call="1")})
    for key, value, suffix in (("epoch", "0", "inputs"), ("source_id", "x\0y", "inputs"),
                                ("major", "2", "inputs"), ("length", "511", "inputs"),
                                ("source_bytes", "1", "window")):
        yield case("invalid-" + key, v, controls={key: value}, refusal="ntfs_capture_" + suffix)
    yield case("empty-reader", v, controls={"empty_reader": True}, refusal="ntfs_capture_reader")


def prepare():
    rows = []
    for name, v, request, diagnostic, refusal in cases():
        rows.append(dict(case=name, request_sha256=sha(canonical(request)), diagnostic=diagnostic,
                         refusal=refusal, success=not diagnostic and not refusal,
                         table_sha256=sha(v.table), expected_reads=[dict(offset=str(at), bytes=str(n)) for at, n in v.initial_reads * 2]))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    expected = prepare()
    summary = dict(status="expected-only", expected_cases_sha256=sha(canonical(expected)),
                   count=len(expected), recipe_sha256=sha(Path(__file__).read_bytes()), cases=[])

    def save():
        args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")

    save()
    if args.probe is None:
        summary["expected"] = expected
        save()
        return
    try:
        for name, v, request, diagnostic, refusal in cases():
            payload = canonical([request])
            completed = subprocess.run([str(args.probe.resolve())], input=payload, capture_output=True, timeout=30)
            receipt = dict(case=name, request_sha256=sha(payload), response_sha256=sha(completed.stdout), passed=False)
            summary["cases"].append(receipt)
            save()
            try:
                assert completed.returncode == 0 and not completed.stderr, (name, completed.returncode, completed.stderr)
                values = json.loads(completed.stdout)
                assert len(values) == 1
                result = values[0]
                assert result["source_unchanged"] and result["refusal"] == refusal, (name, result)
                if refusal:
                    assert result["requests"] == [] and result["report"] is None
                else:
                    report = result["report"]
                    assert report["schema"] == "org.disked.ntfs-upcase-observation-prototype/1"
                    assert report["diagnostic"] == diagnostic, (name, diagnostic, report["diagnostic"])
                    assert report["applicable"] == (not diagnostic)
                    assert report["complete"] == (not diagnostic) and report["reread_equal"] == (not diagnostic)
                    assert not any(report[k] for k in ("atomic_snapshot", "current_source_authority", "effects_authorized"))
                    wanted = [dict(offset=str(at), bytes=str(n)) for at, n in v.initial_reads * 2]
                    assert result["requests"] == wanted[:len(result["requests"])], (name, result["requests"], wanted)
                    assert int(report["read_requests"]) == len(result["requests"])
                    assert int(report["read_bytes"]) == sum(int(r["bytes"]) for r in result["requests"])
                    assert int(report["retained_bytes"]) == sum(int(r["bytes"]) for r in report["regions"])
                    assert report["regions"] == v.regions()[:len(report["regions"])]
                    assert len(canonical(report)) <= int(request["limits"]["output_bytes"])
                    if not diagnostic:
                        assert result["requests"] == wanted
                        table = report["upcase"]
                        assert table["schema"] == "org.disked.ntfs-upcase-table-observation/1" and table["complete"]
                        assert table["table_hex"] == v.table.hex() and table["table_sha256"] == sha(v.table)
                        assert table["table_bytes"] == "131072" and table["base_reference"] == str(v.reference)
                        assert table["base_record_sha256"] == sha(v.base_raw)
                        assert table["source_id"] == v.input["source_id"] and table["epoch"] == v.input["epoch"]
                        assert table["volume_offset"] == v.input["offset"] and table["volume_bytes"] == v.input["length"]
                        assert table["volume_serial"] == str(int.from_bytes(bytes_at(v.input, v.offset + 72, 8), "little"))
                        closure = report["record_closures"]["upcase"]
                        assert closure["base_reference"] == str(v.reference) and closure["join_current"]
                        assert closure["join"]["complete"] and closure["join"]["name_hex"] == ""
                    if name == "small-output-before-table":
                        assert len(result["requests"]) <= len(v.initial_reads) - len(v.table_reads)
                    if name.startswith("changed-reread-"):
                        assert report["upcase"]["complete"] and report["upcase"]["table_sha256"] == sha(v.table)
                receipt["passed"] = True
            except BaseException:
                args.output.with_suffix(".failure-input.json").write_bytes(payload)
                args.output.with_suffix(".failure-response.json").write_bytes(completed.stdout)
                args.output.with_suffix(".failure-stderr.log").write_bytes(completed.stderr)
                raise
        summary["status"] = "pass"
    except BaseException as error:
        summary.update(status="fail", error=repr(error))
        save()
        raise
    save()
    print(json.dumps(dict(status=summary["status"], count=summary["count"])))


if __name__ == "__main__":
    main()
