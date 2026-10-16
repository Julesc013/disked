#include "fat.h"
#include <string.h>

static unsigned short word(const unsigned char *p) {
    return (unsigned short)((de_u32)p[0] | ((de_u32)p[1] << 8));
}

static int valid_date(unsigned short raw) {
    static const unsigned char days[12] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    unsigned int year, month, day, maximum;
    if (!raw)
        return 1; /* Unspecified; no invented date or timezone. */
    year = 1980U + (raw >> 9);
    month = (raw >> 5) & 15U;
    day = raw & 31U;
    if (!month || month > 12 || !day)
        return 0;
    maximum = days[month - 1];
    if (month == 2 && !(year % 4) && ((year % 100) || !(year % 400)))
        ++maximum;
    return day <= maximum;
}

static int valid_time(unsigned short raw) {
    return (raw >> 11) <= 23 && ((raw >> 5) & 63U) <= 59 && (raw & 31U) <= 29;
}

int de_fat_dirent_read(const de_view *record, int bits, de_fat_dirent *out) {
    de_fat_dirent value;
    const unsigned char *p;
    unsigned short low, high;
    size_t i;
    static const unsigned char positions[13] = {1, 3, 5, 7, 9, 14, 16, 18, 20, 22, 24, 28, 30};
    if (!record || !out || (!record->data && record->size) ||
        (bits != 12 && bits != 16 && bits != 32))
        return DE_INVALID;
    if (record->size > 32)
        return DE_BOUNDS;
    memset(&value, 0, sizeof(value));
    value.raw = *record;
    if (record->size < 32) {
        value.issues = DE_FAT_DIR_TRUNCATED;
        *out = value;
        return DE_OK;
    }
    p = record->data;
    value.name_field.data = p;
    value.name_field.size = 11;
    if (!p[0] || p[0] == 0xe5) {
        value.kind = p[0] ? DE_FAT_DIRENT_DELETED : DE_FAT_DIRENT_END;
        *out = value;
        return DE_OK;
    }
    value.attributes = p[11];
    if (p[11] & 0xc0)
        value.issues |= DE_FAT_DIR_ATTRIBUTES;
    if ((p[11] & 0x3f) == 0x0f) {
        value.kind = DE_FAT_DIRENT_LONG;
        value.ordinal = p[0];
        value.checksum = p[13];
        value.lfn_type = p[12];
        if ((p[0] & 0xa0) || !(p[0] & 31) || (p[0] & 31) > 20)
            value.issues |= DE_FAT_DIR_ORDINAL;
        if (p[12] || word(p + 26))
            value.issues |= DE_FAT_DIR_SLOT;
        for (i = 0; i < 13; ++i)
            value.lfn_units[i] = word(p + positions[i]);
        *out = value;
        return DE_OK;
    }
    value.kind =
        (p[11] & 0x18) == 0x18
            ? DE_FAT_DIRENT_INVALID
            : ((p[11] & 8) ? DE_FAT_DIRENT_VOLUME
                           : ((p[11] & 16) ? DE_FAT_DIRENT_DIRECTORY : DE_FAT_DIRENT_FILE));
    if (value.kind == DE_FAT_DIRENT_INVALID)
        value.issues |= DE_FAT_DIR_ATTRIBUTES;
    value.case_flags = p[12];
    value.creation_fraction = p[13];
    if (p[12] & ~0x18U)
        value.issues |= DE_FAT_DIR_CASE;
    if (p[0] == 0x20)
        value.issues |= DE_FAT_DIR_NAME;
    value.lead_byte_escape = p[0] == 5;
    if (!memcmp(p, ".          ", 11))
        value.dot = 1;
    else if (!memcmp(p, "..         ", 11))
        value.dot = 2;
    high = word(p + 20);
    low = word(p + 26);
    value.raw_cluster = ((de_u32)high << 16) | low;
    value.cluster = bits == 32 ? value.raw_cluster & 0x0fffffffUL : low;
    if ((bits == 32 && (value.raw_cluster & 0xf0000000UL)) || (bits != 32 && high) ||
        (bits == 12 && low > 0xfff))
        value.issues |= DE_FAT_DIR_CLUSTER;
    value.file_bytes = (de_u32)word(p + 28) | ((de_u32)word(p + 30) << 16);
    if ((value.kind == DE_FAT_DIRENT_VOLUME && (value.cluster || value.file_bytes)) ||
        (value.kind == DE_FAT_DIRENT_DIRECTORY && value.file_bytes) ||
        (value.kind == DE_FAT_DIRENT_FILE &&
         ((!value.file_bytes && value.cluster) || (value.file_bytes && value.cluster < 2))))
        value.issues |= DE_FAT_DIR_FILE_STATE;
    value.creation_time = word(p + 14);
    value.creation_date = word(p + 16);
    value.access_date = word(p + 18);
    value.write_time = word(p + 22);
    value.write_date = word(p + 24);
    if (p[13] > 199 || !valid_date(value.creation_date) || !valid_date(value.access_date) ||
        !valid_date(value.write_date) || !valid_time(value.creation_time) ||
        !valid_time(value.write_time))
        value.issues |= DE_FAT_DIR_TIME;
    *out = value;
    return DE_OK;
}

