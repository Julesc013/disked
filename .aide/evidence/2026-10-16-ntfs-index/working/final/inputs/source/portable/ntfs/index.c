#include "ntfs.h"
#include <string.h>

static unsigned short word(const unsigned char *p) {
    return (unsigned short)((de_u32)p[0] | ((de_u32)p[1] << 8));
}
static de_u32 dword(const unsigned char *p) {
    return (de_u32)word(p) | ((de_u32)word(p + 2) << 16);
}
static int power_two(de_u32 value) {
    return value && !(value & (value - 1));
}

int de_ntfs_index_root_begin(const de_view *raw, unsigned int major, unsigned int minor,
                             de_u32 cluster, de_u32 expected, unsigned int limit,
                             de_ntfs_index_root *out, de_ntfs_index_cursor *cursor) {
    de_ntfs_index_root root;
    de_ntfs_index_cursor next;
    const unsigned char *p;
    de_u32 units;
    if (!raw || !out || !cursor || (!raw->data && raw->size) || major != 3 || minor > 1)
        return DE_INVALID;
    if (!limit || limit > DE_NTFS_MAX_ITEMS || cluster < 512 || cluster > DE_NTFS_MAX_CLUSTER ||
        !power_two(cluster) || expected < 512 || expected > DE_NTFS_MAX_RECORD ||
        !power_two(expected))
        return DE_BOUNDS;
    memset(&root, 0, sizeof(root));
    memset(&next, 0, sizeof(next));
    root.raw = *raw;
    next.major = major;
    next.minor = minor;
    next.limit = limit;
    next.stopped = 1;
    if (raw->size < 32)
        root.issues = DE_NTFS_INDEX_TRUNCATED;
    else {
        p = raw->data;
        root.fields_present = 1;
        root.type = dword(p);
        root.collation = dword(p + 4);
        root.index_bytes = dword(p + 8);
        root.units_per_index = p[12];
        root.first_offset = dword(p + 16);
        root.used_bytes = dword(p + 20);
        root.allocated_bytes = dword(p + 24);
        root.flags = p[28];
        root.child_unit_bytes = expected < cluster ? 512 : cluster;
        units = expected / root.child_unit_bytes;
        root.geometry_matches = root.index_bytes == expected && root.units_per_index == units;
        if (!root.geometry_matches)
            root.issues |= DE_NTFS_INDEX_GEOMETRY;
        if (root.type != 0x30 || root.collation != 1)
            root.issues |= DE_NTFS_INDEX_PROFILE;
        if (root.flags & ~1U)
            root.issues |= DE_NTFS_INDEX_FLAGS;
        if (root.first_offset & 7)
            root.issues |= DE_NTFS_INDEX_ALIGNMENT;
        if (root.first_offset < 16 || root.used_bytes < root.first_offset ||
            root.used_bytes - root.first_offset < 16 || root.used_bytes > root.allocated_bytes ||
            root.allocated_bytes > raw->size - 16)
            root.issues |= DE_NTFS_INDEX_LENGTH;
        if (root.allocated_bytes > raw->size - 16)
            root.issues |= DE_NTFS_INDEX_TRUNCATED;
        root.envelope_valid = !(root.issues & (DE_NTFS_INDEX_LENGTH | DE_NTFS_INDEX_ALIGNMENT));
        root.directory_profile = root.envelope_valid && !root.issues;
        if (root.envelope_valid) {
            next.value.data = p + 16 + (size_t)root.first_offset;
            next.value.size = (size_t)(root.used_bytes - root.first_offset);
        }
        next.has_children = (root.flags & 1) != 0;
        next.stopped = !root.directory_profile;
    }
    next.issues = root.issues;
    *out = root;
    *cursor = next;
    return DE_OK;
}

