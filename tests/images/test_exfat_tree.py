"""Independent sparse-image allocation and logical-content tree oracles."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import unittest
from test_exfat_capture import Volume, source_bytes
from exfat_directory_vectors import file_set, seal
from test_exfat_upcase import namehash

parser = argparse.ArgumentParser()
parser.add_argument('--probe', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args, remaining = parser.parse_known_args()
receipts = []
case_count = 0

def name(text):
    raw = text.encode('utf-16-le')
    return list(struct.unpack('<' + 'H' * (len(raw) // 2), raw))

def entry(volume, text, first=0, length=0, valid=None, directory=False, contiguous=False):
    units = name(text)
    raw = file_set(units, cluster=first, length=length, valid_length=length if valid is None else valid)
    struct.pack_into('<H', raw, 4, 16 if directory else 0)
    raw[33] = 3 if contiguous else 1
    struct.pack_into('<H', raw, 36, namehash(volume.table, units))
    return bytes(seal(raw))

def allocate(volume, clusters):
    for i, cluster in enumerate(clusters):
        volume.bitmap[(cluster - 2) // 8] |= 1 << ((cluster - 2) % 8)
        volume.links[cluster] = clusters[i + 1] if i + 1 < len(clusters) else 0xffffffff

def fat_address(volume, cluster):
    # FatOffset and FatLength are distinct boot fields. Volume.fat is bytes
    # per FAT; it is not the FAT's start offset.
    start = struct.unpack_from('<I', volume.boot, 80)[0] * volume.sector
    return volume.offset + start + volume.active * volume.fat + cluster * 4

def fixture(*, contiguous=False, copies=1, active=0, offset=0, valid=515):
    volume = Volume(copies=copies, active=active, offset=offset, fragmented=False)
    if copies == 2:
        volume.links[4] = 0xffffffff
    directories = [1000, 1001] if contiguous else [1000, 1003]
    data = [1100, 1101] if contiguous else [1100, 1105]
    allocate(volume, directories)
    allocate(volume, data)
    volume.records.append(entry(volume, 'folder', directories[0], volume.size * 2,
        directory=True, contiguous=contiguous))
    volume.records.append(entry(volume, 'empty'))
    volume.records.append(entry(volume, 'emptydir', directory=True))
    # Put a file set across the directory's physical cluster boundary.
    prefix = bytes([1]) + bytes(31)
    child = prefix * (volume.size // 32 - 1)
    child += entry(volume, 'alpha', data[0], 700, valid=valid, contiguous=contiguous)
    child += bytes(32)
    payload = bytes(i % 251 for i in range(700))
    row = volume.request()
    for i, cluster in enumerate(directories):
        piece = child[i * volume.size:(i + 1) * volume.size].ljust(volume.size, b'\0')
        row['regions'].append(dict(offset=str(volume.offset + volume.cluster_offset(cluster)), hex=piece.hex()))
    for i, cluster in enumerate(data):
        piece = payload[i * volume.size:(i + 1) * volume.size].ljust(volume.size, b'\xee')
        row['regions'].append(dict(offset=str(volume.offset + volume.cluster_offset(cluster)), hex=piece.hex()))
    return volume, row, directories, data, payload[:valid] + bytes(700 - valid)

def run(rows):
    global case_count
    before = copy.deepcopy(rows)
    data = json.dumps(rows, separators=(',', ':')).encode()
    result = subprocess.run([str(args.probe.resolve())], input=data, capture_output=True, timeout=100)
    assert result.returncode == 0 and not result.stderr, (result.returncode, result.stderr.decode(errors='replace'))
    values = json.loads(result.stdout)
    assert rows == before and len(values) == len(rows)
    case_count += len(rows)
    receipts.append(dict(cases=len(rows), input_sha256=hashlib.sha256(data).hexdigest(),
        output_sha256=hashlib.sha256(result.stdout).hexdigest()))
    return values

class Tree(unittest.TestCase):
    def observe(self, row):
        value = run([row])[0]
        self.assertNotIn('error', value, value)
        tree = value['observation']
        self.assertTrue(value['source_unchanged'])
        self.assertFalse(tree['authorizes_effects'])
        self.assertEqual(len(value['requests']), int(tree['read_requests']))
        self.assertEqual(sum(int(r['bytes']) for r in value['requests']), int(tree['read_bytes']))
        for read in value['requests']:
            self.assertGreater(int(read['bytes']), 0)
            self.assertGreaterEqual(int(read['offset']), int(row['offset']))
            self.assertLessEqual(int(read['offset']) + int(read['bytes']), int(row['offset']) + int(row['length']))
        return value, tree

    def test_nested_fragmented_and_contiguous_content(self):
        for contiguous in [False, True]:
            for copies, active in [(1, 0), (2, 0), (2, 1)]:
                volume, row, dirs, clusters, expected = fixture(contiguous=contiguous, copies=copies, active=active, offset=65536)
                value, tree = self.observe(row)
                self.assertTrue(tree['complete'], tree['diagnostics'])
                self.assertTrue(tree['reread_equal'])
                self.assertEqual(3, len(tree['directories']))
                alpha = next(e for e in tree['entries'] if e['entry']['original_units'] == list(map(str, name('alpha'))))
                self.assertEqual(list(map(str, clusters)), alpha['clusters'])
                self.assertEqual(expected.hex(), alpha['content_hex'])
                self.assertEqual('sha256:' + hashlib.sha256(expected).hexdigest(), alpha['content_sha256'])
                self.assertEqual('185', alpha['defined_zero_bytes'])
                physical = volume.offset + volume.cluster_offset(clusters[1])
                self.assertFalse(any(int(r['offset']) >= physical + 3 and int(r['offset']) < physical + volume.size for r in value['requests']))
                child = next(d for d in tree['directories'] if d['id'] == '1')['namespace']
                first = child['entries'][0]['source_record_offset']
                self.assertEqual(str(volume.offset + volume.cluster_offset(dirs[0]) + volume.size - 32), first)

    def test_valid_data_length_boundaries_and_empty_streams(self):
        for valid in [0, 1, 511, 512, 513, 699, 700]:
            volume, row, _, _, expected = fixture(valid=valid)
            _, tree = self.observe(row)
            self.assertTrue(tree['complete'], tree['diagnostics'])
            alpha = next(e for e in tree['entries'] if e.get('content_hex') == expected.hex() and e['entry']['name_length'] == '5')
            self.assertEqual(str(valid), alpha['source_data_bytes'])
            self.assertEqual(str(700 - valid), alpha['defined_zero_bytes'])
            empty = next(e for e in tree['entries'] if e['entry']['original_units'] == list(map(str, name('empty'))))
            self.assertEqual('', empty['content_hex'])
            empty_dir = next(d for d in tree['directories'] if d['id'] == '2')
            self.assertEqual([], empty_dir['namespace']['entries'])

    def test_contiguous_streams_ignore_fat_cells(self):
        volume, row, dirs, files, _ = fixture(contiguous=True)
        addresses = [fat_address(volume, c) for c in dirs + files]
        for address in addresses:
            row['regions'].append(dict(offset=str(address), hex='f7ffffff'))
        value, tree = self.observe(row)
        self.assertTrue(tree['complete'], tree['diagnostics'])
        self.assertTrue(all(not any(int(r['offset']) <= p < int(r['offset']) + int(r['bytes']) for r in value['requests']) for p in addresses))

    def test_chain_corruption_bitmap_and_crosslinks(self):
        volume, base, dirs, files, _ = fixture()
        variants = []
        for cluster, value in [(files[0], 0xffffffff), (files[1], 1200), (files[1], files[0]), (files[0], 0xfffffff7), (dirs[0], 2)]:
            row = copy.deepcopy(base)
            row['regions'].append(dict(offset=str(fat_address(volume, cluster)), hex=struct.pack('<I', value).hex()))
            variants.append(row)
        row = copy.deepcopy(base)
        bitmap = bytearray(volume.bitmap)
        bitmap[(files[0] - 2) // 8] &= ~(1 << ((files[0] - 2) % 8))
        row['regions'].append(dict(offset=str(volume.cluster_offset(3)), hex=bitmap.hex()))
        variants.append(row)
        for row in variants:
            _, tree = self.observe(row)
            self.assertFalse(tree['complete'])
            self.assertTrue(tree['diagnostics'])

    def test_source_change_failed_read_and_callback_withdrawal(self):
        _, baseline, _, _, _ = fixture()
        value, tree = self.observe(baseline)
        self.assertTrue(tree['complete'])
        for mode in ['throw', 'short', 'oversized', 'null', 'change']:
            row = copy.deepcopy(baseline)
            row['fault'] = dict(mode=mode, call=str(len(value['requests'])))
            _, tree = self.observe(row)
            self.assertFalse(tree['complete'])
        row = copy.deepcopy(baseline)
        row['applicable'] = False
        value, tree = self.observe(row)
        self.assertFalse(tree['complete'])
        self.assertEqual([], value['requests'])
        row = copy.deepcopy(baseline)
        row['withdraw_after_reads'] = '12'
        _, tree = self.observe(row)
        self.assertFalse(tree['complete'])

    def test_resource_limits_remain_partial(self):
        _, baseline, _, _, _ = fixture()
        for field, value in [('directories', 1), ('depth', 1), ('clusters', 4), ('records', 4),
            ('read_requests', 3), ('read_bytes', 512), ('retained_bytes', 64), ('content_bytes', 10)]:
            row = copy.deepcopy(baseline)
            row['tree_limits'] = {field: str(value)}
            _, tree = self.observe(row)
            # Depth one supports this one-level tree; everything else clips it.
            self.assertEqual(field == 'depth', tree['complete'], (field, tree))

    def test_ambiguous_names_and_unsupported_records_remain_observations(self):
        volume = Volume(fragmented=False)
        volume.records += [entry(volume, 'same'), entry(volume, 'SAME')]
        _, tree = self.observe(volume.request())
        self.assertFalse(tree['complete'])
        self.assertIn('exfat_tree_name_collision', tree['diagnostics'])
        self.assertEqual(2, len(tree['entries']))
        volume, row, dirs, _, _ = fixture()
        row['regions'].append(dict(offset=str(volume.cluster_offset(dirs[0])),
            hex=(bytes([0xc0]) + bytes(31)).hex()))
        _, tree = self.observe(row)
        self.assertFalse(tree['complete'])
        self.assertIn('exfat_tree_namespace_incomplete', tree['diagnostics'])

    def test_partial_directory_keeps_observed_record_prefix(self):
        _, row, _, _, _ = fixture()
        row['tree_limits'] = {'records': '18'}
        _, tree = self.observe(row)
        self.assertFalse(tree['complete'])
        self.assertIsNotNone(tree['partial_directory'])
        self.assertFalse(tree['partial_directory']['complete'])
        self.assertGreater(len(tree['partial_directory']['records']), 0)

    def test_protected_borrowed_views_and_root_snapshot_parity(self):
        _, row, _, _, _ = fixture()
        row['guard'] = True
        row['root_parity'] = True
        value, tree = self.observe(row)
        self.assertTrue(tree['complete'], tree)
        self.assertEqual(str(len(value['requests'])), value['protected_views'])
        self.assertEqual(value['legacy_root'], tree['root'])
        self.assertEqual(value['legacy_root_requests'], value['requests'][:len(value['legacy_root_requests'])])

if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tree))
    args.output.write_text(json.dumps(dict(passed=result.wasSuccessful(), methods=result.testsRun,
        cases=case_count, receipts=receipts), indent=2) + '\n', encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
