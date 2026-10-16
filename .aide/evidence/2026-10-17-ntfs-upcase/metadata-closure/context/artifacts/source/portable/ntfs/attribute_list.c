#include "ntfs.h"
#include <string.h>

static unsigned short word(const unsigned char *p) {
    return (unsigned short)((de_u32)p[0] | ((de_u32)p[1] << 8));
}
static de_u32 dword(const unsigned char *p) {
    return (de_u32)word(p) | ((de_u32)word(p + 2) << 16);
}

int de_ntfs_attr_list_begin(const de_view *value, unsigned int major, unsigned int minor,
                            unsigned int limit, de_ntfs_attr_list_cursor *out) {
    de_ntfs_attr_list_cursor next;
    if (!value || !out || (!value->data && value->size) || major != 3 || minor > 1)
        return DE_INVALID;
    if (!limit || limit > DE_NTFS_MAX_ITEMS)
        return DE_BOUNDS;
    memset(&next, 0, sizeof(next));
    next.value = *value;
    next.limit = limit;
    next.terminated = value->size == 0;
    *out = next;
    return DE_OK;
}

static int decode(const de_view *raw, de_ntfs_attr_list_entry *entry) {
    const unsigned char *p;
    size_t length, name_bytes;
    memset(entry, 0, sizeof(*entry));
    entry->raw = *raw;
    if (raw->size < 26) {
        entry->issues = DE_NTFS_LIST_TRUNCATED;
        return 0;
    }
    p = raw->data;
    entry->present = 1;
    entry->type = dword(p);
    entry->record_length = word(p + 4);
    entry->name_length = p[6];
    entry->name_offset = p[7];
    de_u64_load_le(p + 8, 8, &entry->lowest_vcn);
    de_u64_load_le(p + 16, 8, &entry->segment_reference);
    entry->record_number = entry->segment_reference;
    entry->record_number.limb[3] = 0;
    entry->sequence = entry->segment_reference.limb[3];
    entry->attribute_id = word(p + 24);
    if (entry->type < 0x10 || entry->type > 0x100 || entry->type % 16)
        entry->issues |= DE_NTFS_LIST_TYPE;
    if (entry->lowest_vcn.limb[3] & 0x8000U)
        entry->issues |= DE_NTFS_LIST_VCN;
    length = entry->record_length;
    if (length < 26 || length > raw->size)
        entry->issues |= DE_NTFS_LIST_LENGTH;
    if (length > raw->size)
        entry->issues |= DE_NTFS_LIST_TRUNCATED;
    if (length & 7)
        entry->issues |= DE_NTFS_LIST_ALIGNMENT;
    if (entry->issues & (DE_NTFS_LIST_LENGTH | DE_NTFS_LIST_ALIGNMENT))
        return 0;
    entry->raw.size = length;
    name_bytes = (size_t)entry->name_length * 2;
    if (name_bytes) {
        if (entry->name_offset < 26 || entry->name_offset > length ||
            name_bytes > length - entry->name_offset)
            entry->issues |= DE_NTFS_LIST_NAME;
        else {
            entry->name.data = p + entry->name_offset;
            entry->name.size = name_bytes;
        }
    }
    entry->envelope_valid = !(entry->issues & ~DE_NTFS_LIST_TYPE);
    return 1;
}

int de_ntfs_attr_list_next(de_ntfs_attr_list_cursor *cursor, de_ntfs_attr_list_entry *out) {
    de_ntfs_attr_list_cursor next;
    de_ntfs_attr_list_entry value;
    de_view raw;
    int advance;
    if (!cursor || !out || (!cursor->value.data && cursor->value.size) ||
        cursor->offset > cursor->value.size || !cursor->limit ||
        cursor->limit > DE_NTFS_MAX_ITEMS || cursor->count > cursor->limit)
        return DE_INVALID;
    if (cursor->terminated || cursor->stopped || cursor->offset == cursor->value.size)
        return DE_EMPTY;
    next = *cursor;
    raw.data = cursor->value.data;
    if (cursor->offset)
        raw.data += cursor->offset;
    raw.size = cursor->value.size - cursor->offset;
    if (cursor->count == cursor->limit) {
        memset(&value, 0, sizeof(value));
        value.raw = raw;
        value.issues = DE_NTFS_LIST_BUDGET;
        next.stopped = 1;
    } else {
        advance = decode(&raw, &value);
        if (value.present)
            ++next.count;
        if (advance) {
            next.offset += value.record_length;
            next.terminated = next.offset == next.value.size;
        } else
            next.stopped = 1;
    }
    next.issues |= value.issues;
    *cursor = next;
    *out = value;
    return DE_OK;
}
