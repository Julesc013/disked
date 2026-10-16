"""Independent generated exFAT File-set bytes for DE-W064 verification."""
import datetime
import struct

def set_checksum(raw):
    value = 0
    for index, byte in enumerate(raw):
        if index not in (2, 3):
            value = ((value // 2) + (value % 2) * 32768 + byte) % 65536
    return value

def seal(raw):
    declared = (raw[1] + 1) * 32
    assert len(raw) >= declared
    struct.pack_into('<H', raw, 2, set_checksum(raw[:declared]))
    return raw

def timestamp(year=2024, month=2, day=29, hour=23, minute=59, double_seconds=29):
    return ((year - 1980) << 25) | (month << 21) | (day << 16) | (hour << 11) | (minute << 5) | double_seconds

def valid_timestamp(raw):
    try:
        datetime.datetime(1980 + (raw >> 25), (raw >> 21) & 15,
                          (raw >> 16) & 31, (raw >> 11) & 31,
                          (raw >> 5) & 63, (raw & 31) * 2)
        return True
    except ValueError:
        return False

def file_set(units, *, attributes=32, cluster=2, length=512, valid_length=None,
             flags=1, extra=(), padding=0):
    assert 1 <= len(units) <= 255
    names = (len(units) + 14) // 15
    count = 1 + names + len(extra)
    assert count <= 255
    raw = bytearray((count + 1) * 32)
    raw[0:2] = bytes((0x85, count))
    struct.pack_into('<H', raw, 4, attributes)
    for at in (8, 12, 16):
        struct.pack_into('<I', raw, at, timestamp())
    raw[20:25] = bytes((199, 199, 128, 128, 128))
    raw[32:36] = bytes((0xc0, flags, 0, len(units)))
    struct.pack_into('<Q', raw, 40, length if valid_length is None else valid_length)
    struct.pack_into('<I', raw, 52, cluster)
    struct.pack_into('<Q', raw, 56, length)
    for i in range(names):
        at = 64 + i * 32
        raw[at] = 0xc1
        values = list(units[i * 15:(i + 1) * 15])
        values += [padding] * (15 - len(values))
        struct.pack_into('<15H', raw, at + 2, *values)
    for i, entry in enumerate(extra):
        assert len(entry) == 32
        at = (2 + names + i) * 32
        raw[at:at + 32] = entry
    return seal(raw)

def extension(kind=0xe2):
    raw = bytearray(32)
    raw[0] = kind
    raw[2:] = bytes(range(30))
    return bytes(raw)
