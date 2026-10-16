#include "ntfs.h"
#include <string.h>

static unsigned short word(const unsigned char *p) {
    return (unsigned short)((de_u32)p[0] | ((de_u32)p[1] << 8));
}
static de_u32 dword(const unsigned char *p) {
    return (de_u32)word(p) | ((de_u32)word(p + 2) << 16);
}
static int zero(const de_u64 *n) {
    return !(n->limb[0] || n->limb[1] || n->limb[2] || n->limb[3]);
}
static int maximum(const de_u64 *n) {
    return n->limb[0] == 65535U && n->limb[1] == 65535U && n->limb[2] == 65535U &&
           n->limb[3] == 65535U;
}
static int negative(const de_u64 *n) {
    return (n->limb[3] & 0x8000) != 0;
}
static int span(size_t start, size_t count, size_t header, size_t length) {
    return start <= length && count <= length - start && (!count || start >= header);
}

int de_ntfs_attributes_begin(const de_view *original, unsigned int major, unsigned int minor,
                             const de_buffer *restored, unsigned int limit,
                             de_ntfs_attr_cursor *out) {
    de_ntfs_attr_cursor value;
    de_ntfs_record record;
    int status;
    if (!out)
        return DE_INVALID;
    if (!limit || limit > DE_NTFS_MAX_ITEMS)
        return DE_BOUNDS;
    status = de_ntfs_record_restore(original, major, minor, restored, &record);
    if (status)
        return status;
    memset(&value, 0, sizeof(value));
    value.logical.data = restored->data;
    value.logical.size = (size_t)record.used_bytes;
    value.offset = record.attribute_offset;
    value.limit = limit;
    *out = value;
    return DE_OK;
}

