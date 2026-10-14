"""Independent sparse exFAT images and exact region/source observation checks."""
import argparse
import copy
import hashlib
import json
import random
import struct
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'property'))
from test_exfat import boot, seal
from test_exfat_upcase import checksum, compress, literal, mapping
from exfat_directory_vectors import file_set, seal as seal_file_set

PROBE = None
RECEIPTS = []


class Volume:
    def __init__(self, copies=1, active=0, compressed=True, offset=0, shift=9,
                 cluster_shift=0, clusters=4096, fragmented=True):
        self.copies = copies
        self.active = active
        self.compressed = compressed
        self.offset = offset
        self.boot, self.length = boot(shift, cluster_shift, clusters, copies)
        struct.pack_into('<H', self.boot, 106, active)
        seal(self.boot)
        self.sector = 1 << shift
        self.size = self.sector << cluster_shift
        self.clusters = clusters
        self.fat = struct.unpack_from('<I', self.boot, 84)[0] * self.sector
        self.heap = struct.unpack_from('<I', self.boot, 88)[0] * self.sector
        self.root = [2, 9] if fragmented else [2]
        self.table = mapping()
        for n in range(128, 800):
            self.table[n] = (n + 977) % 65535
        self.upcase = compress(self.table) if compressed else literal(self.table)
        self.bitmap_length = (clusters + 7) // 8
        self.bitmap_chain = [3] + [20 + n * 2 for n in range((self.bitmap_length + self.size - 1) // self.size - 1)]
        self.upcase_chain = [100 + n * 2 for n in range((len(self.upcase) + self.size - 1) // self.size)]
        self.links = {}
        for chain in [self.root, self.bitmap_chain, self.upcase_chain]:
            for n, cluster in enumerate(chain):
                self.links[cluster] = chain[n + 1] if n + 1 < len(chain) else 0xffffffff
        self.bitmap = bytearray(self.bitmap_length)
        for cluster in self.root + self.bitmap_chain + self.upcase_chain + ([4] if copies == 2 else []):
            self.bitmap[(cluster - 2) // 8] |= 1 << ((cluster - 2) % 8)
        self.records = [bytes([1]) + bytes(31)] * (self.size // 32 - 1 if fragmented else 0)
        for identifier in range(copies):
            self.records.append(self.descriptor(0x81, self.bitmap_chain[0] if identifier == active else 4,
                                                self.bitmap_length, identifier))
        self.records.append(self.descriptor(0x82, self.upcase_chain[0], len(self.upcase), checksum(self.upcase)))
        self.end = True
        self.extra = {}

    @staticmethod
    def descriptor(kind, first, length, value=0):
        raw = bytearray(32)
        raw[0] = kind
        if kind == 0x81:
            raw[1] = value
        else:
            struct.pack_into('<I', raw, 4, value)
        struct.pack_into('<IQ', raw, 20, first, length)
        return bytes(raw)

    def cluster_offset(self, cluster):
        return self.heap + (cluster - 2) * self.size

    def regions(self):
        regions = {0: bytes(self.boot)}
        for copy_index in range(self.copies):
            table = bytearray(self.fat)
            for cluster, value in self.links.items():
                struct.pack_into('<I', table, cluster * 4, value if copy_index == self.active else cluster)
            regions[24 * self.sector + copy_index * self.fat] = bytes(table)
        root_bytes = b''.join(self.records) + (bytes(32) if self.end else b'')
        for index, cluster in enumerate(self.root):
            start = index * self.size
            regions[self.cluster_offset(cluster)] = root_bytes[start:start + self.size].ljust(self.size, b'\x01')
        for chain, payload in [(self.bitmap_chain, self.bitmap), (self.upcase_chain, self.upcase)]:
            for index, cluster in enumerate(chain):
                regions[self.cluster_offset(cluster)] = bytes(payload[index * self.size:(index + 1) * self.size])
        regions.update(self.extra)
        return {self.offset + at: value for at, value in regions.items()}

    def request(self):
        return dict(epoch='7', source_bytes=str(self.offset + self.length), offset=str(self.offset),
                    length=str(self.length), compressed=self.compressed,
                    regions=[dict(offset=str(at), hex=value.hex()) for at, value in sorted(self.regions().items())])

    def replace_descriptor(self, kind, **changes):
        index = next(n for n, raw in enumerate(self.records) if raw[0] == kind)
        raw = bytearray(self.records[index])
        for key, value in changes.items():
            if key == 'identifier':
                raw[1] = value
            elif key == 'first':
                struct.pack_into('<I', raw, 20, value)
            elif key == 'length':
                struct.pack_into('<Q', raw, 24, value)
            elif key == 'checksum':
                struct.pack_into('<I', raw, 4, value)
        self.records[index] = bytes(raw)


def source_bytes(row, offset, size):
    data = bytearray(size)
    for region in row['regions']:
        start = int(region['offset'])
        raw = bytes.fromhex(region['hex'])
        a, b = max(offset, start), min(offset + size, start + len(raw))
        if a < b:
            data[a - offset:b - offset] = raw[a - start:b - start]
    return bytes(data)


def run(rows):
    encoded = json.dumps(rows, separators=(',', ':')).encode()
    result = subprocess.run([str(PROBE)], input=encoded, capture_output=True, timeout=90)
    assert result.returncode == 0 and not result.stderr, (result.returncode, result.stderr)
    output = json.loads(result.stdout)
    assert len(output) == len(rows)
    RECEIPTS.append(dict(cases=len(rows), input_sha256='sha256:' + hashlib.sha256(encoded).hexdigest()))
    return output


class Tests(unittest.TestCase):
    def observation(self, row):
        out = run([row])[0]
        self.assertTrue(out['source_unchanged'])
        if row.get('guard'):
            expected = len(out['requests']) - (1 if row.get('fault', {}).get('mode') == 'null' else 0)
            self.assertEqual(str(expected), out['protected_views'])
        for read in out['requests']:
            start, size = int(read['offset']), int(read['bytes'])
            self.assertGreater(size, 0)
            self.assertGreaterEqual(start, int(row['offset']))
            self.assertLessEqual(start + size, int(row['offset']) + int(row['length']))
        if 'observation' in out:
            obs = out['observation']
            self.assertEqual('root-and-active-system-metadata', obs['applicability_scope'])
            self.assertFalse(obs['atomic_snapshot'])
            self.assertFalse(obs['current_source_authority'])
            self.assertEqual(len(out['requests']), int(obs['read_requests']))
            self.assertEqual(sum(int(r['bytes']) for r in out['requests']), int(obs['read_bytes']))
            if not obs['complete']:
                self.assertFalse(obs['applicable'])
            for region in obs['regions']:
                raw = source_bytes(row, int(region['source_offset']), int(region['bytes']))
                self.assertEqual('sha256:' + hashlib.sha256(raw).hexdigest(), region['sha256'])
            self.assertLessEqual(len(json.dumps(obs, separators=(',', ':'), ensure_ascii=False).encode()),
                                 int(row.get('limits', {}).get('output_bytes', 1048576)))
        return out

    def good(self, volume):
        row = volume.request()
        observed = self.observation(row)
        out = observed['observation']
        self.assertTrue(out['complete'], out)
        self.assertTrue(out['applicable'], out)
        self.assertTrue(out['cardinality_valid'])
        self.assertTrue(out['system_membership'])
        self.assertTrue(out['reread_equal'])
        self.assertEqual(str(volume.active), out['boot']['active_fat'])
        self.assertEqual(list(map(str, volume.root)), out['root_chain']['clusters'])
        self.assertEqual(list(map(str, volume.bitmap_chain)), out['bitmap_chain']['clusters'])
        self.assertEqual(list(map(str, volume.upcase_chain)), out['upcase_chain']['clusters'])
        count = sum((volume.bitmap[n // 8] >> (n % 8)) & 1 for n in range(volume.clusters))
        self.assertEqual(str(count), out['bitmap']['unavailable'])
        self.assertEqual(str(volume.clusters - count), out['bitmap']['available'])
        self.assertEqual('sha256:' + hashlib.sha256(struct.pack('<65536H', *volume.table)).hexdigest(),
                         out['upcase']['mapping_sha256'])
        self.assertEqual('sha256:' + hashlib.sha256(volume.upcase).hexdigest(), out['upcase']['sha256'])
        expected_records = list(volume.records) + ([bytes(32)] if volume.end else [])
        if not volume.end:
            expected_records += [b'\x01' * 32] * (len(volume.root) * volume.size // 32 - len(expected_records))
        self.assertEqual([r.hex() for r in expected_records], [r['raw'] for r in out['root_records']])
        for index, record in enumerate(out['root_records']):
            cluster = volume.root[index // (volume.size // 32)]
            offset = volume.offset + volume.cluster_offset(cluster) + (index % (volume.size // 32)) * 32
            self.assertEqual(str(offset), record['source_offset'])
        # Every observed region is reread in the same order, including overlaps.
        half = len(out['regions'])
        self.assertEqual(self.last_requests(row), observed['requests'])
        self.assertEqual(out['regions'], [dict(source_offset=r['offset'], bytes=r['bytes'],
                         sha256='sha256:' + hashlib.sha256(source_bytes(row, int(r['offset']), int(r['bytes']))).hexdigest())
                         for r in self.last_requests(row)[:half]])
        return out

    def last_requests(self, row):
        # Used only for independent trace assertions; no fresh native launch.
        # Derive the exact read order from geometry and declared chains.
        volume_start = int(row['offset'])
        raw = source_bytes(row, volume_start, 512)
        unit = 1 << raw[108]
        cluster_bytes = unit << raw[109]
        heap = struct.unpack_from('<I', raw, 88)[0] * unit
        active = struct.unpack_from('<H', raw, 106)[0] & 1
        fat = struct.unpack_from('<I', raw, 80)[0] * unit + active * struct.unpack_from('<I', raw, 84)[0] * unit
        reads = [dict(offset=str(volume_start), bytes='512'), dict(offset=str(volume_start), bytes=str(unit * 12))]
        def chain(first):
            result = []
            while True:
                result.append(first)
                at = volume_start + fat + first * 4
                reads.append(dict(offset=str(at), bytes='4'))
                first = struct.unpack('<I', source_bytes(row, at, 4))[0]
                if first == 0xffffffff:
                    return result
        root = chain(struct.unpack_from('<I', raw, 96)[0])
        records = []
        end = False
        for cluster in root:
            for at in range(0, cluster_bytes, 8192):
                offset = volume_start + heap + (cluster - 2) * cluster_bytes + at
                size = min(8192, cluster_bytes - at)
                reads.append(dict(offset=str(offset), bytes=str(size)))
                data = source_bytes(row, offset, size)
                for n in range(0, len(data), 32):
                    records.append(data[n:n + 32])
                    if not data[n]:
                        end = True
                        break
                if end:
                    break
            if end:
                break
        bitmap = next(r for r in records if r[0] == 0x81 and r[1] & 1 == active)
        upcase = next(r for r in records if r[0] == 0x82)
        chains = [chain(struct.unpack_from('<I', r, 20)[0]) for r in [bitmap, upcase]]
        for record, clusters in zip([bitmap, upcase], chains):
            remaining = struct.unpack_from('<Q', record, 24)[0]
            for cluster in clusters:
                size = min(remaining, cluster_bytes)
                for at in range(0, size, 8192):
                    reads.append(dict(offset=str(volume_start + heap + (cluster - 2) * cluster_bytes + at),
                                      bytes=str(min(8192, size - at))))
                remaining -= size
        return reads + copy.deepcopy(reads)

    def bad(self, volume, code):
        out = self.observation(volume.request())['observation']
        self.assertFalse(out['applicable'])
        self.assertEqual([code], out['diagnostics'])
        return out

    def test_profiles_active_pairing_fragmentation_and_original_values(self):
        for copies, active in [(1, 0), (2, 0), (2, 1)]:
            for compressed in [True, False]:
                self.good(Volume(copies, active, compressed, offset=12345))
        for shift, cluster_shift in [(10, 0), (11, 1), (12, 2), (9, 5)]:
            self.good(Volume(shift=shift, cluster_shift=cluster_shift))
        v = Volume(clusters=65536)
        self.good(v)
        v = Volume(clusters=4099)
        v.bitmap[-1] |= 0xf8
        self.good(v)
        v = Volume(fragmented=False)
        v.end = False
        self.good(v)

    def test_root_cardinality_critical_entries_and_partial_sets(self):
        for kind in [0x81, 0x82]:
            v = Volume()
            v.records = [r for r in v.records if r[0] != kind]
            self.bad(v, 'exfat_root_cardinality')
            v = Volume()
            v.records.append(next(r for r in v.records if r[0] == kind))
            self.bad(v, 'exfat_bitmap_descriptor' if kind == 0x81 else 'exfat_upcase_descriptor')
        v = Volume(copies=2, active=1)
        v.replace_descriptor(0x81, identifier=1)
        self.bad(v, 'exfat_bitmap_descriptor')
        for kind, code in [(0x80, 'exfat_critical_root_entry'), (0x84, 'exfat_critical_root_entry'),
                           (0xc0, 'exfat_orphan_secondary'), (0xe4, 'exfat_orphan_secondary'),
                           (0x85, 'exfat_root_file_set')]:
            v = Volume()
            v.records.append(bytes([kind]) + bytes(31))
            self.bad(v, code)
        v = Volume()
        v.records.append(b'\xa4' + bytes(31))
        self.good(v)
        v = Volume()
        v.records.extend([b'\x83' + bytes(31)] * 2)
        self.bad(v, 'exfat_label_descriptor')
        v = Volume()
        v.records.append(b'\x83\x0c' + bytes(30))
        self.bad(v, 'exfat_label_descriptor')

    def test_boot_and_all_system_chain_failures(self):
        v = Volume()
        v.boot[11] = 1
        seal(v.boot)
        self.bad(v, 'exfat_boot_invalid')
        v = Volume()
        v.boot[-1] ^= 1
        self.bad(v, 'exfat_boot_invalid')
        for first in [2, 3, 100]:
            for value in [0, 1, 0xfffffff7, 0xfffffffe, 4098]:
                v = Volume()
                v.links[first] = value
                self.bad(v, 'exfat_chain_marker')
            v = Volume()
            v.links[first] = first
            self.bad(v, 'exfat_chain_cycle')
        v = Volume()
        v.replace_descriptor(0x82, first=3)
        self.bad(v, 'exfat_chain_crosslink')
        v = Volume()
        v.links[3] = 2
        self.bad(v, 'exfat_chain_crosslink')
        v = Volume()
        v.links[3] = 7
        v.links[7] = 0xffffffff
        self.bad(v, 'exfat_chain_length')
        v = Volume()
        v.links[100] = 0xffffffff
        self.bad(v, 'exfat_chain_length')
        for kind in [0x81, 0x82]:
            for first in [0, 1, 4098]:
                v = Volume()
                v.replace_descriptor(kind, first=first)
                self.bad(v, 'exfat_bitmap_descriptor' if kind == 0x81 else 'exfat_upcase_descriptor')

    def test_bitmap_membership_upcase_validation_and_representation(self):
        for cluster in [2, 9, 3, 100]:
            v = Volume()
            v.bitmap[(cluster - 2) // 8] &= ~(1 << ((cluster - 2) % 8))
            self.bad(v, 'exfat_system_cluster_available')
        v = Volume()
        v.replace_descriptor(0x82, checksum=checksum(v.upcase) ^ 1)
        self.bad(v, 'exfat_upcase_mapping')
        v = Volume()
        v.upcase = compress([0] * 65536)
        v.upcase_chain = [100 + n * 2 for n in range((len(v.upcase) + v.size - 1) // v.size)]
        for n, cluster in enumerate(v.upcase_chain):
            v.links[cluster] = v.upcase_chain[n + 1] if n + 1 < len(v.upcase_chain) else 0xffffffff
            v.bitmap[(cluster - 2) // 8] |= 1 << ((cluster - 2) % 8)
        v.replace_descriptor(0x82, length=len(v.upcase), checksum=checksum(v.upcase))
        self.bad(v, 'exfat_upcase_mapping')
        v = Volume()
        v.compressed = False
        self.bad(v, 'exfat_upcase_representation')

    def test_request_limits_invalid_calls_and_reader_failures(self):
        v = Volume()
        for name, value, code in [('read_requests', 1, 'exfat_read_budget'), ('read_bytes', 512, 'exfat_read_budget'),
                                  ('clusters', 1, 'exfat_chain_budget'), ('records', 1, 'exfat_record_budget'),
                                  ('retained_bytes', 1, 'exfat_retained_budget')]:
            row = v.request()
            row['limits'] = {name: str(value)}
            out = self.observation(row)['observation']
            self.assertEqual([code], out['diagnostics'])
        for name in ['read_requests', 'read_bytes', 'clusters', 'records', 'retained_bytes']:
            row = v.request()
            row['limits'] = {name: '0'}
            out = self.observation(row)
            self.assertEqual('exfat_capture_limits', out['refusal'])
            self.assertEqual([], out['requests'])
        for key, value in [('epoch', '0'), ('source_bytes', '0'), ('offset', str((1 << 64) - 1)),
                           ('length', str((1 << 64) - 1)), ('source_id', '')]:
            row = v.request()
            row[key] = value
            out = self.observation(row)
            self.assertIn('refusal', out)
            self.assertEqual([], out['requests'])
        for mode, code in [('short', 'exfat_read_length'), ('oversized', 'exfat_read_length'),
                           ('null', 'exfat_read_length'), ('throw', 'exfat_reader_failure')]:
            for call in [1, 2, 5]:
                row = v.request()
                row['fault'] = dict(mode=mode, call=str(call))
                self.assertEqual([code], self.observation(row)['observation']['diagnostics'])
        row = v.request()
        row['fault'] = dict(mode='no_reader', call='0')
        out = self.observation(row)
        self.assertEqual('exfat_reader_required', out['refusal'])
        self.assertEqual([], out['requests'])

    def test_overlap_and_final_reread_withdraw_applicability(self):
        v = Volume()
        trace = self.last_requests(v.request())
        for call in [2, len(trace) // 2 + 1, len(trace)]:
            row = v.request()
            row['fault'] = dict(mode='change', call=str(call))
            out = self.observation(row)['observation']
            self.assertFalse(out['applicable'])
            self.assertFalse(out['reread_equal'])
            self.assertEqual(['exfat_source_changed'], out['diagnostics'])
        row = v.request()
        row['limits'] = dict(read_requests=str(len(trace) - 1))
        out = self.observation(row)['observation']
        self.assertFalse(out['applicable'])
        self.assertEqual(['exfat_read_budget'], out['diagnostics'])

    def test_high_offsets_large_root_chunks_and_cross_cluster_file_sets(self):
        v = Volume()
        v.offset = (1 << 64) - 1 - v.length
        self.good(v)
        v = Volume(offset=987654, shift=12, cluster_shift=3)
        self.good(v)
        for name_length in [1, 15, 16, 255]:
            v = Volume()
            original = list(v.records)
            records = file_set([65] * name_length, cluster=800, length=512)
            count = len(records) // 32
            v.root = [2, 9, 13] if count > 16 else [2, 9]
            for index, cluster in enumerate(v.root):
                v.links[cluster] = v.root[index + 1] if index + 1 < len(v.root) else 0xffffffff
                v.bitmap[(cluster - 2) // 8] |= 1 << ((cluster - 2) % 8)
            # The primary occupies the last slot of the first cluster.
            v.records = original[:15] + [bytes(records[n:n + 32]) for n in range(0, len(records), 32)] + original[15:]
            self.good(v)
            bad = copy.deepcopy(v)
            corrupted = bytearray(records)
            corrupted[32] = 0xc1
            seal_file_set(corrupted)
            bad.records[15:15 + count] = [bytes(corrupted[n:n + 32]) for n in range(0, len(corrupted), 32)]
            self.bad(bad, 'exfat_root_file_set')

    def test_exhausted_output_and_retained_limits_preserve_partial_scope(self):
        v = Volume(compressed=False)
        for value in [16384, 32768, 65536]:
            row = v.request()
            row['limits'] = dict(output_bytes=str(value))
            out = self.observation(row)['observation']
            self.assertFalse(out['applicable'])
            self.assertEqual(['exfat_output_budget'], out['diagnostics'])
        row = v.request()
        row['limits'] = dict(retained_bytes='400000')
        out = self.observation(row)['observation']
        self.assertFalse(out['applicable'])
        self.assertEqual(['exfat_retained_budget'], out['diagnostics'])
        for key, value in [('output_bytes', 16383), ('output_bytes', 1048577),
                           ('read_requests', 8193), ('read_bytes', 2097153),
                           ('clusters', 4097), ('records', 4097), ('retained_bytes', 1048577)]:
            row = v.request()
            row['limits'] = {key: str(value)}
            out = self.observation(row)
            self.assertEqual('exfat_capture_limits', out['refusal'])
            self.assertEqual([], out['requests'])

    def test_native_protected_read_only_reader_views(self):
        for compressed in [True, False]:
            v = Volume(copies=2, active=1, compressed=compressed)
            row = v.request()
            row['guard'] = True
            out = self.observation(row)['observation']
            self.assertTrue(out['applicable'])
            self.assertEqual('sha256:' + hashlib.sha256(struct.pack('<65536H', *v.table)).hexdigest(),
                             out['upcase']['mapping_sha256'])
        for mode in ['short', 'oversized', 'null']:
            row = Volume().request()
            row.update(guard=True, fault=dict(mode=mode, call='2'))
            self.assertEqual(['exfat_read_length'], self.observation(row)['observation']['diagnostics'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    PROBE = args.probe
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    args.output.write_text(json.dumps(dict(passed=result.wasSuccessful(), methods=result.testsRun,
                           cases=sum(r['cases'] for r in RECEIPTS), receipts=RECEIPTS), indent=2) + '\n', encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
