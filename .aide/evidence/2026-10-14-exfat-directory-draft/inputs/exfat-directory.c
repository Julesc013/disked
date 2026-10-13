#include "exfat.h"
#include <string.h>

static unsigned short word(const unsigned char *p) {
    return (unsigned short)((de_u32)p[0] | ((de_u32)p[1] << 8));
}
static de_u32 dword(const unsigned char *p) {
    return (de_u32)word(p) | ((de_u32)word(p + 2) << 16);
}
static int nonzero(const unsigned char *p, size_t n) {
    size_t i;
    for (i = 0; i < n; ++i)
        if (p[i]) return 1;
    return 0;
}
static int illegal(unsigned short n) {
    return n < 32 || n == 34 || n == 42 || n == 47 || n == 58 ||
           n == 60 || n == 62 || n == 63 || n == 92 || n == 124;
}
static int encoding(const unsigned short *units, unsigned int count) {
    unsigned int i;
    for (i = 0; i < count; ++i) {
        unsigned short n = units[i];
        if (n >= 0xd800 && n <= 0xdbff) {
            if (++i >= count || units[i] < 0xdc00 || units[i] > 0xdfff) return 0;
        } else if (n >= 0xdc00 && n <= 0xdfff) return 0;
    }
    return 1;
}
static de_exfat_time time_value(de_u32 raw, unsigned int fraction, unsigned int offset) {
    static const unsigned char days[12] = {31,28,31,30,31,30,31,31,30,31,30,31};
    de_exfat_time value;
    unsigned int maximum;
    int signed_offset;
    memset(&value, 0, sizeof(value));
    value.raw = raw; value.fraction = fraction; value.offset = offset;
    value.year = 1980U + (unsigned int)(raw >> 25);
    value.month = (unsigned int)((raw >> 21) & 15);
    value.day = (unsigned int)((raw >> 16) & 31);
    value.hour = (unsigned int)((raw >> 11) & 31);
    value.minute = (unsigned int)((raw >> 5) & 63);
    value.second = (unsigned int)(raw & 31) * 2;
    value.offset_known = (offset & 128) != 0;
    signed_offset = (int)(offset & 127);
    if (signed_offset >= 64) signed_offset -= 128;
    if (value.offset_known) value.offset_minutes = signed_offset * 15;
    if (!value.month || value.month > 12 || !value.day || value.hour > 23 ||
        value.minute > 59 || value.second > 58 || fraction > 199 ||
        (!value.offset_known && (offset & 127))) return value;
    maximum = days[value.month - 1];
    if (value.month == 2 && !(value.year % 4) &&
        ((value.year % 100) || !(value.year % 400))) ++maximum;
    value.valid = value.day <= maximum;
    return value;
}

int de_exfat_slot_read(const de_view *record, de_exfat_slot *out) {
    de_exfat_slot value;
    const unsigned char *p;
    unsigned int i;
    if (!record || !out || (!record->data && record->size)) return DE_INVALID;
    if (record->size != 32) return DE_BOUNDS;
    memset(&value, 0, sizeof(value)); value.raw = *record; p = record->data;
    value.type = p[0]; value.in_use = (p[0] & 128) != 0;
    value.secondary = (p[0] & 64) != 0; value.benign = (p[0] & 32) != 0;
    if (!p[0]) value.kind = DE_EXFAT_DIR_END;
    else if (p[0] < 128) value.kind = DE_EXFAT_DIR_UNUSED;
    else if (p[0] == 128) { value.kind = DE_EXFAT_DIR_INVALID; value.issues = DE_EXFAT_DIR_TYPE; }
    else {
        value.kind = value.secondary ? DE_EXFAT_DIR_UNKNOWN_SECONDARY : DE_EXFAT_DIR_UNKNOWN_PRIMARY;
        switch (p[0]) {
        case 0x81: value.kind = DE_EXFAT_DIR_BITMAP; break;
        case 0x82: value.kind = DE_EXFAT_DIR_UPCASE; break;
        case 0x83: value.kind = DE_EXFAT_DIR_LABEL; break;
        case 0x85: value.kind = DE_EXFAT_DIR_FILE; break;
        case 0xc0: value.kind = DE_EXFAT_DIR_STREAM; break;
        case 0xc1: value.kind = DE_EXFAT_DIR_NAME; break;
        }
        value.secondary_count = p[1]; value.checksum = word(p + 2);
        value.flags = value.secondary ? p[1] : word(p + 4);
        value.first_cluster = dword(p + 20); de_u64_load_le(p + 24, 8, &value.data_length);
        if (value.kind == DE_EXFAT_DIR_BITMAP) value.flags = p[1];
        if (value.kind == DE_EXFAT_DIR_UPCASE) value.checksum = dword(p + 4);
        if (value.kind == DE_EXFAT_DIR_LABEL || value.kind == DE_EXFAT_DIR_NAME) {
            value.unit_count = value.kind == DE_EXFAT_DIR_LABEL ? (unsigned int)p[1] : 15U;
            if (value.unit_count > 11 && value.kind == DE_EXFAT_DIR_LABEL) value.issues |= DE_EXFAT_DIR_LENGTH;
            for (i = 0; i < (value.kind == DE_EXFAT_DIR_LABEL ? 11U : 15U); ++i)
                value.units[i] = word(p + 2 + i * 2);
        }
    }
    *out = value; return DE_OK;
}

