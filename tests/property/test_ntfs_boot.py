"""Independent supplied-byte NTFS boot/seed geometry oracles; no volume opening."""
import argparse
import hashlib
import json
import random
import struct
import subprocess
from pathlib import Path

U64 = (1 << 64) - 1
I = dict(truncated=1, oem=2, sector=4, cluster=8, bpb=16, record=32, index=64,
         size=128, address=256, capacity=512, overflow=1024, version=2048,
         unsupported=4096, marker=8192, checksum=16384, length=32768)


def boot(sector=512, cluster=8, record=246, index=244, sectors=8191, mft=4, mirror=8):
    raw = bytearray(sector)
    raw[:3] = b'\xeb\x52\x90'
    raw[3:11] = b'NTFS    '
    struct.pack_into('<H', raw, 11, sector)
    raw[13] = cluster
    raw[21] = 0xf8
    struct.pack_into('<HHI', raw, 24, 63, 255, 0xfedcba98)
    struct.pack_into('<QQQ', raw, 40, sectors, mft, mirror)
    raw[64], raw[68] = record, index
    struct.pack_into('<Q', raw, 72, U64)
    raw[510:512] = b'\x55\xaa'
    return raw


def is_power(value):
    return value > 0 and value.bit_count() == 1


def size_from_code(code, cluster):
    signed = int.from_bytes(bytes([code]), 'little', signed=True)
    if signed > 0 and is_power(signed):
        return True, signed * cluster if cluster else None
    if signed < 0 and 9 <= -signed <= 31:
        return True, 2 ** -signed
    return False, None


