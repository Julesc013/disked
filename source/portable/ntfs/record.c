#include "ntfs.h"
#include <string.h>

static unsigned short word(const unsigned char *p) {
    return (unsigned short)((de_u32)p[0] | ((de_u32)p[1] << 8));
}
static de_u32 dword(const unsigned char *p) {
    return (de_u32)word(p) | ((de_u32)word(p + 2) << 16);
}

int de_ntfs_record_read(const de_view *raw, unsigned int major, unsigned int minor,
                        de_ntfs_record *out) {
    de_ntfs_record value;
    const unsigned char *p;
    size_t array_bytes, i;
    if (!raw || !out || (!raw->data && raw->size))
        return DE_INVALID;
    if (raw->size > DE_NTFS_MAX_RECORD)
        return DE_BOUNDS;
    memset(&value, 0, sizeof(value));
    value.raw = *raw;
    if (major != 3 || minor > 1)
        value.issues |= DE_NTFS_VERSION;
    if (raw->size < DE_NTFS_STRIDE || raw->size % DE_NTFS_STRIDE)
        value.issues |= DE_NTFS_LENGTH;
    if (raw->size < 42) {
        value.issues |= DE_NTFS_TRUNCATED;
        *out = value;
        return DE_OK;
    }
    p = raw->data;
    value.fields_present = 1;
    if (memcmp(p, "FILE", 4))
        value.issues |= DE_NTFS_SIGNATURE;
    value.usa_offset = word(p + 4);
    value.usa_count = word(p + 6);
    de_u64_load_le(p + 8, 8, &value.log_sequence);
    value.sequence = word(p + 16);
    value.links = word(p + 18);
    value.attribute_offset = word(p + 20);
    value.flags = word(p + 22);
    value.used_bytes = dword(p + 24);
    value.allocated_bytes = dword(p + 28);
    de_u64_load_le(p + 32, 8, &value.base_reference);
    value.next_attribute_id = word(p + 40);
    value.in_use = (value.flags & 1) != 0;
    value.name_index_present = (value.flags & 2) != 0;
    value.strides = (unsigned int)(raw->size / DE_NTFS_STRIDE);
    if (!value.usa_count || value.usa_count != value.strides + 1)
        value.issues |= DE_NTFS_USA_COUNT;
    /* Reject before multiplication: size_t can be only 16 bits. */
    if (value.usa_count > 255) {
        value.issues |= DE_NTFS_USA_OFFSET;
        array_bytes = 0;
    } else
        array_bytes = (size_t)value.usa_count * 2;
    if (value.usa_offset < 42 || (value.usa_offset & 1) || value.usa_offset > 510 ||
        array_bytes > 510 - (size_t)value.usa_offset || value.usa_offset > raw->size ||
        array_bytes > raw->size - value.usa_offset)
        value.issues |= DE_NTFS_USA_OFFSET;
    if (value.allocated_bytes != (de_u32)raw->size || value.used_bytes > value.allocated_bytes ||
        value.attribute_offset < 42 || (value.attribute_offset & 7) ||
        value.attribute_offset > value.used_bytes ||
        value.used_bytes - value.attribute_offset < 4 ||
        value.usa_offset > value.attribute_offset ||
        array_bytes > (size_t)value.attribute_offset - value.usa_offset)
        value.issues |= DE_NTFS_HEADER;
    if (!(value.issues & (DE_NTFS_LENGTH | DE_NTFS_USA_OFFSET | DE_NTFS_USA_COUNT))) {
        value.update_sequence = word(p + value.usa_offset);
        for (i = 0; i < value.strides; ++i)
            if (word(p + (i + 1) * DE_NTFS_STRIDE - 2) != value.update_sequence)
                ++value.mismatched_tails;
        if (value.mismatched_tails)
            value.issues |= DE_NTFS_TORN;
        else
            value.fixups_valid = 1;
    }
    value.envelope_valid = value.issues == 0;
    *out = value;
    return DE_OK;
}

static int overlaps(const unsigned char *a, const unsigned char *b, size_t length) {
    size_t i;
    /* Equality is defined for unrelated objects; ordering pointers is not. */
    for (i = 0; i < length; ++i)
        if (a + i == b || b + i == a)
            return 1;
    return 0;
}
int de_ntfs_record_restore(const de_view *raw, unsigned int major, unsigned int minor,
                           const de_buffer *output, de_ntfs_record *out) {
    de_ntfs_record value;
    size_t i, offset;
    int status;
    if (!output || !out || (!output->data && output->size))
        return DE_INVALID;
    status = de_ntfs_record_read(raw, major, minor, &value);
    if (status)
        return status;
    if (!value.envelope_valid)
        return DE_INVALID;
    if (output->size < raw->size)
        return DE_BUFFER;
    if (overlaps(raw->data, output->data, raw->size))
        return DE_INVALID;
    memcpy(output->data, raw->data, raw->size);
    for (i = 0; i < value.strides; ++i) {
        offset = (i + 1) * DE_NTFS_STRIDE - 2;
        output->data[offset] = raw->data[value.usa_offset + (i + 1) * 2];
        output->data[offset + 1] = raw->data[value.usa_offset + (i + 1) * 2 + 1];
    }
    *out = value;
    return DE_OK;
}
