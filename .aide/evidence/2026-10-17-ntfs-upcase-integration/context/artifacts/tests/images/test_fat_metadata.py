"""Independent original-name and FAT calendar expectations; no host effects."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import struct
import subprocess
import unittest

PROBE = None
NATIVE = None
RESULTS = []


def record(name=b"EXAMPLE TXT", attributes=32, case=0, dates=None):
    raw = bytearray(32)
    raw[:11] = name
    raw[11] = attributes
    raw[12] = case
    if dates:
        creation_date, creation_time, fraction, access_date, write_date, write_time = dates
        raw[13] = fraction
        struct.pack_into("<HHH", raw, 14, creation_time, creation_date, access_date)
        struct.pack_into("<HH", raw, 22, write_time, write_date)
    return raw


def fat_date(year, month, day):
    return ((year - 1980) << 9) | (month << 5) | day


def fat_time(hour, minute, second):
    return (hour << 11) | (minute << 5) | (second // 2)


def slots(units, raw):
    checksum = 0
    for byte in raw[:11]:
        checksum = (((checksum & 1) << 7) + (checksum >> 1) + byte) & 255
    padded = list(units)
    if len(padded) % 13:
        padded.append(0)
        padded.extend([65535] * (-len(padded) % 13))
    positions = (1, 3, 5, 7, 9, 14, 16, 18, 20, 22, 24, 28, 30)
    result = bytearray()
    count = len(padded) // 13
    for index in reversed(range(count)):
        part = bytearray(32)
        part[0] = index + 1 + (64 if index == count - 1 else 0)
        part[11] = 15
        part[13] = checksum
        for at, unit in zip(positions, padded[index * 13:(index + 1) * 13]):
            struct.pack_into("<H", part, at, unit)
        result.extend(part)
    return result


def utf16(text):
    data = text.encode("utf-16-le")
    return list(struct.unpack("<" + "H" * (len(data) // 2), data))


def run(raw=None, long=None, **options):
    raw = record() if raw is None else raw
    value = {"record": bytes(raw).hex(), "slots": bytes(long or b"").hex(), **options}
    completed = subprocess.run([str(PROBE)], input=json.dumps(value).encode() + b"\n",
                               capture_output=True, timeout=10)
    assert completed.returncode == 0 and not completed.stderr, completed.stderr.decode()
    reply = json.loads(completed.stdout)
    RESULTS.append({"input": value, "output": reply})
    if "value" in reply:
        mapped = reply["value"]
        assert mapped["original"]["raw_record"] == bytes(raw).hex()
        assert mapped["original"]["raw_oem_name"] == bytes(raw[:11]).hex()
        assert mapped["original"]["raw_long_slots"] == bytes(long or b"").hex()
        assert not mapped["authorizes_effects"]
        if mapped["status"] == "candidate":
            assert not mapped["native_metadata_applied"]
            assert not mapped["native_collision_checked"]
    return reply


def ticks(local, offset=0):
    utc = local.replace(tzinfo=timezone.utc) - timedelta(minutes=offset)
    delta = utc - datetime(1601, 1, 1, tzinfo=timezone.utc)
    return str((delta.days * 86400 + delta.seconds) * 10_000_000 + delta.microseconds * 10)


class MetadataTests(unittest.TestCase):
    def candidate(self, reply, name=None, basis=None):
        value = reply["value"]
        self.assertEqual("candidate", value["status"])
        if name is not None:
            self.assertEqual(name, value["name"]["utf8"])
            self.assertEqual(list(map(str, utf16(name))), value["name"]["utf16_units"])
        if basis is not None:
            self.assertEqual(basis, value["name"]["basis"])
        return value

    def test_short_alias_and_explicit_oem(self):
        for bits in (12, 16, 32):
            for case, expected in ((0, "EXAMPLE.TXT"), (8, "example.TXT"),
                                   (16, "EXAMPLE.txt"), (24, "example.txt")):
                self.candidate(run(record(case=case), bits=str(bits)), expected, "short_name")
        self.candidate(run(record(b"NAME       ")), "NAME")
        raw = record(b"\x05FILE   BIN")
        result = run(raw, mapping={"229": "963"}, oem_code_page="437")
        self.candidate(result, "σFILE.BIN")
        self.assertEqual("05", result["value"]["original"]["raw_oem_name"][:2])
        self.candidate(run(record(b"\x82FILE   TXT"), mapping={"130": "233"},
                           oem_code_page="850"), "éFILE.TXT")
        for options in ({"oem_code_page": "0"}, {"decoder_fault": "missing"},
                        {"oem_code_page": "99999"}, {"decoder_fault": "throw"},
                        {"decoder_fault": "ascii_changed"}, {"decoder_fault": "surrogate"},
                        {"decoder_fault": "empty"}):
            self.assertEqual("refused", run(**options)["value"]["status"])
        value = run(record(b"\x82FILE   TXT", case=8), mapping={"130": "233"})["value"]
        self.assertEqual("fat_metadata_non_ascii_case", value["diagnostic"])

    def test_original_long_units_and_explicit_alias_selection(self):
        raw = record()
        for name in ("Hello.txt", "é.txt", "e\u0301.txt", "😀.txt", "x" * 255):
            long = slots(utf16(name), raw)
            value = self.candidate(run(raw, long, oem_code_page="0", decoder_fault="missing"),
                                   name, "long_name")
            original = list(map(int, value["original"]["long_units"]))
            self.assertEqual(utf16(name), original[:len(utf16(name))])
            self.assertTrue(value["name"]["matches_selected_original_name"])
            self.candidate(run(raw, long, name_selection="short"), "EXAMPLE.TXT", "short_name")
        malformed = slots([0xd800], raw)
        self.assertEqual("refused", run(raw, malformed)["value"]["status"])
        self.candidate(run(raw, malformed, name_selection="short"), "EXAMPLE.TXT")
        bad_checksum = slots(utf16("Long.txt"), raw)
        bad_checksum[13] ^= 1
        self.assertEqual("refused", run(raw, bad_checksum)["value"]["status"])

    def test_native_component_refusal_and_identity_mapping(self):
        raw = record()
        for name in ("CON", "con.txt", "COM¹.txt", "LPT².bin", "CONIN$", "NUL",
                     "name.", "name ", "dir/name", "dir\\name", "x:y", "x\x1b", ".."):
            long = slots(utf16(name), raw)
            with self.subTest(name=name):
                value = run(raw, long)["value"]
                self.assertEqual("refused", value["status"])
                mapped = self.candidate(run(raw, long, unrepresentable_name="identity",
                                            source_offset="18446744073709551615"),
                                        "entry_18446744073709551615", "synthetic_identity")
                self.assertFalse(mapped["name"]["matches_selected_original_name"])
                self.assertIsNotNone(mapped["diagnostic"])
        self.candidate(run(record(b"COM0    TXT")), "COM0.TXT")
        self.candidate(run(record(b"COM9    TXT"), name_selection="identity", decoder_fault="throw"),
                       "entry_512", "synthetic_identity")
        self.assertEqual("refused", run(record(b"CON     TXT"))["value"]["status"])

    def test_exact_calendar_candidates_and_precision(self):
        for year, month, day in ((1980, 1, 1), (2000, 2, 29), (2026, 10, 14), (2107, 12, 31)):
            date = fat_date(year, month, day)
            time = fat_time(23, 59, 58)
            raw = record(dates=(date, time, 199, date, date, time))
            for offset in (-840, 0, 330, 840):
                value = self.candidate(run(raw, time_interpretation="fixed_offset",
                                           utc_offset_minutes=str(offset)))
                expected = datetime(year, month, day, 23, 59, 59, 990000)
                self.assertEqual(ticks(expected, offset), value["creation"]["filetime_candidate"])
                self.assertEqual(ticks(expected.replace(second=58, microsecond=0), offset),
                                 value["write"]["filetime_candidate"])
                self.assertEqual(ticks(datetime(year, month, day), offset),
                                 value["access"]["filetime_candidate"])
                for key in ("creation", "write", "access"):
                    self.assertEqual("candidate", value[key]["status"])
                self.assertEqual("10ms", value["creation"]["precision"])
                self.assertEqual("2s", value["write"]["precision"])
                self.assertEqual("date_at_local_midnight", value["access"]["precision"])

    def test_unspecified_invalid_and_raw_only_are_unapplied(self):
        date = fat_date(2026, 10, 14)
        time = fat_time(12, 34, 56)
        value = self.candidate(run(record(dates=(date, time, 12, date, date, time))))
        for key in ("creation", "write", "access"):
            self.assertEqual("raw_only", value[key]["reason"])
            self.assertIsNone(value[key]["filetime_candidate"])
        value = self.candidate(run(time_interpretation="fixed_offset"))
        for key in ("creation", "write", "access"):
            self.assertEqual("unspecified", value[key]["reason"])
        for bad_date in (fat_date(2100, 2, 29), fat_date(2026, 13, 1), fat_date(2026, 1, 0)):
            value = self.candidate(run(record(dates=(bad_date, time, 12, bad_date, date, time)),
                                       time_interpretation="fixed_offset"))
            self.assertEqual("invalid", value["creation"]["reason"])
            self.assertEqual("invalid", value["access"]["reason"])
            self.assertEqual("candidate", value["write"]["status"])
        for bad_time in ((24 << 11), (60 << 5), 31):
            value = self.candidate(run(record(dates=(date, bad_time, 0, date, date, time)),
                                       time_interpretation="fixed_offset"))
            self.assertEqual("invalid", value["creation"]["reason"])
            self.assertEqual("candidate", value["write"]["status"])
        value = self.candidate(run(record(dates=(date, time, 200, date, date, time)),
                                   time_interpretation="fixed_offset"))
        self.assertEqual("invalid", value["creation"]["reason"])

    def test_policy_refusal_precedes_decoder_calls(self):
        for options in ({"name_selection": "guess"}, {"unrepresentable_name": "replace"},
                        {"time_interpretation": "host_local"}, {"utc_offset_minutes": "1"},
                        {"time_interpretation": "fixed_offset", "utc_offset_minutes": "841"},
                        {"time_interpretation": "fixed_offset", "utc_offset_minutes": "-841"},
                        {"bits": "13"}):
            reply = run(**options)
            self.assertIn("error", reply)
            self.assertEqual("0", reply["decoder_calls"])

    def test_type_and_attribute_mapping_without_admission(self):
        for attributes in (0, 1, 2, 4, 32, 39, 16, 55):
            raw = record(attributes=attributes)
            if attributes & 16:
                struct.pack_into("<H", raw, 26, 10)
            value = self.candidate(run(raw))
            self.assertEqual(str(attributes & 39), value["native_attributes_candidate"])
        for raw in (record(attributes=8), record(attributes=24), record(attributes=64),
                    record(b".          ", attributes=16)):
            reply = run(raw, name_selection="identity")
            self.assertEqual("refused", reply["value"]["status"])
            self.assertEqual("0", reply["decoder_calls"])


def native_run(inputs):
    data = b"".join(json.dumps(value).encode() + b"\n" for value in inputs)
    completed = subprocess.run([str(NATIVE)], input=data, capture_output=True, timeout=20)
    assert completed.returncode == 0 and not completed.stderr, completed.stderr.decode()
    replies = [json.loads(line) for line in completed.stdout.splitlines()]
    assert len(replies) == len(inputs)
    for value, reply in zip(inputs, replies):
        RESULTS.append({"native": True, "input": value, "output": reply})
    return replies


class NativeMetadataTests(unittest.TestCase):
    def test_every_byte_in_explicit_pages_matches_independent_codec(self):
        for page in (437, 850):
            inputs = [{"kind": "decode", "oem_code_page": str(page), "bytes": bytes([n]).hex()}
                      for n in range(256)]
            for n, reply in enumerate(native_run(inputs)):
                expected = utf16(bytes([n]).decode("cp" + str(page)))
                self.assertEqual(list(map(str, expected)), reply["units"], (page, n))

    def test_native_name_candidates_and_raw_source_preservation(self):
        raw = record(b"\x05FILE   BIN")
        inputs = [{"record": raw.hex(), "oem_code_page": str(page)} for page in (437, 850)]
        for page, reply in zip((437, 850), native_run(inputs)):
            value = reply["value"]
            expected = b"\xe5FILE".decode("cp" + str(page)) + ".BIN"
            self.assertEqual(expected, value["name"]["utf8"])
            self.assertEqual(raw.hex(), value["original"]["raw_record"])
            self.assertFalse(value["native_metadata_applied"])
        raw = record()
        long = slots(utf16("e\u0301😀.txt"), raw)
        reply = native_run([{"record": raw.hex(), "slots": long.hex(), "oem_code_page": "0"}])[0]
        self.assertEqual("e\u0301😀.txt", reply["value"]["name"]["utf8"])
        self.assertEqual(long.hex(), reply["value"]["original"]["raw_long_slots"])

    def test_unknown_pages_and_invalid_bounds_remain_typed(self):
        inputs = [{"kind": "decode", "oem_code_page": str(page), "bytes": "41"}
                  for page in (0, 1, 2, 932, 65001)]
        for reply in native_run(inputs):
            self.assertEqual("fat_metadata_oem_unqualified", reply["error"])
        for reply in native_run([{"kind": "decode", "bytes": ""},
                                 {"kind": "decode", "bytes": "41" * 12}]):
            self.assertEqual("fat_metadata_oem_bounds", reply["error"])


def main():
    global PROBE, NATIVE
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    PROBE = args.probe.resolve()
    NATIVE = args.native.resolve()
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(kind)
                               for kind in (MetadataTests, NativeMetadataTests))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    args.output.write_text(json.dumps({"passed": result.wasSuccessful(), "methods": result.testsRun,
                                      "cases": len(RESULTS), "records": RESULTS}, indent=2) + "\n",
                           encoding="utf-8", newline="\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
