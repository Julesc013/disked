"""Deterministic disposable partition images; no imported product implementation."""
import argparse
import copy
import hashlib
import json
import struct
import uuid
import zlib
from pathlib import Path

UNIT = 512
BLOCKS = 256
DISK = uuid.UUID('12345678-9abc-4def-8123-456789abcdef')
TYPE = uuid.UUID('ebd0a0a2-b9e5-4433-87c0-68b6b72699c7')


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def mbr_entry(kind, start, count, boot=0):
    return bytes([boot, 0, 2, 0, kind, 255, 255, 255]) + struct.pack('<II', start, count)


def table(entries):
    data = bytearray(512)
    for i, entry in enumerate(entries):
        data[446 + i*16:462 + i*16] = entry
    data[510:512] = b'\x55\xaa'
    return data


def header_crc(data, offset):
    size = struct.unpack_from('<I', data, offset+12)[0]
    assert 92 <= size <= 512
    struct.pack_into('<I', data, offset+16, 0)
    struct.pack_into('<I', data, offset+16, zlib.crc32(data[offset:offset+size]))


def array_crc(data, side):
    offset = (1 if side == 0 else BLOCKS-1)*512
    lba, count, size = struct.unpack_from('<QII', data, offset+72)
    struct.pack_into('<I', data, offset+88, zlib.crc32(data[lba*512:lba*512+count*size]))
    header_crc(data, offset)


def gpt():
    data = bytearray(BLOCKS*512)
    data[:512] = table([mbr_entry(0xee, 1, BLOCKS-1)])
    rows = bytearray(16384)
    for i, (first, last, name) in enumerate([(34, 60, 'Alpha'), (70, 90, 'Beta')]):
        off = i*128
        rows[off:off+16] = TYPE.bytes_le
        rows[off+16:off+32] = uuid.UUID(int=i+1).bytes_le
        struct.pack_into('<QQQ', rows, off+32, first, last, 0)
        text = name.encode('utf-16-le')
        rows[off+56:off+56+len(text)] = text
    for my, alt, array_lba in [(1, BLOCKS-1, 2), (BLOCKS-1, 1, BLOCKS-33)]:
        data[array_lba*512:array_lba*512+len(rows)] = rows
        struct.pack_into('<8sIIIIQQQQ16sQIII', data, my*512, b'EFI PART', 0x10000,
                         92, 0, 0, my, alt, 34, BLOCKS-34, DISK.bytes_le,
                         array_lba, 128, 128, zlib.crc32(rows))
        header_crc(data, my*512)
    return data


