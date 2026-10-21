"""Independent byte/CRC/geometry checks; no Windows or native probe execution."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('windows_reference_recipes', ROOT/'tests/corpus/windows_partitions.py')
fixtures = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixtures)


class WindowsFixtureTests(unittest.TestCase):
    def test_exact_frozen_case_geometry_and_hashes(self):
        path = ROOT/'.aide/evidence/2026-10-21-windows-reference/fixtures-before-native.json'
        frozen = json.loads(path.read_bytes())
        self.assertEqual('expected_before_native_or_windows_evaluation', frozen['status'])
        self.assertEqual('sha256:'+hashlib.sha256((ROOT/frozen['generator']).read_bytes()).hexdigest(), frozen['generator_sha256'])
        self.assertEqual(list(fixtures.CASES), [v['name'] for v in frozen['cases']])
        for row in frozen['cases']:
            with self.subTest(name=row['name']):
                body = fixtures.generate(row['name'])
                self.assertEqual(4194304, len(body))
                self.assertEqual(512, row['unit']); self.assertEqual(8192, row['blocks'])
                self.assertEqual('sha256:'+hashlib.sha256(body).hexdigest(), row['sha256'])
                if row['family'] == 'mbr':
                    self.assertIsNone(row['backup_first'])
                    self.assertIsNone(row['primary_header_crc_valid'])
                    self.assertIsNone(row['backup_header_crc_valid'])
                else:
                    primary = self.parse_copy(body, 1); backup = self.parse_copy(body, 8191)
                    self.assertEqual(row['primary_header_crc_valid'], primary[0])
                    self.assertEqual(row['backup_header_crc_valid'], backup[0])
                    self.assertEqual(row['primary_first'], primary[1][0][0])
                    self.assertEqual(row['backup_first'], backup[1][0][0])

    def test_mbr_layout_is_explicit_and_bounded(self):
        body = fixtures.generate('mbr-valid')
        self.assertEqual(b'\x55\xaa', body[510:512])
        self.assertEqual(0xD15CED01, struct.unpack_from('<I', body, 440)[0])
        rows = []
        for slot in range(4):
            record = body[446+slot*16:462+slot*16]
            rows.append((record[4], *struct.unpack_from('<II', record, 8)))
        self.assertEqual([(7, 2048, 1024), (0x83, 4096, 1024), (0, 0, 0), (0, 0, 0)], rows)
        self.assertEqual(bytes(4194304-512), body[512:])

    def parse_copy(self, body, lba):
        header = bytearray(body[lba*512:(lba+1)*512])
        self.assertEqual(b'EFI PART', header[:8])
        self.assertEqual((0x10000, 92), struct.unpack_from('<II', header, 8))
        checksum = struct.unpack_from('<I', header, 16)[0]
        struct.pack_into('<I', header, 16, 0)
        valid = checksum == zlib.crc32(header[:92])
        my, other, first, last = struct.unpack_from('<QQQQ', header, 24)
        self.assertEqual(lba, my); self.assertEqual(8192-1 if lba == 1 else 1, other)
        self.assertEqual((34, 8158), (first, last))
        table_lba, count, size, table_crc = struct.unpack_from('<QIII', header, 72)
        self.assertEqual((128, 128), (count, size))
        self.assertEqual(2 if lba == 1 else 8159, table_lba)
        rows = body[table_lba*512:table_lba*512+count*size]
        self.assertEqual(table_crc, zlib.crc32(rows))
        ranges = [struct.unpack_from('<QQ', rows, slot*128+32) for slot in (0, 1)]
        self.assertEqual(bytes(16384-256), rows[256:])
        for start, end in ranges: self.assertTrue(first <= start <= end <= last)
        return valid, ranges, rows

    def test_gpt_headers_arrays_and_protective_mbr(self):
        for name in fixtures.CASES[1:]:
            with self.subTest(name=name):
                body = fixtures.generate(name)
                self.assertEqual(0xee, body[450])
                self.assertEqual((1, 8191), struct.unpack_from('<II', body, 454))
                primary = self.parse_copy(body, 1); backup = self.parse_copy(body, 8191)
                self.assertEqual(name != 'gpt-primary-damaged', primary[0]); self.assertTrue(backup[0])
                self.assertEqual([(2048, 3071), (4096, 5119)], primary[1])
                self.assertEqual([(2049 if name == 'gpt-conflicting' else 2048, 3071), (4096, 5119)], backup[1])
                self.assertEqual(name != 'gpt-conflicting', primary[2] == backup[2])

    def test_damage_changes_only_one_declared_crc_byte(self):
        valid = fixtures.generate('gpt-valid'); damaged = fixtures.generate('gpt-primary-damaged')
        self.assertEqual([528], [i for i, pair in enumerate(zip(valid, damaged)) if pair[0] != pair[1]])

    def test_unknown_fixture_cannot_choose_an_implicit_default(self):
        for name in ('', 'unknown', '../gpt-valid', None):
            with self.subTest(name=name), self.assertRaises(ValueError): fixtures.generate(name)


if __name__ == '__main__': unittest.main()
