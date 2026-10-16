"""Independent supplied-byte FAT metadata/chain fixtures; no file or device I/O."""
import argparse
import hashlib
import json
import random
import struct
import subprocess
import unittest
from pathlib import Path

TRUNCATED, SIGNATURE, SECTOR, CLUSTER = 1, 2, 4, 8
COUNTERS, REGIONS, CAPACITY, TABLE_SIZE = 16, 32, 64, 128
TYPE_SHAPE, VERSION, FLAGS, ROOT, AUXILIARY, RESERVED = 256, 512, 1024, 2048, 4096, 8192
COUNTS = {12: 2847, 16: 5000, 32: 65525}
MASKS = {12: 0xfff, 16: 0xffff, 32: 0x0fffffff}
PROBE = None
RECEIPTS = []


def boot(clusters, unit=512, per_cluster=1, copies=2, trailing=0):
    bits = 12 if clusters < 4085 else (16 if clusters < 65525 else 32)
    reserved = 32 if bits == 32 else 1
    root_entries = 0 if bits == 32 else unit//32
    table_bytes = ((clusters+2)*bits+7)//8
    fat_sectors = (table_bytes+unit-1)//unit
    root_sectors = root_entries*32//unit
    first = reserved+copies*fat_sectors+root_sectors
    total = first+clusters*per_cluster+trailing
    assert 0 < total <= 0xffffffff and fat_sectors <= (0xffffffff if bits == 32 else 0xffff)
    raw = bytearray(unit)
    raw[:3] = b'\xeb\x3c\x90'
    struct.pack_into('<HBHBH', raw, 11, unit, per_cluster, reserved, copies, root_entries)
    if total < 65536:
        struct.pack_into('<H', raw, 19, total)
    else:
        struct.pack_into('<I', raw, 32, total)
    raw[21] = 0xf8
    if bits == 32:
        struct.pack_into('<IHHIHH', raw, 36, fat_sectors, 0, 0, 2, 1, 6)
        raw[82:90] = b'FAT32   '
    else:
        struct.pack_into('<H', raw, 22, fat_sectors)
        raw[54:62] = f'FAT{bits}   '.encode()[:8]
    raw[510:512] = b'\x55\xaa'
    return raw, dict(bits=bits, total=total, first=first, root_entries=root_entries,
                     fat_sectors=fat_sectors, reserved=reserved, clusters=clusters,
                     unit=unit, per_cluster=per_cluster, copies=copies, trailing=trailing)


def volume(raw, available=None):
    if available is None:
        total = int.from_bytes(raw[19:21], 'little') or int.from_bytes(raw[32:36], 'little')
        available = total*int.from_bytes(raw[11:13], 'little')
    return dict(op='volume', boot=bytes(raw).hex(), available=str(available))


