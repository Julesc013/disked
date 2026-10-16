"""Independent generated NTFS FILE-envelope/fixup oracle; no volume or I/O claim."""
import argparse
import hashlib
import json
import random
import struct
import subprocess
from pathlib import Path

LIMIT = 49152
ISS = dict(truncated=1, length=2, signature=4, version=8, offset=16,
           count=32, torn=64, header=128)


def record(size=1024, offset=48, flags=3):
    logical = bytearray((i * 53 + i // 7) & 255 for i in range(size))
    count = size // 512 + 1
    attribute = (offset + count * 2 + 7) // 8 * 8
    logical[:4] = b'FILE'
    struct.pack_into('<HHQHHHHIIQH', logical, 4, offset, count,
                     (1 << 64) - 1, 65535, 7, attribute, flags,
                     size, size, 0xfedcba9876543210, 65535)
    struct.pack_into('<I', logical, attribute, 0xffffffff)
    # Protect each stride independently; expected restoration comes from these
    # original logical bytes rather than any observation produced by C.
    raw = bytearray(logical)
    saved = [bytes(logical[i - 2:i]) for i in range(512, size + 1, 512)]
    struct.pack_into('<H', raw, offset, 0x73a1)
    for i, tail in enumerate(saved):
        raw[offset + 2 + i * 2:offset + 4 + i * 2] = tail
        raw[(i + 1) * 512 - 2:(i + 1) * 512] = b'\xa1\x73'
    restored = bytearray(raw)
    for i, tail in enumerate(saved):
        restored[(i + 1) * 512 - 2:(i + 1) * 512] = tail
    return raw, restored


def oracle(raw, major=3, minor=1, alias='none', capacity=None):
    size = len(raw)
    if size > LIMIT:
        return dict(status=7, observe_unchanged=True, restore_status=7)
    issues = 0 if major == 3 and minor in (0, 1) else ISS['version']
    if size < 512 or size % 512:
        issues |= ISS['length']
    result = dict(status=0, fields_present=size >= 42, fixups_valid=False,
                  envelope_valid=False, mismatched_tails=0)
    if size < 42:
        issues |= ISS['truncated']
    else:
        offset, count, lsn, sequence, links, attribute, flags, used, allocated, base, next_id = struct.unpack_from('<HHQHHHHIIQH', raw, 4)
        result.update(usa_offset=offset, usa_count=count, log_sequence=str(lsn),
                      sequence=sequence, links=links, attribute_offset=attribute,
                      flags=flags, used_bytes=used, allocated_bytes=allocated,
                      in_use=bool(flags & 1), name_index_present=bool(flags & 2),
                      base_reference=str(base), next_attribute_id=next_id,
                      strides=size // 512)
        if raw[:4] != b'FILE':
            issues |= ISS['signature']
        if count != size // 512 + 1 or count == 0:
            issues |= ISS['count']
        # Entries fit the first stride, excluding its protected final word.
        if count > 255 or offset < 42 or offset % 2 or offset + count * 2 > min(510, size):
            issues |= ISS['offset']
        if allocated != size or used > allocated or attribute < 42 or attribute % 8 or attribute + 4 > used or offset + (count * 2 if count <= 255 else 0) > attribute:
            issues |= ISS['header']
        if not issues & (ISS['length'] | ISS['offset'] | ISS['count']):
            usn = struct.unpack_from('<H', raw, offset)[0]
            tails = [struct.unpack_from('<H', raw, i - 2)[0] for i in range(512, size + 1, 512)]
            mismatches = sum(word != usn for word in tails)
            result.update(update_sequence=usn, mismatched_tails=mismatches,
                          fixups_valid=mismatches == 0)
            if mismatches:
                issues |= ISS['torn']
    result.update(issues=issues, envelope_valid=issues == 0)
    if issues:
        result['restore_status'] = 1
    elif capacity is not None and capacity < size:
        result['restore_status'] = 3
    elif alias != 'none':
        result['restore_status'] = 1
    else:
        restored = bytearray(raw)
        for i in range(1, size // 512 + 1):
            restored[i * 512 - 2:i * 512] = raw[offset + i * 2:offset + i * 2 + 2]
        result.update(restore_status=0, restored_hex=restored.hex(),
                      output_tail_unchanged=True)
    return result


def vectors():
    def row(name, raw, **controls):
        request = dict(hex=bytes(raw).hex(), major='3', minor='1')
        request.update(controls)
        return name, request
    for size in (512, 1024, 4096, LIMIT):
        for offset in (42, 48):
            for minor in ('0', '1'):
                raw, expected = record(size, offset)
                assert bytes.fromhex(oracle(raw)['restored_hex']) == expected
                yield row(f'valid-{size}-{offset}-{minor}', raw, minor=minor)
    for flags in (0, 1, 2, 3, 4, 8, 0x8000, 65535):
        yield row(f'raw-flags-{flags}', record(flags=flags)[0])
    for offset in (502, 504):  # Ends at508 and510, including first protected tail.
        yield row(f'array-boundary-{offset}', record(offset=offset)[0])
    raw, _ = record()
    for size in range(512):
        yield row(f'truncation-{size}', raw[:size])
    for size in (513, 1023, 1025, 4095, LIMIT - 1, LIMIT + 1):
        yield row(f'length-{size}', (raw * (size // len(raw) + 1))[:size])
    fields = {
        4: ('H', (0, 40, 41, 43, 49, 506, 508, 510, 511, 512, 65534)),
        6: ('H', (0, 1, 2, 4, 255, 256, 65535)),
        20: ('H', (0, 40, 48, 54, 55, 57, 1021, 1024, 65535)),
        24: ('I', (0, 56, 59, 60, 1025, 0xffffffff)),
        28: ('I', (0, 512, 1023, 1025, 0xffffffff)),
    }
    for offset, (encoding, values) in fields.items():
        for value in values:
            altered = bytearray(raw)
            struct.pack_into('<' + encoding, altered, offset, value)
            yield row(f'header-{offset}-{value}', altered)
    for signature in (b'BAAD', b'INDX', b'\x00' * 4):
        altered = bytearray(raw)
        altered[:4] = signature
        yield row('signature-' + signature.hex(), altered)
    for major, minor in ((0, 0), (2, 1), (3, 2), (4, 0), (65535, 65535)):
        yield row(f'profile-{major}-{minor}', raw, major=str(major), minor=str(minor))
    largest, _ = record(LIMIT)
    for index in range(96):
        altered = bytearray(largest)
        altered[(index + 1) * 512 - 2] ^= 1
        yield row(f'torn-stride-{index}', altered)
    altered = bytearray(largest)
    for tail in range(510, LIMIT, 512):
        altered[tail] ^= 1
    yield row('all-tails-torn', altered)
    for size in (512, 1024, LIMIT):
        raw, _ = record(size)
        for alias in ('same', 'forward', 'backward'):
            yield row(f'overlap-{size}-{alias}', raw, alias=alias)
        for cap in (0, size - 1, size, size + 16):
            yield row(f'capacity-{size}-{cap}', raw, capacity=str(cap))
    rng = random.Random(0x4e544653)
    for index in range(256):
        altered = bytearray(record(rng.choice((512, 1024, 4096)))[0])
        for _ in range(rng.randrange(1, 7)):
            altered[rng.randrange(len(altered))] ^= rng.randrange(1, 256)
        yield row(f'generated-{index}', altered)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    cases = list(vectors())
    records = []
    # Bound each process input; the probe enforces an independent8MiB ceiling.
    for start in range(0, len(cases), 32):
        batch = cases[start:start + 32]
        payload = json.dumps([item for _, item in batch]).encode()
        run = subprocess.run([args.probe], input=payload, capture_output=True, timeout=30)
        if run.returncode:
            raise AssertionError((start, run.returncode, run.stderr.decode(errors='replace')))
        actual = json.loads(run.stdout)
        assert len(actual) == len(batch)
        for (name, request), observed in zip(batch, actual):
            raw = bytes.fromhex(request['hex'])
            expected = oracle(raw, int(request['major']), int(request['minor']),
                              request.get('alias', 'none'),
                              int(request['capacity']) if 'capacity' in request else None)
            for key, value in expected.items():
                assert observed.get(key) == value, (name, key, value, observed.get(key))
            assert observed['input_unchanged'], name
            if observed['restore_status']:
                assert observed['output_unchanged'], name
                assert observed['restore_observation_unchanged'], name
            records.append(dict(case=name, input_sha256=hashlib.sha256(raw).hexdigest(),
                                status=observed['status'], issues=observed.get('issues'),
                                restore_status=observed['restore_status'], passed=True))
    Path(args.output).write_text(json.dumps(dict(cases=records, count=len(records),
                                physical_devices=False, source_writes=False), indent=2) + '\n', encoding='utf-8')
    print(f'{len(records)} supplied-byte NTFS record cases passed; guard-page/read-only input; no volume/provider claim')


if __name__ == '__main__':
    main()
