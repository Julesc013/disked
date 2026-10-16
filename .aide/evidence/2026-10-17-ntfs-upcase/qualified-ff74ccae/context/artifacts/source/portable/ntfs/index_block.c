#include "ntfs.h"
#include "fixup.h"
#include <string.h>

static unsigned short word(const unsigned char *p) {
    return (unsigned short)((de_u32)p[0] | ((de_u32)p[1] << 8));
}
static de_u32 dword(const unsigned char *p) {
    return (de_u32)word(p) | ((de_u32)word(p + 2) << 16);
}

int de_ntfs_index_block_read(const de_view *raw, unsigned int major, unsigned int minor,
                             de_u32 expected, const de_u64 *vbn, de_ntfs_index_block *out) {
    de_ntfs_index_block value;
    const unsigned char *p;
    size_t array_bytes;
    if (!raw || !vbn || !out || (!raw->data && raw->size) || major != 3 || minor > 1)
        return DE_INVALID;
    if (expected < 512 || expected > DE_NTFS_MAX_RECORD || (expected & (expected - 1)) ||
        (vbn->limb[3] & 0x8000U) || raw->size > DE_NTFS_MAX_RECORD)
        return DE_BOUNDS;
    memset(&value, 0, sizeof(value));
    value.raw = *raw;
    if (raw->size != expected)
        value.issues |= DE_NTFS_LENGTH;
    if (raw->size < 40) {
        value.issues |= DE_NTFS_TRUNCATED;
        *out = value;
        return DE_OK;
    }
    p = raw->data;
    value.fields_present = 1;
    if (memcmp(p, "INDX", 4))
        value.issues |= DE_NTFS_SIGNATURE;
    value.usa_offset = word(p + 4);
    value.usa_count = word(p + 6);
    de_u64_load_le(p + 8, 8, &value.log_sequence);
    de_u64_load_le(p + 16, 8, &value.vbn);
    if (de_u64_compare(&value.vbn, vbn))
        value.issues |= DE_NTFS_BLOCK_VBN;
    value.first_offset = dword(p + 24);
    value.used_bytes = dword(p + 28);
    value.allocated_bytes = dword(p + 32);
    value.flags = p[36];
    if (value.flags & ~1U)
        value.issues |= DE_NTFS_BLOCK_FLAGS;
    value.strides = (unsigned int)(raw->size / DE_NTFS_STRIDE);
    if (!value.usa_count || value.usa_count != value.strides + 1)
        value.issues |= DE_NTFS_USA_COUNT;
    if (value.usa_count > 255) {
        value.issues |= DE_NTFS_USA_OFFSET;
        array_bytes = 0;
    } else
        array_bytes = (size_t)value.usa_count * 2;
    if (value.usa_offset < 40 || (value.usa_offset & 1) || value.usa_offset > 510 ||
        array_bytes > 510 - (size_t)value.usa_offset || value.usa_offset > raw->size ||
        array_bytes > raw->size - value.usa_offset)
        value.issues |= DE_NTFS_USA_OFFSET;
    if (value.first_offset < 16 || (value.first_offset & 7) ||
        value.used_bytes < value.first_offset || value.used_bytes - value.first_offset < 16 ||
        value.used_bytes > value.allocated_bytes || value.allocated_bytes > raw->size - 24 ||
        value.usa_offset > 24 + value.first_offset ||
        array_bytes > 24 + value.first_offset - value.usa_offset)
        value.issues |= DE_NTFS_HEADER;
    if (!(value.issues & (DE_NTFS_LENGTH | DE_NTFS_USA_OFFSET | DE_NTFS_USA_COUNT))) {
        value.update_sequence = word(p + value.usa_offset);
        value.mismatched_tails = de_ntfs_fixup_mismatches(raw, value.usa_offset, value.strides);
        if (value.mismatched_tails)
            value.issues |= DE_NTFS_TORN;
        else
            value.fixups_valid = 1;
    }
    value.envelope_valid = value.issues == 0;
    *out = value;
    return DE_OK;
}

int de_ntfs_index_block_restore(const de_view *raw, unsigned int major, unsigned int minor,
                                de_u32 expected, const de_u64 *vbn, const de_buffer *restored,
                                de_ntfs_index_block *out) {
    de_ntfs_index_block value;
    int status;
    if (!restored || !out || (!restored->data && restored->size))
        return DE_INVALID;
    status = de_ntfs_index_block_read(raw, major, minor, expected, vbn, &value);
    if (status)
        return status;
    if (!value.envelope_valid)
        return DE_INVALID;
    status = de_ntfs_fixup_restore(raw, value.usa_offset, restored);
    if (status)
        return status;
    *out = value;
    return DE_OK;
}

int de_ntfs_index_block_begin(const de_view *raw, unsigned int major, unsigned int minor,
                              de_u32 expected, const de_u64 *vbn, const de_buffer *restored,
                              unsigned int limit, de_ntfs_index_block *out,
                              de_ntfs_index_cursor *cursor) {
    de_ntfs_index_block value;
    de_ntfs_index_cursor next;
    int status;
    if (!out || !cursor)
        return DE_INVALID;
    if (!limit || limit > DE_NTFS_MAX_ITEMS)
        return DE_BOUNDS;
    status = de_ntfs_index_block_restore(raw, major, minor, expected, vbn, restored, &value);
    if (status)
        return status;
    memset(&next, 0, sizeof(next));
    next.value.data = restored->data + 24 + (size_t)value.first_offset;
    next.value.size = (size_t)(value.used_bytes - value.first_offset);
    next.major = major;
    next.minor = minor;
    next.limit = limit;
    next.has_children = (value.flags & 1) != 0;
    *out = value;
    *cursor = next;
    return DE_OK;
}