def recipes():
    out = []
    def add(name, family, data, checks, note, common=False):
        out.append(dict(name=name, family=family, data=bytes(data), blocks=BLOCKS,
                        unit=UNIT, checks=copy.deepcopy(checks), note=note,
                        common_projection=common))
    def mbr_case(name, entries, checks, note, common=False):
        data = bytearray(BLOCKS*512); data[:512] = table(entries)
        add(name, 'mbr', data, checks, note, common)
    mbr_case('mbr-empty', [], {'mbr.issues': 0}, 'Empty signed table', True)
    mbr_case('mbr-two', [mbr_entry(7, 1, 31), mbr_entry(0x83, 40, 60)],
             {'mbr.issues': 0}, 'Two nonoverlapping primary extents', True)
    mbr_case('mbr-overlap', [mbr_entry(7, 1, 40), mbr_entry(0x83, 40, 60)],
             {'mbr.issues': 16}, 'Overlapping primary extents')
    mbr_case('mbr-outside', [mbr_entry(7, 250, 10)], {'mbr.issues': 8}, 'Outside source')
    mbr_case('mbr-zero-type', [mbr_entry(0, 1, 10)], {'mbr.issues': 4}, 'Inactive metadata retained')
    mbr_case('mbr-boot-byte', [mbr_entry(7, 1, 10, 3)], {'mbr.issues': 2}, 'Invalid boot indicator')
    data = bytearray(BLOCKS*512); data[:512] = table([mbr_entry(7, 1, 10)])
    data[511] = 0
    add('mbr-signature', 'mbr', data, {'mbr.issues': 1}, 'Invalid signature prevents entry interpretation')
    add('mbr-truncated', 'mbr', data[:511], {'mbr.issues': 256}, 'Incomplete logical block')
    chain = bytearray(BLOCKS*512); chain[:512] = table([mbr_entry(15, 10, 200)])
    chain[10*512:11*512] = table([mbr_entry(7, 1, 9), mbr_entry(15, 30, 170)])
    chain[40*512:41*512] = table([mbr_entry(0x83, 1, 19)])
    add('ebr-two', 'mbr', chain, {'mbr.issues': 0, 'walks.0.issues': 0, 'walks.0.complete': True},
        'Logical start relative to current EBR; link relative to original container', True)
    data = bytearray(chain); data[40*512:41*512] = table([mbr_entry(0x83, 1, 19), mbr_entry(15, 0, 200)])
    add('ebr-cycle', 'mbr', data, {'walks.0.issues': 1024, 'walks.0.complete': False}, 'Cycle ends with incomplete coverage')
    data = bytearray(chain); data[10*512:11*512] = table([mbr_entry(7, 1, 50), mbr_entry(15, 30, 170)])
    add('ebr-overlap', 'mbr', data, {'walks.0.issues': 4112}, 'Logical data overlaps later data and EBR metadata')
    data = bytearray(chain); data[40*512+511] = 0
    add('ebr-signature', 'mbr', data, {'walks.0.issues': 1, 'walks.0.complete': False}, 'Bad downstream signature')
    add('ebr-unavailable', 'mbr', chain[:40*512], {'walks.0.issues': 8192, 'walks.0.complete': False}, 'Missing requested EBR')
    add('gpt-valid', 'gpt', gpt(), {'comparison': 1, 'copies.0.candidate.issues': 0,
                                  'copies.1.candidate.issues': 0}, 'Independent complete candidates agree', True)
    for side in (0, 1):
        h = (1 if side == 0 else BLOCKS-1)*512
        a = (2 if side == 0 else BLOCKS-33)*512
        for kind in ['header-crc', 'array-crc', 'reserved', 'range', 'duplicate', 'overlap', 'utf16', 'attributes']:
            data = gpt(); checks = {'comparison': 0}; note = kind
            if kind == 'header-crc':
                data[h+16] ^= 1; checks[f'copies.{side}.header.issues'] = 16
            elif kind == 'array-crc':
                data[a+56] ^= 1; checks[f'copies.{side}.candidate.issues'] = 1024
            elif kind == 'reserved':
                data[h+200] = 1; checks[f'copies.{side}.header.issues'] = 32
            else:
                flag = {'range': 2048, 'duplicate': 8192, 'overlap': 4096, 'utf16': 32768, 'attributes': 32}[kind]
                if kind == 'range': struct.pack_into('<Q', data, a+40, 300)
                if kind == 'duplicate': data[a+144:a+160] = data[a+16:a+32]
                if kind == 'overlap': struct.pack_into('<Q', data, a+128+32, 60)
                if kind == 'utf16': struct.pack_into('<H', data, a+56, 0xd800)
                if kind == 'attributes': struct.pack_into('<Q', data, a+48, 8)
                array_crc(data, side); checks[f'copies.{side}.candidate.issues'] = flag
            add('gpt-'+str(side)+'-'+kind, 'gpt', data, checks, note+'; other copy remains independently observed')
    data = gpt(); offset = (BLOCKS-33)*512
    struct.pack_into('<Q', data, offset+32, 35); array_crc(data, 1)
    add('gpt-valid-disagreement', 'gpt', data, {'comparison': 2, 'copies.0.candidate.issues': 0,
        'copies.1.candidate.issues': 0}, 'Both valid; distinct start remains unresolved')
    data = gpt(); data[(BLOCKS-1)*512+56] ^= 1; header_crc(data, (BLOCKS-1)*512)
    add('gpt-guid-disagreement', 'gpt', data, {'comparison': 2}, 'Distinct valid disk GUIDs remain unresolved')
    data = gpt(); data[512+16] ^= 1; data[(BLOCKS-1)*512+16] ^= 1
    add('gpt-both-crc', 'gpt', data, {'comparison': 0, 'copies.0.header.issues': 16,
        'copies.1.header.issues': 16}, 'Neither copy trusted')
    data = gpt(); data[512:520] = b'NOT GPT!'
    add('gpt-primary-signature', 'gpt', data, {'comparison': 0, 'copies.0.header.issues': 2},
        'Primary absence must not suppress backup interpretation')
    add('gpt-short-backup', 'gpt', gpt()[:-1], {'comparison': 0, 'copies.1.header.issues': 1},
        'Truncated backup is incomplete despite valid primary')
    return out


def generate(output):
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=False)
    manifest = []
    for item in recipes():
        data = item.pop('data'); sha = digest(data)
        path = output/(sha.removeprefix('sha256:')+'.img')
        if not path.exists(): path.write_bytes(data)
        manifest.append(dict(item, file=path.name, bytes=len(data), sha256=sha))
    result = dict(schema='org.disked.partition-corpus/1', generator_sha256=digest(Path(__file__).read_bytes()), cases=manifest)
    (output/'manifest.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True)
    args = parser.parse_args(); print(json.dumps(generate(args.output), indent=2))