def oracle(raw, available, major=3, minor=1):
    if len(raw) > 4096:
        return dict(status=7, result_unchanged=True)
    issues = 0 if (major, minor) in ((3, 0), (3, 1)) else I['version']
    if len(raw) < 512:
        return dict(status=0, issues=issues | I['truncated'], fields_present=False,
                    geometry_valid=False, bootstrap_usable=False)
    sector = struct.unpack_from('<H', raw, 11)[0]
    cluster_code, record_code, index_code = raw[13], raw[64], raw[68]
    field, mft, mirror = struct.unpack_from('<QQQ', raw, 40)
    serial = struct.unpack_from('<Q', raw, 72)[0]
    checksum = struct.unpack_from('<I', raw, 80)[0]
    calculated = sum(struct.unpack_from('<20I', raw)) % (1 << 32)
    marker = struct.unpack_from('<H', raw, 510)[0]
    sector_known = sector in (512, 1024, 2048, 4096)
    if raw[3:11] != b'NTFS    ':
        issues |= I['oem']
    if not sector_known:
        issues |= I['sector']
    elif len(raw) != sector:
        issues |= I['length']
        if len(raw) < sector:
            issues |= I['truncated']
    if any(raw[pos] for pos in (*range(14, 21), 22, 23, *range(32, 36))):
        issues |= I['bpb']
    if marker != 0xaa55:
        issues |= I['marker']
    if checksum and checksum != calculated:
        issues |= I['checksum']
    if 1 <= cluster_code <= 128 and is_power(cluster_code):
        spc = cluster_code
    elif 244 <= cluster_code <= 255:
        spc = 2 ** (256 - cluster_code)
    else:
        spc = 0
        issues |= I['cluster']
    cluster = spc * sector if sector_known else 0
    if cluster > 2097152:
        issues |= I['unsupported']
    record_shape, record_size = size_from_code(record_code, cluster)
    index_shape, index_size = size_from_code(index_code, cluster)
    if not record_shape:
        issues |= I['record']
    if not index_shape:
        issues |= I['index']
    supported = record_size is not None and record_size <= 49152
    if record_size is not None and not supported:
        issues |= I['unsupported']
    clusters = field // spc if spc else 0
    if not field or spc and not clusters:
        issues |= I['size']
    data = field * sector if sector_known else None
    media = data + sector if data is not None and data <= U64 else None
    geometry_overflow = data is not None and data > U64 or media is not None and media > U64
    if geometry_overflow:
        issues |= I['overflow']
    data_known = data is not None and data <= U64
    media_known = media is not None and media <= U64
    if media_known and media > available:
        issues |= I['capacity']
    offsets = [0, 0]
    known = [False, False]
    addresses = False
    if cluster and record_size is not None and data_known:
        mathematical = [mft * cluster, mirror * cluster]
        known = [value <= U64 for value in mathematical]
        offsets = [value if valid else 0 for value, valid in zip(mathematical, known)]
        if not all(known):
            issues |= I['overflow']
        elif any(value + record_size > U64 for value in offsets):
            issues |= I['overflow']
        else:
            ranges = [(value, value + record_size) for value in offsets]
            addresses = (mft < clusters and mirror < clusters and
                         all(start >= sector and end <= data for start, end in ranges) and
                         (ranges[0][1] <= ranges[1][0] or ranges[1][1] <= ranges[0][0]))
        if not addresses:
            issues |= I['address']
    fatal_geometry = sum(I[name] for name in ('truncated', 'oem', 'sector', 'cluster', 'bpb',
                                               'size', 'capacity', 'version', 'length'))
    geometry = 0 < cluster <= 2097152 and not geometry_overflow and not issues & fatal_geometry
    return dict(status=0, issues=issues, fields_present=True,
                bytes_per_sector=sector, cluster_code=cluster_code, record_code=record_code,
                index_code=index_code, sectors_per_cluster=spc, cluster_bytes=cluster,
                record_bytes=record_size or 0, index_bytes=index_size or 0,
                sector_field=str(field), mft_lcn=str(mft), mirror_lcn=str(mirror), serial=str(serial),
                checksum=checksum, calculated_checksum=calculated, marker=marker,
                hidden_sectors=struct.unpack_from('<I', raw, 28)[0],
                sectors_per_track=struct.unpack_from('<H', raw, 24)[0],
                heads=struct.unpack_from('<H', raw, 26)[0], media_type=raw[21],
                data_bytes=str(data if data_known else 0), media_span_bytes=str(media if media_known else 0),
                clusters=str(clusters), mft0_offset=str(offsets[0]), mirror0_offset=str(offsets[1]),
                complete_sector=sector_known and len(raw) == sector, data_bound_known=data_known,
                media_span_known=media_known, record_size_known=record_size is not None,
                index_size_known=index_size is not None, record_budget_supported=supported,
                mft0_offset_known=known[0], mirror0_offset_known=known[1], seed_addresses_valid=bool(addresses),
                checksum_present=checksum != 0, checksum_matches=bool(checksum and checksum == calculated),
                geometry_valid=bool(geometry), bootstrap_usable=bool(geometry and supported and addresses))


