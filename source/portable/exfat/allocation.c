#include "exfat.h"
#include <string.h>

static de_u32 little32(const unsigned char *p) {
    return (de_u32)p[0] | ((de_u32)p[1] << 8) | ((de_u32)p[2] << 16) | ((de_u32)p[3] << 24);
}
int de_exfat_bitmap_read(const de_view *record, de_u32 clusters, unsigned int cluster_shift,
                         unsigned int fat_count, de_exfat_bitmap *out) {
    de_exfat_bitmap value;
    de_u64 count, size;
    size_t i;
    if (!record || !out || (!record->data && record->size) || !clusters ||
        clusters > DE_EXFAT_MAX_CLUSTERS || cluster_shift < 9 || cluster_shift > 25 ||
        (fat_count != 1 && fat_count != 2))
        return DE_INVALID;
    if (record->size != 32)
        return DE_BOUNDS;
    memset(&value, 0, sizeof(value));
    value.raw = *record;
    value.identifier = record->data[1] & 1;
    value.first_cluster = little32(record->data + 20);
    de_u64_load_le(record->data + 24, 8, &value.data_length);
    value.minimum_bytes = de_u64_from_u32(clusters / 8 + (clusters % 8 != 0));
    count = de_u64_from_u32(clusters);
    size = de_u64_from_u32((de_u32)1 << cluster_shift);
    de_u64_mul(&count, &size, &value.heap_bytes);
    if (record->data[0] != 0x81)
        value.issues |= DE_EXFAT_DIR_TYPE;
    if (value.identifier >= fat_count)
        value.issues |= DE_EXFAT_DIR_FLAGS;
    if (record->data[1] & ~1U)
        value.issues |= DE_EXFAT_DIR_RESERVED;
    for (i = 2; i < 20; ++i)
        if (record->data[i])
            value.issues |= DE_EXFAT_DIR_RESERVED;
    if (value.first_cluster < 2 || value.first_cluster > clusters + 1)
        value.issues |= DE_EXFAT_DIR_CLUSTER;
    if (de_u64_compare(&value.data_length, &value.minimum_bytes) < 0 ||
        de_u64_compare(&value.data_length, &value.heap_bytes) > 0)
        value.issues |= DE_EXFAT_DIR_LENGTH;
    value.valid = !(value.issues & ~DE_EXFAT_DIR_RESERVED);
    *out = value;
    return DE_OK;
}

int de_exfat_bitmap_count(const de_view *window, const de_u64 *byte_offset,
                          const de_u64 *data_length, de_u32 clusters, de_u32 first_cluster,
                          de_u32 count, de_u32 bit_budget, de_exfat_bitmap_interval *out) {
    de_exfat_bitmap_interval value;
    de_u64 length, end, minimum, first, last, relative;
    de_u32 bit, last_bit, i;
    size_t at;
    if (!window || !byte_offset || !data_length || !out || (!window->data && window->size) ||
        !clusters || clusters > DE_EXFAT_MAX_CLUSTERS || first_cluster < 2 ||
        first_cluster > clusters + 1 || !count || count > clusters + 2 - first_cluster)
        return DE_INVALID;
    if (window->size > 8192 || count > bit_budget)
        return DE_BOUNDS;
    minimum = de_u64_from_u32(clusters / 8 + (clusters % 8 != 0));
    if (de_u64_compare(data_length, &minimum) < 0)
        return DE_INVALID;
    de_u64_from_size(window->size, &length);
    if (de_u64_add(byte_offset, &length, &end))
        return DE_OVERFLOW;
    if (de_u64_compare(&end, data_length) > 0)
        return DE_BOUNDS;
    bit = first_cluster - 2;
    last_bit = bit + count - 1;
    first = de_u64_from_u32(bit / 8);
    last = de_u64_from_u32(last_bit / 8);
    if (de_u64_compare(&first, byte_offset) < 0 || de_u64_compare(&last, &end) >= 0)
        return DE_BOUNDS;
    de_u64_sub(&first, byte_offset, &relative);
    if (de_u64_to_size(&relative, &at))
        return DE_BOUNDS;
    memset(&value, 0, sizeof(value));
    value.first_cluster = first_cluster;
    value.cluster_count = count;
    value.first_byte = first;
    value.last_byte = last;
    for (i = 0; i < count; ++i) {
        if (window->data[at] & (1U << (bit & 7)))
            ++value.unavailable;
        else
            ++value.available;
        ++bit;
        if (!(bit & 7))
            ++at;
    }
    *out = value;
    return DE_OK;
}
