#include "ntfs.h"
#include <string.h>

static int zero(const de_u64 *n) {
    return !(n->limb[0] || n->limb[1] || n->limb[2] || n->limb[3]);
}
static void unpack(const unsigned char *p, unsigned int width, int extend, de_u64 *out) {
    unsigned char bytes[8];
    memset(bytes, extend ? 255 : 0, sizeof(bytes));
    memcpy(bytes, p, width);
    de_u64_load_le(bytes, 8, out);
}
int de_ntfs_runs_begin(const de_view *pairs, const de_u64 *first_vcn, const de_u64 *count,
                       const de_u64 *volume_clusters, int allow_sparse, unsigned int limit,
                       de_ntfs_run_cursor *out) {
    de_ntfs_run_cursor value;
    int status;
    if (!pairs || !first_vcn || !count || !volume_clusters || !out ||
        (!pairs->data && pairs->size) || zero(volume_clusters) ||
        (allow_sparse != 0 && allow_sparse != 1))
        return DE_INVALID;
    if (pairs->size > DE_NTFS_MAX_RECORD || !limit || limit > DE_NTFS_MAX_ITEMS)
        return DE_BOUNDS;
    memset(&value, 0, sizeof(value));
    status = de_u64_add(first_vcn, count, &value.end_vcn);
    if (status)
        return status;
    value.pairs = *pairs;
    value.next_vcn = *first_vcn;
    value.volume_clusters = *volume_clusters;
    value.allow_sparse = allow_sparse;
    value.limit = limit;
    *out = value;
    return DE_OK;
}

int de_ntfs_runs_next(de_ntfs_run_cursor *cursor, de_ntfs_run *out) {
    de_ntfs_run_cursor next;
    de_ntfs_run value;
    de_u64 delta, maximum, magnitude, one, difference;
    const unsigned char *p;
    size_t remaining, bytes;
    unsigned char header;
    if (!cursor || !out || (!cursor->pairs.data && cursor->pairs.size) ||
        cursor->pairs.size > DE_NTFS_MAX_RECORD || cursor->offset > cursor->pairs.size ||
        !cursor->limit || cursor->limit > DE_NTFS_MAX_ITEMS || cursor->count > cursor->limit)
        return DE_INVALID;
    if (cursor->terminated || cursor->stopped)
        return DE_EMPTY;
    next = *cursor;
    memset(&value, 0, sizeof(value));
    value.vcn = cursor->next_vcn;
    value.raw.data = cursor->pairs.data;
    if (cursor->offset)
        value.raw.data += cursor->offset;
    remaining = value.raw.size = cursor->pairs.size - cursor->offset;
    if (!remaining) {
        value.issues = DE_NTFS_RUN_TRUNCATED;
        goto stop;
    }
    p = value.raw.data;
    header = p[0];
    if (!header) {
        value.raw.size = 1;
        value.end_marker = 1;
        next.terminated = 1;
        if (de_u64_compare(&cursor->next_vcn, &cursor->end_vcn))
            value.issues = DE_NTFS_RUN_COVERAGE;
        goto publish;
    }
    if (cursor->count == cursor->limit) {
        value.issues = DE_NTFS_RUN_BUDGET;
        goto stop;
    }
    value.present = 1;
    value.length_width = header & 15;
    value.offset_width = header >> 4;
    if (!value.length_width || value.length_width > 8 || value.offset_width > 8) {
        value.issues = DE_NTFS_RUN_WIDTH;
        goto stop;
    }
    bytes = 1 + (size_t)value.length_width + value.offset_width;
    if (bytes > remaining) {
        value.issues = DE_NTFS_RUN_TRUNCATED;
        goto stop;
    }
    value.raw.size = bytes;
    unpack(p + 1, value.length_width, 0, &value.length);
    if (zero(&value.length) || (p[value.length_width] & 128)) {
        value.issues = DE_NTFS_RUN_LENGTH;
        goto stop;
    }
    if (de_u64_add(&cursor->next_vcn, &value.length, &value.next_vcn)) {
        value.issues = DE_NTFS_RUN_OVERFLOW;
        goto stop;
    }
    if (de_u64_compare(&value.next_vcn, &cursor->end_vcn) > 0) {
        value.issues = DE_NTFS_RUN_COVERAGE;
        goto stop;
    }
    value.sparse = value.offset_width == 0;
    if (value.sparse) {
        if (!cursor->allow_sparse) {
            value.issues = DE_NTFS_RUN_SPARSE;
            goto stop;
        }
    } else {
        p += 1 + value.length_width;
        value.negative_delta = (p[value.offset_width - 1] & 128) != 0;
        unpack(p, value.offset_width, value.negative_delta, &delta);
        if (value.negative_delta) {
            maximum.limb[0] = maximum.limb[1] = maximum.limb[2] = maximum.limb[3] = 65535U;
            one = de_u64_from_u32(1);
            de_u64_sub(&maximum, &delta, &difference);
            de_u64_add(&difference, &one, &magnitude);
            if (de_u64_sub(&cursor->previous_lcn, &magnitude, &value.lcn)) {
                value.issues = DE_NTFS_RUN_RANGE;
                goto stop;
            }
        } else if (de_u64_add(&cursor->previous_lcn, &delta, &value.lcn)) {
            value.issues = DE_NTFS_RUN_OVERFLOW;
            goto stop;
        }
        if (de_u64_add(&value.lcn, &value.length, &value.lcn_end)) {
            value.issues = DE_NTFS_RUN_OVERFLOW;
            goto stop;
        }
        if (de_u64_compare(&value.lcn_end, &cursor->volume_clusters) > 0) {
            value.issues = DE_NTFS_RUN_RANGE;
            goto stop;
        }
        next.previous_lcn = value.lcn;
    }
    value.valid = 1;
    next.offset += bytes;
    next.next_vcn = value.next_vcn;
    ++next.count;
    goto publish;
stop:
    next.stopped = 1;
publish:
    next.issues |= value.issues;
    *cursor = next;
    *out = value;
    return DE_OK;
}