int de_fat_short_checksum(const de_view *name, unsigned char *out) {
    unsigned int value = 0;
    size_t i;
    if (!name || !out || (!name->data && name->size))
        return DE_INVALID;
    if (name->size != 11)
        return DE_BOUNDS;
    for (i = 0; i < 11; ++i) {
        value = (value >> 1) | ((value & 1U) << 7);
        value = (value + name->data[i]) & 255U;
    }
    *out = (unsigned char)value;
    return DE_OK;
}

int de_fat_lfn_read(const de_view *slots, const de_view *short_record, int bits, de_fat_lfn *out) {
    de_fat_lfn value;
    de_fat_dirent entry, slot;
    de_view record;
    unsigned char checksum;
    size_t i, n, at;
    unsigned short unit;
    de_u32 association_issues;
    int status;
    if (!slots || !short_record || !out || (!slots->data && slots->size) ||
        (!short_record->data && short_record->size) || (bits != 12 && bits != 16 && bits != 32))
        return DE_INVALID;
    if (slots->size > DE_FAT_LFN_MAX_SLOTS * 32U)
        return DE_BUFFER;
    if (short_record->size > 32)
        return DE_BOUNDS;
    memset(&value, 0, sizeof(value));
    value.raw_slots = *slots;
    value.raw_short = *short_record;
    if (!slots->size) {
        *out = value;
        return DE_OK;
    }
    if ((slots->size % 32) || short_record->size < 32) {
        value.issues = DE_FAT_LFN_TRUNCATED;
        *out = value;
        return DE_OK;
    }
    value.slots = slots->size / 32;
    status = de_fat_dirent_read(short_record, bits, &entry);
    if (status)
        return status;
    if ((entry.kind != DE_FAT_DIRENT_FILE && entry.kind != DE_FAT_DIRENT_DIRECTORY) || entry.dot ||
        (entry.issues & (DE_FAT_DIR_ATTRIBUTES | DE_FAT_DIR_NAME)))
        value.issues |= DE_FAT_LFN_SHORT_ENTRY;
    status = de_fat_short_checksum(&entry.name_field, &checksum);
    if (status)
        return status;
    for (i = 0; i < value.slots; ++i) {
        record.data = slots->data + i * 32;
        record.size = 32;
        status = de_fat_dirent_read(&record, bits, &slot);
        if (status)
            return status;
        if (slot.kind != DE_FAT_DIRENT_LONG ||
            slot.issues & (DE_FAT_DIR_ATTRIBUTES | DE_FAT_DIR_SLOT))
            value.issues |= DE_FAT_LFN_SLOT;
        if (slot.ordinal != (value.slots - i + (i ? 0U : 64U)))
            value.issues |= DE_FAT_LFN_ORDINAL;
        if (slot.checksum != checksum)
            value.issues |= DE_FAT_LFN_CHECKSUM;
    }
    /* Bad order cannot establish a logical string. Original records stay raw. */
    if (value.issues & DE_FAT_LFN_ORDINAL) {
        *out = value;
        return DE_OK;
    }
    value.unit_count = value.slots * 13;
    for (i = 0; i < value.slots; ++i) {
        record.data = slots->data + i * 32;
        record.size = 32;
        status = de_fat_dirent_read(&record, bits, &slot);
        if (status)
            return status;
        at = (value.slots - i - 1) * 13;
        for (n = 0; n < 13; ++n)
            value.units[at + n] = slot.lfn_units[n];
    }
    value.name_length = value.unit_count;
    for (i = 0; i < value.unit_count; ++i) {
        if (!value.units[i]) {
            value.name_length = i;
            value.terminated = 1;
            break;
        }
        if (value.units[i] == 0xffff)
            value.issues |= DE_FAT_LFN_PADDING;
    }
    if (value.terminated) {
        for (i = value.name_length + 1; i < value.unit_count; ++i)
            if (value.units[i] != 0xffff)
                value.issues |= DE_FAT_LFN_PADDING;
    }
    if (!value.name_length || value.name_length > 255 ||
        value.name_length <= (value.slots - 1) * 13)
        value.issues |= DE_FAT_LFN_LENGTH;
    for (i = 0; i < value.name_length; ++i) {
        unit = value.units[i];
        if (unit < 32 || unit == '"' || unit == '*' || unit == '/' || unit == ':' || unit == '<' ||
            unit == '>' || unit == '?' || unit == '\\' || unit == '|')
            value.issues |= DE_FAT_LFN_CHARACTERS;
        if (unit < 32 || unit > 126 || unit == '\\')
            value.requires_escaping = 1;
        if (unit >= 0xd800 && unit <= 0xdbff) {
            if (i + 1 == value.name_length || value.units[i + 1] < 0xdc00 ||
                value.units[i + 1] > 0xdfff)
                value.issues |= DE_FAT_LFN_UTF16;
            else
                ++i;
        } else if (unit >= 0xdc00 && unit <= 0xdfff)
            value.issues |= DE_FAT_LFN_UTF16;
    }
    if (value.name_length && (value.units[0] == ' ' || value.units[value.name_length - 1] == ' ' ||
                              value.units[value.name_length - 1] == '.'))
        value.issues |= DE_FAT_LFN_NONCANONICAL;
    value.unicode_valid = !(value.issues & DE_FAT_LFN_UTF16);
    value.canonical_name =
        !(value.issues & (DE_FAT_LFN_PADDING | DE_FAT_LFN_LENGTH | DE_FAT_LFN_UTF16 |
                          DE_FAT_LFN_CHARACTERS | DE_FAT_LFN_NONCANONICAL));
    association_issues = DE_FAT_LFN_SLOT | DE_FAT_LFN_CHECKSUM | DE_FAT_LFN_SHORT_ENTRY |
                         DE_FAT_LFN_PADDING | DE_FAT_LFN_LENGTH;
    value.associated = !(value.issues & association_issues);
    *out = value;
    return DE_OK;
}

int de_fat_name_display(const unsigned short *units, size_t count, char *out, size_t capacity) {
    static const char hex[] = "0123456789ABCDEF";
    size_t i, required = 0, position = 0;
    unsigned int unit, shift;
    if (!out || (!units && count))
        return DE_INVALID;
    if (count > DE_FAT_LFN_MAX_UNITS)
        return DE_BUFFER;
    if (capacity <= count)
        return DE_BUFFER;
    for (i = 0; i < count; ++i) {
        unit = units[i];
        required += unit == '\\' ? 2 : (unit >= 32 && unit <= 126 ? 1 : 6);
    }
    if (capacity <= required)
        return DE_BUFFER;
    for (i = 0; i < count; ++i) {
        unit = units[i];
        if (unit == '\\') {
            out[position++] = '\\';
            out[position++] = '\\';
        } else if (unit >= 32 && unit <= 126)
            out[position++] = (char)unit;
        else {
            out[position++] = '\\';
            out[position++] = 'u';
            for (shift = 12;; shift -= 4) {
                out[position++] = hex[(unit >> shift) & 15U];
                if (!shift)
                    break;
            }
        }
    }
    out[position] = '\0';
    return DE_OK;
}