static int decode(const de_view *raw, de_ntfs_attribute *value) {
    const unsigned char *p;
    size_t length, header, name_bytes;
    de_u64 one, difference;
    int advance;
    memset(value, 0, sizeof(*value));
    value->raw = *raw;
    if (raw->size < 4) {
        value->issues = DE_NTFS_ATTR_TRUNCATED | DE_NTFS_ATTR_END;
        return 0;
    }
    p = raw->data;
    value->type = dword(p);
    if (value->type == 0xffffffffUL) {
        value->raw.size = 4;
        value->end_marker = 1;
        return 0;
    }
    if (raw->size < 16) {
        value->issues = DE_NTFS_ATTR_TRUNCATED;
        return 0;
    }
    value->present = 1;
    value->record_length = dword(p + 4);
    value->form = p[8];
    value->name_length = p[9];
    value->name_offset = word(p + 10);
    value->flags = word(p + 12);
    value->instance = word(p + 14);
    if (value->type < 0x10 || value->type > 0x100 || value->type % 16)
        value->issues |= DE_NTFS_ATTR_TYPE;
    advance = value->record_length >= 16 && !(value->record_length & 7) &&
              value->record_length <= raw->size;
    if (!advance) {
        value->issues |= DE_NTFS_ATTR_LENGTH;
        return 0;
    }
    length = (size_t)value->record_length;
    value->raw.size = length;
    header = value->form == 0 ? 24 : 64;
    if (value->form > 1) {
        value->issues |= DE_NTFS_ATTR_FORM;
        return 1;
    }
    if (length < header) {
        value->issues |= DE_NTFS_ATTR_LENGTH;
        return 1;
    }
    value->variant_fields = 1;
    if (!value->form) {
        value->value_length = dword(p + 16);
        value->value_offset = word(p + 20);
        value->resident_flags = p[22];
        if (value->flags || (value->resident_flags & 0xfe))
            value->issues |= DE_NTFS_ATTR_FEATURE;
    } else {
        de_u64_load_le(p + 16, 8, &value->lowest_vcn);
        de_u64_load_le(p + 24, 8, &value->highest_vcn);
        value->mapping_offset = word(p + 32);
        value->compression_unit = word(p + 34);
        de_u64_load_le(p + 40, 8, &value->allocated_size);
        de_u64_load_le(p + 48, 8, &value->data_size);
        de_u64_load_le(p + 56, 8, &value->initialized_size);
        value->sizes_applicable = zero(&value->lowest_vcn);
        if (value->sizes_applicable && (value->flags & 0x80ff)) {
            header = 72;
            if (length < header)
                value->issues |= DE_NTFS_ATTR_LENGTH;
            else {
                de_u64_load_le(p + 64, 8, &value->total_allocated);
                value->has_total_allocated = 1;
            }
        }
        if ((value->flags & 0x7fff) || value->compression_unit)
            value->issues |= DE_NTFS_ATTR_FEATURE;
        if (value->sizes_applicable) {
            if (negative(&value->allocated_size) || negative(&value->data_size) ||
                negative(&value->initialized_size) ||
                (value->has_total_allocated && negative(&value->total_allocated)) ||
                de_u64_compare(&value->initialized_size, &value->data_size) > 0 ||
                (!value->flags && de_u64_compare(&value->data_size, &value->allocated_size) > 0))
                value->issues |= DE_NTFS_ATTR_SIZE;
            value->empty_stream = maximum(&value->highest_vcn) && zero(&value->allocated_size) &&
                                  zero(&value->data_size) && zero(&value->initialized_size) &&
                                  (!value->has_total_allocated || zero(&value->total_allocated));
        }
        if (!value->empty_stream) {
            one = de_u64_from_u32(1);
            if (negative(&value->lowest_vcn) || negative(&value->highest_vcn) ||
                de_u64_sub(&value->highest_vcn, &value->lowest_vcn, &difference) ||
                de_u64_add(&difference, &one, &value->cluster_span))
                value->issues |= DE_NTFS_ATTR_VCN;
        }
    }
    name_bytes = (size_t)value->name_length * 2;
    if (name_bytes) {
        if (!span(value->name_offset, name_bytes, header, length))
            value->issues |= DE_NTFS_ATTR_NAME;
        else {
            value->name.data = p + value->name_offset;
            value->name.size = name_bytes;
        }
    }
    if (!value->form) {
        if (value->value_offset > length || value->value_length > length - value->value_offset ||
            (value->value_length && value->value_offset < header))
            value->issues |= DE_NTFS_ATTR_VALUE;
        else {
            value->value.data = p + value->value_offset;
            value->value.size = (size_t)value->value_length;
            if (name_bytes && value->name.size && value->value.size &&
                value->name_offset < value->value_offset + value->value.size &&
                value->value_offset < value->name_offset + name_bytes)
                value->issues |= DE_NTFS_ATTR_NAME;
        }
    } else {
        if (value->mapping_offset < header || value->mapping_offset >= length ||
            (name_bytes && value->name.size &&
             value->name_offset + name_bytes > value->mapping_offset))
            value->issues |= DE_NTFS_ATTR_MAPPING;
        else {
            value->mapping.data = p + value->mapping_offset;
            value->mapping.size = length - value->mapping_offset;
        }
    }
    value->envelope_valid = !(value->issues & ~(DE_NTFS_ATTR_TYPE | DE_NTFS_ATTR_FEATURE));
    value->ordinary_mapping = value->form == 1 && value->envelope_valid &&
                              !(value->issues & (DE_NTFS_ATTR_TYPE | DE_NTFS_ATTR_FEATURE));
    return 1;
}

int de_ntfs_attributes_next(de_ntfs_attr_cursor *cursor, de_ntfs_attribute *out) {
    de_ntfs_attr_cursor next;
    de_ntfs_attribute value;
    de_view raw;
    int advance;
    if (!cursor || !out || (!cursor->logical.data && cursor->logical.size) ||
        cursor->logical.size > DE_NTFS_MAX_RECORD || cursor->offset > cursor->logical.size ||
        !cursor->limit || cursor->limit > DE_NTFS_MAX_ITEMS || cursor->count > cursor->limit)
        return DE_INVALID;
    if (cursor->terminated || cursor->stopped)
        return DE_EMPTY;
    next = *cursor;
    raw.data = cursor->logical.data;
    if (cursor->offset)
        raw.data += cursor->offset;
    raw.size = cursor->logical.size - cursor->offset;
    if (cursor->count == cursor->limit && (raw.size < 4 || dword(raw.data) != 0xffffffffUL)) {
        memset(&value, 0, sizeof(value));
        value.raw = raw;
        value.issues = DE_NTFS_ATTR_BUDGET;
        next.stopped = 1;
    } else {
        advance = decode(&raw, &value);
        if (value.end_marker)
            next.terminated = 1;
        else {
            if (value.present)
                ++next.count;
            if (advance)
                next.offset += (size_t)value.record_length;
            else
                next.stopped = 1;
        }
    }
    next.issues |= value.issues;
    *cursor = next;
    *out = value;
    return DE_OK;
}