def vectors():
    def row(name, raw, available=4194304, major=3, minor=1):
        return name, dict(hex=bytes(raw).hex(), available=str(available), major=str(major), minor=str(minor))
    for sector in (512, 1024, 2048, 4096):
        for cluster in (1, 2, 4, 8, 16, 32, 64, 128, *range(244, 256)):
            spc = cluster if cluster <= 128 else 2 ** (256 - cluster)
            sectors = max(8191, spc * 128 - 1)
            raw = boot(sector, cluster, sectors=sectors)
            yield row(f'geometry-{sector}-{cluster}', raw, (sectors + 1) * sector)
    for key in (13, 64, 68):
        for code in range(256):
            raw = boot()
            raw[key] = code
            yield row(f'encoding-{key}-{code}', raw)
    base = boot()
    for size in range(512):
        yield row(f'prefix-{size}', base[:size])
    for sector in (512, 1024, 2048, 4096):
        raw = boot(sector)
        for size in (512, sector - 1, sector, min(4096, sector + 1), 4097):
            yield row(f'view-{sector}-{size}', (raw + bytes(4097))[:size])
    for pos in (*range(14, 21), 22, 23, *range(32, 36)):
        raw = boot()
        raw[pos] = 1
        yield row(f'required-zero-{pos}', raw)
    for value in (0, 1, 255, 256, 511, 513, 8192, 32768, 65535):
        raw = boot()
        struct.pack_into('<H', raw, 11, value)
        yield row(f'sector-{value}', raw)
    for sector in (512, 4096):
        for count in (0, 1, 7, 8, 9, U64 // sector - 1, U64 // sector, U64 // sector + 1, U64):
            raw = boot(sector, sectors=count)
            yield row(f'sector-field-{sector}-{count}', raw, U64)
    for lcn in (0, 1, 4, 8, 1023, 1024, U64 // 4096, U64 // 4096 + 1, U64):
        for offset in (48, 56):
            raw = boot()
            struct.pack_into('<Q', raw, offset, lcn)
            yield row(f'lcn-{offset}-{lcn}', raw, U64)
    for mft, mirror, code in ((1, 2, 4), (2, 1, 4), (1, 2, 1), (2, 1, 1), (1, 1, 1)):
        raw = boot(cluster=1, mft=mft, mirror=mirror, record=code)
        yield row(f'seed-overlap-{mft}-{mirror}-{code}', raw)
    yield row('record-crosses-data-bound', boot(mft=1022, record=2))
    yield row('record-exact-data-end', boot(cluster=1, sectors=9, mft=7, mirror=1, record=2))
    yield row('record-past-data-end', boot(cluster=1, sectors=9, mft=8, mirror=1, record=2))
    yield row('record-end-add-overflow', boot(sectors=U64 // 512 - 1, mft=U64 // 4096, record=225), U64)
    for count in (7, 8, 9, 15, 16, 17):
        yield row(f'partial-allocation-{count}', boot(sectors=count, mft=1, mirror=0))
    for available in (0, 4193792, 4194303, 4194304, 4194305, U64):
        yield row(f'available-{available}', boot(), available)
    for marker in (0, 0x55aa, 0xaa55, 65535):
        raw = boot()
        struct.pack_into('<H', raw, 510, marker)
        yield row(f'marker-{marker}', raw)
    for checksum in (0, 1, 0xffffffff, sum(struct.unpack_from('<20I', base)) % (1 << 32)):
        raw = boot()
        struct.pack_into('<I', raw, 80, checksum)
        yield row(f'checksum-{checksum}', raw)
    for major, minor in ((3, 0), (3, 1), (0, 0), (2, 1), (3, 2), (65535, 65535)):
        yield row(f'profile-{major}-{minor}', base, major=major, minor=minor)
    rng = random.Random(0x425042)
    for index in range(256):
        raw = boot(rng.choice((512, 1024, 2048, 4096)))
        for _ in range(rng.randrange(1, 6)):
            raw[rng.randrange(len(raw))] ^= rng.randrange(1, 256)
        yield row(f'generated-{index}', raw, rng.choice((0, 4194304, U64)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    cases, records = list(vectors()), []
    for start in range(0, len(cases), 32):
        batch = cases[start:start + 32]
        process = subprocess.run([args.probe], input=json.dumps([row for _, row in batch]).encode(),
                                 capture_output=True, timeout=30)
        assert process.returncode == 0, (start, process.returncode, process.stderr.decode(errors='replace'))
        actual = json.loads(process.stdout)
        assert len(actual) == len(batch)
        for (name, row), observed in zip(batch, actual):
            raw = bytes.fromhex(row['hex'])
            expected = oracle(raw, int(row['available']), int(row['major']), int(row['minor']))
            for key, value in expected.items():
                assert observed.get(key) == value, (name, key, value, observed.get(key))
            assert observed['input_unchanged'], name
            records.append(dict(case=name, input_sha256=hashlib.sha256(raw).hexdigest(),
                                status=observed['status'], issues=observed.get('issues'), passed=True))
    Path(args.output).write_text(json.dumps(dict(count=len(records), cases=records,
                                physical_devices=False, source_writes=False), indent=2) + '\n', encoding='utf-8', newline='\n')
    print(f'{len(records)} NTFS boot/seed cases passed; protected read-only bytes; no volume/provider claim')


if __name__ == '__main__':
    main()
