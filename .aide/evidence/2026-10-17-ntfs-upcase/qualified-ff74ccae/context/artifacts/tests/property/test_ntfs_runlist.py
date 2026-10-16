"""Independent canonical signed mapping-pair oracle; no source or content claim."""
import argparse
import hashlib
import json
import random
import subprocess
from pathlib import Path

U64 = (1 << 64) - 1
I = dict(truncated=1, width=2, length=4, overflow=8, range=16,
         coverage=32, sparse=64, budget=128)


def encoded(length, delta, length_width=None, offset_width=None):
    if length_width is None:
        length_width = max(1, (length.bit_length() + 1 + 7) // 8)
    left = length.to_bytes(length_width, 'little')
    if delta is None:
        return bytes([length_width]) + left
    if offset_width is None:
        offset_width = next(n for n in range(1, 9) if -(1 << (8*n-1)) <= delta < (1 << (8*n-1)))
    return bytes([length_width | offset_width << 4]) + left + delta.to_bytes(offset_width, 'little', signed=True)


def oracle(raw, first, count, volume, sparse=1, budget=4096):
    if volume == 0 or sparse not in (0, 1):
        return dict(init_status=1, cursor_unchanged=True)
    if len(raw) > 49152 or not 1 <= budget <= 4096:
        return dict(init_status=7, cursor_unchanged=True)
    if first + count > U64:
        return dict(init_status=2, cursor_unchanged=True)
    offset = seen = issues = 0
    current, previous, end = first, 0, first + count
    rows, terminated, stopped = [], False, False
    while True:
        row = dict(issues=0, length_width=0, offset_width=0, vcn=str(current),
                   next_vcn='0', length='0', lcn='0', lcn_end='0', present=False,
                   end_marker=False, sparse=False, negative_delta=False, valid=False)
        if offset == len(raw):
            row['issues'] = I['truncated']
        elif raw[offset] == 0:
            row['end_marker'] = terminated = True
            row['issues'] = 0 if current == end else I['coverage']
        elif seen == budget:
            row['issues'] = I['budget']
        else:
            lw, ow = raw[offset] & 15, raw[offset] >> 4
            row.update(present=True, length_width=lw, offset_width=ow)
            length_bytes = raw[offset+1:offset+1+lw]
            if not 1 <= lw <= 8 or ow > 8:
                row['issues'] = I['width']
            elif offset + 1 + lw + ow > len(raw):
                row['issues'] = I['truncated']
            else:
                length = int.from_bytes(length_bytes, 'little')
                row['length'] = str(length)
                if int.from_bytes(length_bytes, 'little', signed=True) <= 0:
                    row['issues'] = I['length']
                elif current + length > U64:
                    row['issues'] = I['overflow']
                else:
                    row['next_vcn'] = str(current + length)
                    if current + length > end:
                        row['issues'] = I['coverage']
                    else:
                        row['sparse'] = ow == 0
                        new_lcn = previous
                        if ow == 0:
                            if not sparse:
                                row['issues'] = I['sparse']
                        else:
                            delta = int.from_bytes(raw[offset+1+lw:offset+1+lw+ow], 'little', signed=True)
                            row['negative_delta'] = delta < 0
                            new_lcn = previous + delta
                            if new_lcn < 0:
                                row['issues'] = I['range']
                            elif new_lcn > U64:
                                row['issues'] = I['overflow']
                            else:
                                row['lcn'] = str(new_lcn)
                                if new_lcn + length > U64:
                                    row['issues'] = I['overflow']
                                else:
                                    row['lcn_end'] = str(new_lcn + length)
                                    if new_lcn + length > volume:
                                        row['issues'] = I['range']
                        if not row['issues']:
                            row['valid'] = True
                            offset += 1 + lw + ow
                            current += length
                            if ow:
                                previous = new_lcn
                            seen += 1
        rows.append(row)
        issues |= row['issues']
        if terminated:
            break
        if row['issues']:
            stopped = True
            break
    return dict(init_status=0, items=rows, count=seen, issues=issues, offset=offset,
                next_vcn=str(current), previous_lcn=str(previous), terminated=terminated, stopped=stopped)


def vectors():
    def row(name, raw, first=0, count=1, volume=10000, sparse=1, budget=4096):
        request = dict(op='runs', hex=bytes(raw).hex(), first=str(first), count=str(count),
                       volume=str(volume), sparse=str(sparse), budget=str(budget))
        return name, request
    yield row('mapped-zero', encoded(1, 0) + b'\0')
    yield row('zero-delta-retains-real-lcn', encoded(2, 100) + encoded(3, 0) + b'\0', count=5)
    yield row('backward', encoded(2, 200) + encoded(3, -128) + b'\0', count=5)
    yield row('sparse-preserves-lcn', encoded(1, 100) + encoded(2, None) + encoded(1, -90) + b'\0', count=4)
    yield row('sparse-first', encoded(1, None) + encoded(1, 0) + b'\0', count=2)
    yield row('sparse-forbidden', encoded(1, None) + b'\0', sparse=0)
    yield row('legacy-minus-one', encoded(1, -1) + b'\0')
    for lw in range(1, 9):
        for ow in range(1, 9):
            yield row(f'widths-{lw}-{ow}', encoded(17, 31, lw, ow) + b'\0', count=17)
    for length in (1, 127, 128, 255, 256, 65535, 65536, (1 << 63)-1):
        yield row(f'length-{length}', encoded(length, 0) + b'\0', count=length, volume=U64)
    for header in range(256):
        yield row(f'header-{header}', bytes([header]) + bytes(16) + b'\0')
    sample = encoded(128, 1234) + encoded(1, -1000) + b'\0'
    for size in range(len(sample) + 1):
        yield row(f'truncated-{size}', sample[:size], count=129)
    for raw in (b'\0', b'', b'\x11\x80\0\0', b'\x11\0\0\0', b'\x10\0'):
        yield row('special-' + raw.hex(), raw)
    for count in (0, 1, 2, 3):
        yield row(f'coverage-{count}', encoded(2, 0) + b'\0', count=count)
    yield row('empty', b'\0', count=0)
    yield row('padding-after-terminator', encoded(1, 0) + b'\0\xff\xff')
    for budget in (0, 1, 2, 4096, 4097):
        yield row(f'budget-{budget}', encoded(1, 0) + encoded(1, 1) + b'\0', count=2, budget=budget)
    for count in (0, 1, 2):
        yield row(f'vcn-bound-{count}', encoded(1, 0) + b'\0', first=U64-1, count=count, volume=U64)
    yield row('invalid-volume', b'\0', volume=0)
    yield row('invalid-sparse', b'\0', sparse=2)
    yield row('mapping-budget', bytes(49153))
    yield row('physical-end-overflow', encoded(1, (1 << 63)-1) * 2 + encoded(2, 0) + b'\0', count=4, volume=U64)
    yield row('vcn-next-overflow', encoded(2, 0) + b'\0', first=U64-1, count=1, volume=U64)
    yield row('lcn-add-overflow', encoded(1, (1 << 63)-1) * 3 + b'\0', count=3, volume=U64)
    yield row('negative-minimum', encoded(1, (1 << 63)-1) + encoded(1, 1) + encoded(1, -(1 << 63)) + b'\0', count=3, volume=U64)
    for volume in (1, 2, 9999, 10000):
        yield row(f'physical-bound-{volume}', encoded(2, 0) + b'\0', count=2, volume=volume)
    rng = random.Random(0x52554e)
    for case in range(256):
        parts, logical, previous = [], 0, 0
        for _ in range(rng.randrange(1, 9)):
            length = rng.randrange(1, 257)
            target = rng.randrange(1000)
            delta = None if rng.randrange(4) == 0 else target-previous
            parts.append(encoded(length, delta))
            if delta is not None:
                previous = target
            logical += length
        raw = b''.join(parts) + b'\0'
        if rng.randrange(2):
            raw = bytearray(raw)
            raw[rng.randrange(len(raw))] ^= rng.randrange(1, 256)
        yield row(f'generated-{case}', raw, count=logical)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    cases, records = list(vectors()), []
    for start in range(0, len(cases), 32):
        batch = cases[start:start+32]
        run = subprocess.run([args.probe], input=json.dumps([row for _, row in batch]).encode(), capture_output=True, timeout=30)
        assert run.returncode == 0, (start, run.returncode, run.stderr.decode(errors='replace'))
        actual = json.loads(run.stdout)
        assert len(actual) == len(batch)
        for (name, request), observed in zip(batch, actual):
            raw = bytes.fromhex(request['hex'])
            expected = oracle(raw, *(int(request[key]) for key in ('first', 'count', 'volume', 'sparse', 'budget')))
            for key, value in expected.items():
                assert observed.get(key) == value, (name, key, value, observed.get(key))
            assert observed['source_unchanged'], name
            records.append(dict(case=name, input_sha256=hashlib.sha256(raw).hexdigest(), passed=True,
                                init_status=observed['init_status'], issues=observed.get('issues')))
    Path(args.output).write_text(json.dumps(dict(count=len(records), cases=records, physical_devices=False), indent=2)+'\n', encoding='utf-8', newline='\n')
    print(f'{len(records)} canonical NTFS mapping cases passed; no source/content authority')


if __name__ == '__main__':
    main()