int de_exfat_file_set_read(const de_view *records, de_u32 clusters, unsigned int cluster_shift,
                           size_t budget, de_exfat_file_set *out) {
    de_exfat_file_set value;
    const unsigned char *p, *s;
    size_t required, present, i, n;
    unsigned int names, expected, index;
    de_u32 sum;
    de_u64 count, size, capacity, remaining, limit, quotient, remainder;
    if (!records || !out || (!records->data && records->size) || !clusters ||
        clusters > DE_EXFAT_MAX_CLUSTERS || cluster_shift < 9 || cluster_shift > 25)
        return DE_INVALID;
    if (records->size > DE_EXFAT_DIR_MAX_SET || records->size > budget) return DE_BOUNDS;
    memset(&value, 0, sizeof(value)); value.raw = *records;
    value.present_bytes = (unsigned int)records->size;
    if (records->size < 32) { value.issues = DE_EXFAT_DIR_TRUNCATED; *out = value; return DE_OK; }
    p = records->data; value.primary_present = 1;
    value.secondary_count = p[1]; required = ((size_t)p[1] + 1) * 32;
    value.declared_bytes = (unsigned int)required;
    present = records->size < required ? records->size : required;
    value.present_bytes = (unsigned int)present; value.raw.size = present;
    value.complete = present == required;
    if (!value.complete) value.issues |= DE_EXFAT_DIR_TRUNCATED;
    if (p[0] != 0x85) { value.issues |= DE_EXFAT_DIR_TYPE; *out = value; return DE_OK; }
    value.stored_checksum = word(p + 2); value.attributes = word(p + 4);
    if ((value.attributes & ~0x37UL) || nonzero(p + 6, 2) || nonzero(p + 25, 7)) value.issues |= DE_EXFAT_DIR_RESERVED;
    value.created = time_value(dword(p + 8), p[20], p[22]);
    value.modified = time_value(dword(p + 12), p[21], p[23]);
    value.accessed = time_value(dword(p + 16), 0, p[24]);
    if (!value.created.valid || !value.modified.valid || !value.accessed.valid) value.issues |= DE_EXFAT_DIR_TIME;
    if (value.complete) {
        sum = 0;
        for (i = 0; i < required; ++i) {
            if (i == 2 || i == 3) continue;
            sum = ((sum >> 1) | ((sum & 1) ? 0x8000UL : 0)) + p[i]; sum &= 0xffffUL;
        }
        value.calculated_checksum = (unsigned short)sum;
        value.checksum_valid = value.stored_checksum == value.calculated_checksum;
        if (!value.checksum_valid) value.issues |= DE_EXFAT_DIR_CHECKSUM;
    }
    if (present < 64 || p[32] != 0xc0) {
        value.issues |= DE_EXFAT_DIR_ORDER; *out = value; return DE_OK;
    }
    s = p + 32; value.stream_present = 1; value.stream_flags = s[1];
    value.name_length = s[3]; value.name_hash = word(s + 4);
    de_u64_load_le(s + 8, 8, &value.valid_data_length);
    value.first_cluster = dword(s + 20); de_u64_load_le(s + 24, 8, &value.data_length);
    if ((s[1] & ~3U) || s[2] || nonzero(s + 6, 2) || nonzero(s + 16, 4)) value.issues |= DE_EXFAT_DIR_RESERVED;
    if (!(s[1] & 1)) value.issues |= DE_EXFAT_DIR_FLAGS;
    if (!value.name_length) value.issues |= DE_EXFAT_DIR_LENGTH;
    names = (value.name_length + 14) / 15; expected = names + 1;
    if (value.secondary_count < expected) value.issues |= DE_EXFAT_DIR_ORDER;
    for (index = 0; index < names; ++index) {
        i = ((size_t)index + 2) * 32;
        if (i + 32 > present) { value.issues |= DE_EXFAT_DIR_TRUNCATED; break; }
        if (p[i] != 0xc1) { value.issues |= DE_EXFAT_DIR_ORDER; break; }
        if (p[i + 1]) value.issues |= DE_EXFAT_DIR_RESERVED;
        for (n = 0; n < 15; ++n) {
            unsigned short unit = word(p + i + 2 + n * 2);
            if (value.name_units_present < value.name_length) {
                value.units[value.name_units_present++] = unit;
                if (illegal(unit)) value.issues |= DE_EXFAT_DIR_CHARACTERS;
            } else if (unit) value.issues |= DE_EXFAT_DIR_PADDING;
        }
    }
    for (index = expected + 1; index <= value.secondary_count; ++index) {
        i = (size_t)index * 32;
        if (i + 32 > present) break;
        if ((p[i] & 0xc0) != 0xc0 || p[i] == 0xc0 || p[i] == 0xc1) value.issues |= DE_EXFAT_DIR_ORDER;
        else if (!(p[i] & 32)) { ++value.unsupported_extensions; value.issues |= DE_EXFAT_DIR_UNSUPPORTED; }
        else ++value.benign_extensions;
    }
    value.encoding_valid = value.name_units_present == value.name_length && encoding(value.units, value.name_units_present);
    if (!value.encoding_valid) value.issues |= DE_EXFAT_DIR_UTF16;
    if ((value.name_length == 1 && value.units[0] == 46) ||
        (value.name_length == 2 && value.units[0] == 46 && value.units[1] == 46)) value.issues |= DE_EXFAT_DIR_DOT;
    value.name_characters_valid = value.name_length && value.name_units_present == value.name_length &&
        !(value.issues & (DE_EXFAT_DIR_CHARACTERS | DE_EXFAT_DIR_DOT));
    count = de_u64_from_u32(clusters); size = de_u64_from_u32((de_u32)1 << cluster_shift);
    de_u64_mul(&count, &size, &capacity);
    if (de_u64_compare(&value.data_length, &capacity) > 0 ||
        de_u64_compare(&value.valid_data_length, &value.data_length) > 0) value.issues |= DE_EXFAT_DIR_CAPACITY;
    limit = de_u64_from_u32(0);
    if ((!value.first_cluster && de_u64_compare(&value.data_length, &limit)) ||
        (value.first_cluster && (value.first_cluster < 2 || value.first_cluster > clusters + 1))) value.issues |= DE_EXFAT_DIR_CLUSTER;
    if (s[1] & 2) {
        if (!value.first_cluster || !de_u64_compare(&value.data_length, &limit)) value.issues |= DE_EXFAT_DIR_FLAGS;
        else if (value.first_cluster >= 2 && value.first_cluster <= clusters + 1) {
            remaining = de_u64_from_u32(clusters + 2 - value.first_cluster); de_u64_mul(&remaining, &size, &limit);
            if (de_u64_compare(&value.data_length, &limit) > 0) value.issues |= DE_EXFAT_DIR_CAPACITY;
        }
    }
    if (value.attributes & 16) {
        limit = de_u64_from_u32(268435456UL);
        de_u64_divmod(&value.data_length, &size, &quotient, &remainder);
        remaining = de_u64_from_u32(0);
        if (de_u64_compare(&value.valid_data_length, &value.data_length) ||
            de_u64_compare(&value.data_length, &limit) > 0 || de_u64_compare(&remainder, &remaining)) value.issues |= DE_EXFAT_DIR_LENGTH;
    }
    value.associated = value.complete && value.checksum_valid &&
        !(value.issues & (DE_EXFAT_DIR_TYPE | DE_EXFAT_DIR_ORDER | DE_EXFAT_DIR_UNSUPPORTED | DE_EXFAT_DIR_TRUNCATED));
    value.stream_valid = value.associated && !(value.issues & (DE_EXFAT_DIR_FLAGS | DE_EXFAT_DIR_CLUSTER | DE_EXFAT_DIR_CAPACITY | DE_EXFAT_DIR_LENGTH));
    value.metadata_valid = value.stream_valid && value.encoding_valid && value.name_characters_valid && !(value.issues & DE_EXFAT_DIR_TIME);
    *out = value; return DE_OK;
}
