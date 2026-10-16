"""Independent supplied-byte continuation oracle; no host storage access."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import struct
import subprocess
import unittest

PROBE = None
RECEIPTS = []
COUNTS = {12: 4084, 16: 65524, 32: 65525}
MASKS = {12: 0xfff, 16: 0xffff, 32: 0x0fffffff}


def pack(bits, mapping):
    width = 32 if bits == 32 else bits
    data = bytearray(((max(mapping, default=0)+1)*width+7)//8)
    for index, value in mapping.items():
        if bits != 12:
            struct.pack_into('<H' if bits == 16 else '<I', data, index*(width//8), value)
        else:
            bit = index*12
            for n in range(12):
                if value & (1 << n):
                    data[(bit+n)//8] |= 1 << ((bit+n) % 8)
    # An even FAT12 last entry still requires its exact two-byte cell.
    return bytes(data)


def oracle(bits, clusters, start, raw, page):
    current, steps, seen = start, [], set()
    mask = MASKS[bits]
    disposition = 0 if not start else (5 if start < 2 or start > clusters+1 else -1)
    while disposition == -1:
        cluster = current
        offset = cluster*bits//8
        size = 4 if bits == 32 else 2
        if offset+size > len(raw):
            steps.append([cluster, len(steps), False, 0, 0, 0])
            disposition = 7
            break
        stored = int.from_bytes(raw[offset:offset+size], 'little')
        link = (stored >> (4 if bits == 12 and cluster % 2 else 0)) & mask
        kind = 2 if link == 0 else 6 if link >= mask-7 else 5 if link == mask-8 else 3 if 2 <= link <= clusters+1 else 4
        steps.append([cluster, len(steps), True, stored, link, kind])
        seen.add(cluster)
        if kind == 3:
            current = link
            if link in seen:
                disposition = 6
        else:
            disposition = {6: 1, 2: 2, 5: 3, 4: 4}[kind]
    pages = []
    for begin in range(0, len(steps), page):
        end = min(begin+page, len(steps))
        running = end < len(steps)
        pages.append([end-begin, end, running, -1 if running else disposition,
                      steps[end-1][4] if running else current])
    return dict(status=0, steps=steps, pages=pages, count=len(steps), current=current,
                disposition=disposition)


def run(bits, mapping, page, start=2, clusters=None, truncate=None):
    clusters = COUNTS[bits] if clusters is None else clusters
    raw = pack(bits, mapping)
    if truncate is not None:
        raw = raw[:truncate]
    request = dict(bits=bits, clusters=clusters, start=start, fat=raw.hex(), page=page)
    data = json.dumps(request, separators=(',', ':')).encode()+b'\n'
    result = subprocess.run([str(PROBE)], input=data, capture_output=True, timeout=45)
    assert result.returncode == 0 and not result.stderr, result.stderr.decode(errors='replace')
    observed = json.loads(result.stdout)
    expected = oracle(bits, clusters, start, raw, page)
    assert observed == expected, (bits, page, start, observed, expected)
    assert len({s[0] for s in observed['steps']}) == observed['count']
    RECEIPTS.append(dict(bits=bits, clusters=clusters, start=start, page=page,
                         cells=observed['count'], disposition=observed['disposition'],
                         input_sha256=hashlib.sha256(data).hexdigest(),
                         output_sha256=hashlib.sha256(result.stdout).hexdigest()))
    return observed


class WalkTests(unittest.TestCase):
    def test_long_chains_and_partition_independence(self):
        for bits, length in ((12, 3000), (16, 33000), (32, 12000)):
            mapping = {i: i+1 for i in range(2, length+1)}
            mapping[length+1] = MASKS[bits]
            baseline = None
            for page in (1, 7, 1024, 4096, 70000):
                value = run(bits, mapping, page)
                self.assertEqual(length, value['count'])
                self.assertEqual(1, value['disposition'])
                if baseline is not None:
                    self.assertEqual(baseline, value['steps'])
                baseline = value['steps']

    def test_cycles_span_pages_without_duplicate_emission(self):
        for bits in (12, 16, 32):
            for length, target in ((1, 2), (1025, 2), (2050, 1700)):
                mapping = {i: i+1 for i in range(2, length+1)}
                mapping[length+1] = target
                for page in (1, 17, 1024):
                    value = run(bits, mapping, page)
                    self.assertEqual(6, value['disposition'])
                    self.assertEqual(length, value['count'])
                    self.assertEqual(target, value['current'])

    def test_markers_empty_invalid_and_high_bits(self):
        for bits in (12, 16, 32):
            mask = MASKS[bits]
            for marker in (0, 1, mask-8, *range(mask-7, mask+1)):
                raw = marker | (0xb0000000 if bits == 32 else 0)
                run(bits, {2: 3, 3: raw}, 1)
            for start in (0, 1, COUNTS[bits]+2, 0xffffffff):
                run(bits, {}, 1, start=start)

    def test_truncation_at_exact_cells(self):
        for bits in (12, 16, 32):
            mapping = {2: 3, 3: 4, 4: MASKS[bits]}
            raw = pack(bits, mapping)
            for length in range(len(raw)+1):
                run(bits, mapping, 2, truncate=length)

    def test_seeded_noncontiguous_chains(self):
        rng = random.Random(0xDE052)
        for bits in (12, 16, 32):
            for _ in range(10):
                nodes = rng.sample(range(2, min(COUNTS[bits]+2, 2000)), rng.randrange(2, 300))
                mapping = dict(zip(nodes, nodes[1:]))
                mapping[nodes[-1]] = MASKS[bits] if rng.randrange(2) else rng.choice(nodes)
                for page in (3, 65):
                    run(bits, mapping, page, start=nodes[0])


def main():
    global PROBE
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--probe', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); PROBE = args.probe.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(WalkTests))
    summary = dict(passed=result.wasSuccessful(), test_methods=result.testsRun, cases=len(RECEIPTS),
                   maximum_chain=max((r['cells'] for r in RECEIPTS), default=0), records=RECEIPTS,
                   scope='Supplied allocation cells only; no source/capture freshness or recursive extraction admission.')
    args.output.write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8', newline='\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
