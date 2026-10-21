"""Four small, deterministic Windows-reference fixtures; no product code/imports.

Only supplied bytes are generated. No device, file, mount or Windows API access.
The original 128 KiB differential corpus remains unchanged.
"""
import hashlib
import struct
import uuid
import zlib

UNIT = 512
BLOCKS = 8192
CASES = ('mbr-valid', 'gpt-valid', 'gpt-primary-damaged', 'gpt-conflicting')
DISK = uuid.UUID('bf17b16e-05de-4fe1-8a8b-df0242754900')
TYPE = uuid.UUID('ebd0a0a2-b9e5-4433-87c0-68b6b72699c7')


def mbr_entry(kind, start, count):
    return bytes((0, 0, 2, 0, kind, 255, 255, 255)) + struct.pack('<II', start, count)


def header(my, other, array_lba, rows):
    body = bytearray(UNIT)
    struct.pack_into('<8sIIIIQQQQ16sQIII', body, 0, b'EFI PART', 0x10000, 92, 0,
                     0, my, other, 34, BLOCKS-34, DISK.bytes_le, array_lba,
                     128, 128, zlib.crc32(rows))
    struct.pack_into('<I', body, 16, zlib.crc32(body[:92]))
    return body


def generate(name):
    if name not in CASES:
        raise ValueError('Unknown Windows reference fixture')
    data = bytearray(BLOCKS*UNIT)
    struct.pack_into('<I', data, 440, 0xD15CED01 if name == 'mbr-valid' else 0xD15CED02)
    data[510:512] = b'\x55\xaa'
    if name == 'mbr-valid':
        for slot, kind, first in ((0, 7, 2048), (1, 0x83, 4096)):
            data[446+slot*16:462+slot*16] = mbr_entry(kind, first, 1024)
        return bytes(data)
    data[446:462] = mbr_entry(0xee, 1, BLOCKS-1)
    for side in (0, 1):
        rows = bytearray(128*128)
        for slot, first, last, text in ((0, 2048, 3071, 'Alpha'), (1, 4096, 5119, 'Beta')):
            offset = slot*128
            rows[offset:offset+16] = TYPE.bytes_le
            rows[offset+16:offset+32] = uuid.UUID(int=slot+1).bytes_le
            start = first + (1 if name == 'gpt-conflicting' and side == 1 and slot == 0 else 0)
            struct.pack_into('<QQQ', rows, offset+32, start, last, 0)
            encoded = text.encode('utf-16-le')
            rows[offset+56:offset+56+len(encoded)] = encoded
        my, other, array_lba = (1, BLOCKS-1, 2) if side == 0 else (BLOCKS-1, 1, BLOCKS-33)
        data[array_lba*UNIT:array_lba*UNIT+len(rows)] = rows
        data[my*UNIT:(my+1)*UNIT] = header(my, other, array_lba, rows)
    if name == 'gpt-primary-damaged':
        data[UNIT+16] ^= 1  # Deliberately bad primary header CRC; backup untouched.
    return bytes(data)


def describe(name):
    body = generate(name)
    return dict(name=name, bytes=len(body), unit=UNIT, blocks=BLOCKS,
                sha256='sha256:'+hashlib.sha256(body).hexdigest(),
                family='mbr' if name == 'mbr-valid' else 'gpt',
                primary_first=2048, backup_first=None if name == 'mbr-valid' else 2049 if name == 'gpt-conflicting' else 2048,
                primary_header_crc_valid=None if name == 'mbr-valid' else name != 'gpt-primary-damaged',
                backup_header_crc_valid=None if name == 'mbr-valid' else True,
                source_effects='Supplied bytes only;Windows observations not run')