static void decode(const de_view *raw, int children, unsigned int major, unsigned int minor,
                   de_ntfs_index_entry *entry) {
    const unsigned char *p;
    size_t length, capacity;
    memset(entry, 0, sizeof(*entry));
    entry->raw = *raw;
    if (raw->size < 16) {
        entry->issues = DE_NTFS_INDEX_TRUNCATED | DE_NTFS_INDEX_END;
        return;
    }
    entry->present = 1;
    p = raw->data;
    entry->record_length = word(p + 8);
    entry->key_length = word(p + 10);
    entry->flags = word(p + 12);
    entry->has_child = (entry->flags & 1) != 0;
    entry->end_marker = (entry->flags & 2) != 0;
    length = entry->record_length;
    if (length < 16 || length > raw->size || (entry->has_child && length < 24))
        entry->issues |= DE_NTFS_INDEX_LENGTH;
    if (length > raw->size)
        entry->issues |= DE_NTFS_INDEX_TRUNCATED;
    if (length & 7)
        entry->issues |= DE_NTFS_INDEX_ALIGNMENT;
    if (entry->flags & ~3U || entry->has_child != children)
        entry->issues |= DE_NTFS_INDEX_FLAGS;
    if (entry->issues)
        return;
    entry->raw.size = length;
    capacity = length - 16 - (entry->has_child ? 8 : 0);
    if (entry->key_length > capacity) {
        entry->issues |= DE_NTFS_INDEX_KEY;
        return;
    }
    entry->key.data = p + 16;
    entry->key.size = entry->key_length;
    entry->padding.data = entry->key.data + entry->key.size;
    entry->padding.size = capacity - entry->key.size;
    if (entry->has_child) {
        de_u64_load_le(p + length - 8, 8, &entry->child_vbn);
        if (entry->child_vbn.limb[3] & 0x8000U)
            entry->issues |= DE_NTFS_INDEX_CHILD;
    }
    if (entry->end_marker) {
        if (entry->key_length || length != raw->size)
            entry->issues |= DE_NTFS_INDEX_END;
    } else {
        de_u64_load_le(p, 8, &entry->segment_reference);
        entry->record_number = entry->segment_reference;
        entry->record_number.limb[3] = 0;
        entry->sequence = entry->segment_reference.limb[3];
        if (!entry->sequence)
            entry->issues |= DE_NTFS_INDEX_REFERENCE;
        de_ntfs_filename_read(&entry->key, major, minor, &entry->filename);
        if (entry->filename.issues || !entry->filename.envelope_valid)
            entry->issues |= DE_NTFS_INDEX_KEY;
    }
    entry->envelope_valid = !entry->issues;
}

int de_ntfs_index_next(de_ntfs_index_cursor *cursor, de_ntfs_index_entry *out) {
    de_ntfs_index_cursor next;
    de_ntfs_index_entry value;
    de_view raw;
    if (!cursor || !out || (!cursor->value.data && cursor->value.size) ||
        cursor->offset > cursor->value.size || !cursor->limit ||
        cursor->limit > DE_NTFS_MAX_ITEMS || cursor->count > cursor->limit || cursor->major != 3 ||
        cursor->minor > 1 || (cursor->has_children != 0 && cursor->has_children != 1))
        return DE_INVALID;
    if (cursor->stopped || cursor->terminated)
        return DE_EMPTY;
    next = *cursor;
    raw = cursor->value;
    if (cursor->offset)
        raw.data += cursor->offset;
    raw.size -= cursor->offset;
    if (!raw.size || cursor->count == cursor->limit) {
        memset(&value, 0, sizeof(value));
        value.raw = raw;
        value.issues = raw.size ? DE_NTFS_INDEX_BUDGET : DE_NTFS_INDEX_END;
        next.stopped = 1;
    } else {
        decode(&raw, cursor->has_children, cursor->major, cursor->minor, &value);
        if (value.present)
            ++next.count;
        if (value.envelope_valid) {
            next.offset += value.record_length;
            next.terminated = value.end_marker;
        } else
            next.stopped = 1;
    }
    next.issues |= value.issues;
    *cursor = next;
    *out = value;
    return DE_OK;
}