def packed(bits, mapping, length=None):
    # Bit positions encode the mathematical packed array independently of the C
    # reader's odd/even cell-offset implementation. Preserve neighboring cells.
    width = 32 if bits == 32 else bits
    size = max(((index+1)*width+7)//8 for index in mapping) if mapping else 0
    n = 0
    for index, value in mapping.items():
        n |= value << (index*width)
    data = n.to_bytes(size, 'little')
    return data if length is None else data[:length]


def entry(bits, index, data, clusters=None):
    return dict(op='entry', fat=data.hex(), bits=str(bits),
                clusters=str(COUNTS[bits] if clusters is None else clusters), index=str(index))


def chain(bits, data, start=2, budget=32, capacity=None):
    return dict(op='chain', fat=data.hex(), bits=str(bits), clusters=str(COUNTS[bits]),
                start=str(start), budget=str(budget), capacity=str(budget if capacity is None else capacity))


def run(requests):
    data = b''.join(json.dumps(r, sort_keys=True, separators=(',', ':')).encode()+b'\n' for r in requests)
    result = subprocess.run([str(PROBE)], input=data, capture_output=True, timeout=60)
    assert result.returncode == 0 and not result.stderr, result.stderr.decode(errors='replace')
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(rows) == len(requests)
    RECEIPTS.append(dict(cases=len(requests), input_sha256=hashlib.sha256(data).hexdigest(),
                         output_sha256=hashlib.sha256(result.stdout).hexdigest()))
    return rows


class FatTests(unittest.TestCase):
    def test_cluster_thresholds_all_sector_and_cluster_units(self):
        requests, expected = [], []
        for count in (1, 2847, 4084, 4085, 65524, 65525, 70000):
            for unit in (512, 1024, 2048, 4096):
                for per_cluster in (1, 2, 4, 8, 16, 32, 64, 128):
                    raw, values = boot(count, unit, per_cluster)
                    requests.append(volume(raw)); expected.append(values)
        for row, e in zip(run(requests), expected):
            self.assertEqual((row['status'], row['issues'], row['usable']), (0, 0, True))
            self.assertEqual((row['bits'], row['cluster_count']), (e['bits'], e['clusters']))
            self.assertEqual(row['first_data_sector'], e['first'])
            self.assertEqual(int(row['data_offset_bytes']), e['first']*e['unit'])
            self.assertEqual(int(row['fat_bytes']), e['fat_sectors']*e['unit'])
            self.assertEqual(int(row['volume_bytes']), e['total']*e['unit'])
            self.assertEqual(row['data_sectors'], e['clusters']*e['per_cluster'])
            self.assertEqual(row['cluster_bytes'], e['unit']*e['per_cluster'])

    def test_large_byte_extents_and_trailing_partial_cluster(self):
        raw, expected = boot(60000000, 512, 64, trailing=63)
        row = run([volume(raw)])[0]
        self.assertTrue(row['usable']); self.assertEqual(row['cluster_count'], 60000000)
        self.assertGreater(int(row['volume_bytes']), 2**32)
        self.assertEqual(int(row['volume_bytes']), expected['total']*512)
        self.assertEqual(row['data_sectors'], 60000000*64+63)

    def test_nonstandard_copy_count_preserved_without_automatic_selection(self):
        requests = [volume(boot(65525, copies=n)[0]) for n in (1, 3, 16, 255)]
        for row, n in zip(run(requests), (1, 3, 16, 255)):
            self.assertTrue(row['usable']); self.assertEqual(row['fat_count'], n)

    def test_labels_hidden_sectors_and_padding_do_not_select_geometry(self):
        requests = []
        for count in (2847, 5000, 65525):
            raw, _ = boot(count)
            raw[3:11] = b'EXFAT   '
            raw[54:62] = b'FAT32   ' if count < 65525 else b'FAT12   '
            # FAT32 extended reserved fields include54..61; preserve them here.
            if count >= 65525:
                raw[52:64] = bytes(12); raw[82:90] = b'FAT12   '
            struct.pack_into('<I', raw, 28, 0xffffffff)
            requests.append(volume(raw))
        self.assertEqual([r['bits'] for r in run(requests)], [12, 16, 32])

    def test_short_and_overlong_boot_views(self):
        raw, _ = boot(2847)
        requests = [volume(raw[:n], 1474560) for n in (0, 1, 10, 35, 36, 63, 127, 510, 511)]
        for row in run(requests):
            self.assertEqual((row['status'], row['issues'], row['usable']), (0, TRUNCATED, False))
        self.assertEqual(run([volume(raw+b'x'), volume(raw+bytes(4097))]), [{'status': 7}, {'status': 7}])
        wide, _ = boot(2847, 4096)
        row = run([volume(wide[:512], 2**64-1)])[0]
        self.assertEqual(row['issues'], TRUNCATED); self.assertFalse(row['usable'])

    def test_invalid_common_geometry_and_insufficient_capacity(self):
        baseline, e = boot(2847)
        cases = []
        for offset, width, value, issue in ((11, 2, 0, SECTOR), (11, 2, 8192, SECTOR),
                (13, 1, 0, CLUSTER), (13, 1, 3, CLUSTER), (13, 1, 255, CLUSTER),
                (14, 2, 0, REGIONS), (16, 1, 0, REGIONS), (510, 2, 0, SIGNATURE),
                (19, 2, 0, COUNTERS), (17, 2, 17, TYPE_SHAPE)):
            raw = bytearray(baseline); raw[offset:offset+width] = value.to_bytes(width, 'little')
            cases.append((volume(raw, 2**64-1), issue))
        for row, (_, issue) in zip(run([x[0] for x in cases]), cases):
            self.assertFalse(row['usable']); self.assertTrue(row['issues'] & issue)
        row = run([volume(baseline, e['total']*512-1)])[0]
        self.assertEqual(row['issues'], CAPACITY)

    def test_counter_and_type_shape_conflicts(self):
        cases = []
        raw, _ = boot(2847); struct.pack_into('<I', raw, 32, 2880); cases.append((raw, COUNTERS))
        raw, _ = boot(2847); struct.pack_into('<H', raw, 17, 0); cases.append((raw, TYPE_SHAPE))
        raw, _ = boot(2847); struct.pack_into('<I', raw, 36, 9); struct.pack_into('<H', raw, 22, 0)
        cases.append((raw, TYPE_SHAPE))
        raw, _ = boot(65525); struct.pack_into('<H', raw, 22, 512); cases.append((raw, TYPE_SHAPE))
        raw, _ = boot(65525); struct.pack_into('<H', raw, 17, 16); cases.append((raw, TYPE_SHAPE))
        for row, (_, issue) in zip(run([volume(raw, 2**64-1) for raw, _ in cases]), cases):
            self.assertFalse(row['usable']); self.assertTrue(row['issues'] & issue)

    def test_regions_and_table_capacity_use_wide_arithmetic(self):
        baseline, _ = boot(65525)
        raw = bytearray(baseline); raw[16] = 255; struct.pack_into('<I', raw, 36, 0xffffffff)
        result = run([volume(raw, 2**64-1)])[0]
        self.assertEqual(result['issues'], REGIONS); self.assertEqual(result['bits'], 0)
        self.assertEqual(int(result['fat_bytes']), 0xffffffff*512)
        raw = bytearray(baseline); struct.pack_into('<I', raw, 36, 1)
        result = run([volume(raw)])[0]; self.assertTrue(result['issues'] & TABLE_SIZE)
        for count in (0, 268435446):
            raw = bytearray(baseline); struct.pack_into('<I', raw, 32, 32+2*512+count)
            result = run([volume(raw)])[0]; self.assertFalse(result['usable'])
            self.assertTrue(result['issues'] & (REGIONS | TYPE_SHAPE))

    def test_fat32_extended_features_and_auxiliary_references(self):
        baseline, _ = boot(65525)
        cases = []
        for offset, width, value, issue in ((40, 2, 0x10, FLAGS), (40, 2, 0x100, FLAGS),
                (40, 2, 0x82, FLAGS), (42, 2, 1, VERSION), (44, 4, 1, ROOT),
                (44, 4, 65527, ROOT), (44, 4, 0x10000002, ROOT), (48, 2, 0, AUXILIARY),
                (48, 2, 32, AUXILIARY), (50, 2, 32, AUXILIARY), (50, 2, 1, AUXILIARY),
                (52, 1, 1, RESERVED), (63, 1, 1, RESERVED)):
            raw = bytearray(baseline); raw[offset:offset+width] = value.to_bytes(width, 'little')
            cases.append((raw, issue))
        for row, (_, issue) in zip(run([volume(raw) for raw, _ in cases]), cases):
            self.assertFalse(row['usable']); self.assertEqual(row['issues'], issue)
        positives = []
        for flags in (0, 15, 0x80, 0x81):
            raw = bytearray(baseline); struct.pack_into('<H', raw, 40, flags); positives.append(volume(raw))
        for row, flags in zip(run(positives), (0, 15, 0x80, 0x81)):
            self.assertTrue(row['usable']); self.assertEqual(row['flags'], flags)
            self.assertEqual(row['mirrored'], flags < 128)
        raw = bytearray(baseline); struct.pack_into('<HH', raw, 48, 0xffff, 0xffff)
        self.assertTrue(run([volume(raw)])[0]['usable'])

    def test_random_geometry_oracle(self):
        rng = random.Random(0xFA712); requests, expected = [], []
        for _ in range(256):
            count = rng.choice((rng.randrange(1, 4085), rng.randrange(4085, 65525), rng.randrange(65525, 500000)))
            unit = rng.choice((512, 1024, 2048, 4096)); per = 2**rng.randrange(8)
            raw, values = boot(count, unit, per, copies=rng.randrange(1, 5), trailing=rng.randrange(per))
            requests.append(volume(raw)); expected.append(values)
        for row, values in zip(run(requests), expected):
            self.assertTrue(row['usable']); self.assertEqual(row['cluster_count'], values['clusters'])
            self.assertEqual(int(row['volume_bytes']), values['total']*values['unit'])
            self.assertEqual(row['data_sectors'], values['clusters']*values['per_cluster']+values['trailing'])

    def test_all_entry_marker_classes_and_high_nibble(self):
        requests, expected = [], []
        for bits, clusters in COUNTS.items():
            mask = MASKS[bits]
            for value, kind in ((0, 2), (1, 4), (2, 3), (clusters+1, 3), (clusters+2, 4),
                                (mask-9, 4), (mask-8, 5), (mask-7, 6), (mask, 6)):
                for index in (2, 3):
                    raw_value = value | (0xa0000000 if bits == 32 else 0)
                    data = packed(bits, {index: raw_value})
                    requests.append(entry(bits, index, data)); expected.append((value, kind))
        for row, (value, kind) in zip(run(requests), expected):
            self.assertEqual((row['status'], row['value'], row['kind']), (0, value, kind))
            if row['raw'] > 0xffff:
                self.assertEqual(row['raw'] & 0xf0000000, 0xa0000000)

    def test_reserved_header_entries_are_not_chain_data(self):
        for bits in COUNTS:
            data = packed(bits, {0: MASKS[bits], 1: MASKS[bits]})
            for row in run([entry(bits, i, data) for i in (0, 1)]):
                self.assertEqual(row['kind'], 1)

    def test_conflicting_fat_copies_remain_explicit_observations(self):
        for bits in COUNTS:
            left = packed(bits, {2: 3, 3: MASKS[bits]})
            right = packed(bits, {2: 4, 4: MASKS[bits]})
            rows = run([chain(bits, left), chain(bits, right)])
            self.assertEqual([r['prefix'] for r in rows], [[2, 3], [2, 4]])
            self.assertEqual([r['disposition'] for r in rows], [1, 1])

    def test_packed_neighbors_and_cross_sector_cell(self):
        mapping = {n: (n*37) & 0xfff for n in range(400)}
        data = packed(12, mapping)
        for row, index in zip(run([entry(12, n, data) for n in range(2, 400)]), range(2, 400)):
            self.assertEqual(row['value'], mapping[index])
        # Odd FAT12 index341 starts at byte511 and requires byte512 too.
        data = packed(12, {340: 0xabc, 341: 0xfff})
        self.assertEqual(run([entry(12, 341, data)])[0]['value'], 0xfff)
        self.assertEqual(run([entry(12, 341, data[:512])])[0], {'status': 7})

    def test_entry_shape_index_and_truncation_errors_preserve_output(self):
        for bits in COUNTS:
            data = packed(bits, {2: MASKS[bits]})
            for row in run([entry(bits, 2, data[:n]) for n in range(len(data))]):
                self.assertEqual(row, {'status': 7})
            self.assertEqual(run([entry(bits, COUNTS[bits]+2, data)])[0], {'status': 7})
            wrong = entry(bits, 2, data); wrong['clusters'] = '0'
            self.assertEqual(run([wrong])[0], {'status': 1})
        for bits, count in ((12, 4085), (16, 4084), (32, 65524), (32, 268435446)):
            self.assertEqual(run([entry(bits, 2, b'', count)])[0], {'status': 1})
        self.assertEqual(run([entry(32, 268435446, b'', 268435445)])[0], {'status': 7})

    def test_chain_terminal_and_start_dispositions(self):
        for bits in COUNTS:
            for value, disposition in ((MASKS[bits], 1), (0, 2), (MASKS[bits]-8, 3), (1, 4)):
                row = run([chain(bits, packed(bits, {2: 3, 3: value}))])[0]
                self.assertEqual(row['prefix'], [2, 3]); self.assertEqual(row['disposition'], disposition)
            for start, disposition in ((0, 0), (1, 5), (COUNTS[bits]+2, 5)):
                row = run([chain(bits, b'', start=start)])[0]
                self.assertEqual(row['prefix'], []); self.assertEqual(row['disposition'], disposition)
            row = run([chain(bits, packed(bits, {2: 3, 3: MASKS[bits]}), budget=1)])[0]
            self.assertEqual((row['prefix'], row['disposition'], row['stopped_cluster']), ([2], 8, 3))

    def test_chain_cycle_precedes_unseen_budget_and_truncation(self):
        for bits in COUNTS:
            for mapping, prefix, stopped in (({2: 2}, [2], 2), ({2: 3, 3: 2}, [2, 3], 2),
                                            ({2: 3, 3: 4, 4: 3}, [2, 3, 4], 3)):
                row = run([chain(bits, packed(bits, mapping), budget=len(prefix))])[0]
                self.assertEqual((row['prefix'], row['disposition'], row['stopped_cluster']), (prefix, 6, stopped))
            row = run([chain(bits, packed(bits, {2: 3}))])[0]
            self.assertEqual((row['prefix'], row['disposition']), ([2, 3], 7))

    def test_capacity_and_budget_errors(self):
        for request, status in ((chain(12, b'', budget=2, capacity=1), 3),
                                (chain(12, b'', budget=1, capacity=0), 3),
                                (chain(12, b'', budget=0), 1),
                                (chain(12, b'', budget=1025, capacity=1024), 1)):
            self.assertEqual(run([request])[0], {'status': status})
        values = {n: n+1 for n in range(2, 1026)}
        row = run([chain(12, packed(12, values), budget=1024)])[0]
        self.assertEqual(row['prefix'], list(range(2, 1026))); self.assertEqual(row['disposition'], 8)

    def test_random_chain_oracle(self):
        rng = random.Random(0xC1A17)
        requests, expected = [], []
        for _ in range(256):
            bits = rng.choice((12, 16, 32)); budget = rng.randrange(1, 33)
            mapping = {n: rng.choice((0, 1, MASKS[bits], MASKS[bits]-8, rng.randrange(2, 34))) for n in range(2, 34)}
            prefix, current = [], 2
            while True:
                if current in prefix: disposition = 6; break
                if len(prefix) == budget: disposition = 8; break
                prefix.append(current); value = mapping[current]
                if value == 0: disposition = 2; break
                if value == 1: disposition = 4; break
                if value == MASKS[bits]: disposition = 1; break
                if value == MASKS[bits]-8: disposition = 3; break
                current = value
            requests.append(chain(bits, packed(bits, mapping), budget=budget))
            expected.append((prefix, disposition, current))
        for row, e in zip(run(requests), expected):
            self.assertEqual((row['prefix'], row['disposition'], row['stopped_cluster']), e)


def main():
    global PROBE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(); PROBE = args.probe.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FatTests))
    if args.output:
        args.output.write_text(json.dumps(dict(tests_run=result.testsRun, passed=result.wasSuccessful(),
                                              cases=sum(r['cases'] for r in RECEIPTS), batches=RECEIPTS), indent=2)+'\n', encoding='utf-8')
    print(f'FAT supplied-byte cases executed: {sum(r["cases"] for r in RECEIPTS)}', flush=True)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__': main()
