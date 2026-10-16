#include "exfat.h"
#include <string.h>

static de_u32 le16(const unsigned char *p) {
    return (de_u32)p[0] | ((de_u32)p[1] << 8);
}
static de_u32 le32(const unsigned char *p) {
    return le16(p) | (le16(p + 2) << 16);
}
static int product(de_u32 a, de_u32 b, de_u64 *out) {
    de_u64 left, right;
    left = de_u64_from_u32(a);
    right = de_u64_from_u32(b);
    return de_u64_mul(&left, &right, out);
}

int de_exfat_boot_read(const de_view *region, const de_u64 *available, int backup,
                       de_exfat_boot *out) {
    de_exfat_boot value;
    const unsigned char *p;
    de_u64 sectors, overhead, heap, required, divisor, quotient, remainder, limit;
    de_u32 expected_clusters, i;
    size_t bytes, at;
    if (!region || !available || !out || (!region->data && region->size) ||
        (backup != 0 && backup != 1))
        return DE_INVALID;
    if (region->size > DE_EXFAT_MAX_REGION)
        return DE_BOUNDS;
    memset(&value, 0, sizeof(value));
    value.raw = *region;
    value.available_bytes = *available;
    value.backup = backup;
    value.mutable_fields_stale = backup;
    if (region->size < 512) {
        value.issues = DE_EXFAT_TRUNCATED;
        *out = value;
        return DE_OK;
    }
    p = region->data;
    value.fields_present = 1;
    de_u64_load_le(p + 64, 8, &value.partition_offset);
    de_u64_load_le(p + 72, 8, &value.volume_sectors);
    value.fat_offset = le32(p + 80);
    value.fat_length = le32(p + 84);
    value.heap_offset = le32(p + 88);
    value.cluster_count = le32(p + 92);
    value.root_cluster = le32(p + 96);
    value.serial = le32(p + 100);
    value.revision = le16(p + 104);
    value.flags = le16(p + 106);
    value.sector_shift = p[108];
    value.cluster_shift = p[109];
    value.fat_count = p[110];
    value.drive_select = p[111];
    value.percent_in_use = p[112];
    if (p[0] != 0xeb || p[1] != 0x76 || p[2] != 0x90 || p[510] != 0x55 || p[511] != 0xaa)
        value.issues |= DE_EXFAT_SIGNATURE;
    if (memcmp(p + 3, "EXFAT   ", 8))
        value.issues |= DE_EXFAT_NAME;
    for (i = 11; i < 64; ++i)
        if (p[i])
            value.issues |= DE_EXFAT_ZERO;
    for (i = 113; i < 120; ++i)
        if (p[i])
            value.issues |= DE_EXFAT_RESERVED;
    if (value.revision != 0x100)
        value.issues |= DE_EXFAT_REVISION;
    if ((value.flags & ~15UL) || (value.fat_count == 1 && (value.flags & 1)))
        value.issues |= DE_EXFAT_FLAGS;
    if (value.percent_in_use > 100 && value.percent_in_use != 255)
        value.issues |= DE_EXFAT_PERCENT;
    if (value.fat_count != 1 && value.fat_count != 2)
        value.issues |= DE_EXFAT_REGIONS;
    value.texfat_structure = value.fat_count == 2;
    value.active_fat = value.flags & 1;
    if (value.sector_shift < 9 || value.sector_shift > 12) {
        value.issues |= DE_EXFAT_SECTOR;
        *out = value;
        return DE_OK;
    }
    value.sector_bytes = (de_u32)1 << value.sector_shift;
    bytes = (size_t)value.sector_bytes * 12;
    if (region->size > bytes)
        return DE_BOUNDS;
    if (region->size < bytes)
        value.issues |= DE_EXFAT_TRUNCATED;
    else {
        value.complete_region = 1;
        for (at = 0; at < (size_t)value.sector_bytes * 11; ++at) {
            if (at == 106 || at == 107 || at == 112)
                continue;
            value.checksum = (value.checksum >> 1) | ((value.checksum & 1) ? 0x80000000UL : 0);
            value.checksum += p[at];
        }
        value.checksum_word = le32(p + (size_t)value.sector_bytes * 11);
        for (at = (size_t)value.sector_bytes * 11; at < bytes; at += 4)
            if (le32(p + at) != value.checksum)
                ++value.checksum_mismatches;
        value.checksum_valid = value.checksum_mismatches == 0;
        if (!value.checksum_valid)
            value.issues |= DE_EXFAT_CHECKSUM;
        for (i = 1; i <= 8; ++i)
            if (le32(p + (size_t)value.sector_bytes * (i + 1) - 4) != 0xaa550000UL)
                value.issues |= DE_EXFAT_EXTENDED;
        for (at = (size_t)value.sector_bytes * 10; at < (size_t)value.sector_bytes * 11; ++at)
            if (p[at])
                value.issues |= DE_EXFAT_RESERVED;
    }
    if (value.cluster_shift > 25 - value.sector_shift) {
        value.issues |= DE_EXFAT_CLUSTER;
        *out = value;
        return DE_OK;
    }
    value.cluster_sectors = (de_u32)1 << value.cluster_shift;
    value.cluster_bytes = (de_u32)1 << (value.cluster_shift + value.sector_shift);
    divisor = de_u64_from_u32(value.sector_bytes);
    if (de_u64_mul(&value.volume_sectors, &divisor, &value.volume_bytes))
        value.issues |= DE_EXFAT_OVERFLOW;
    else if (de_u64_compare(&value.volume_bytes, available) > 0)
        value.issues |= DE_EXFAT_CAPACITY;
    limit = de_u64_from_u32(1048576UL >> value.sector_shift);
    if (de_u64_compare(&value.volume_sectors, &limit) < 0)
        value.issues |= DE_EXFAT_COUNTERS;
    product(value.fat_length, value.sector_bytes, &value.fat_bytes);
    product(value.heap_offset, value.sector_bytes, &value.heap_offset_bytes);
    product(value.cluster_count, value.cluster_bytes, &value.heap_bytes);
    product(value.fat_length, value.fat_count, &overhead);
    limit = de_u64_from_u32(value.fat_offset);
    de_u64_add(&overhead, &limit, &overhead);
    heap = de_u64_from_u32(value.heap_offset);
    if (value.fat_offset < 24 || !value.fat_length || de_u64_compare(&overhead, &heap) > 0 ||
        de_u64_compare(&heap, &value.volume_sectors) >= 0)
        value.issues |= DE_EXFAT_REGIONS;
    if (!value.cluster_count || value.cluster_count > DE_EXFAT_MAX_CLUSTERS)
        value.issues |= DE_EXFAT_COUNTERS;
    else {
        product(value.cluster_count + 2, 4, &required);
        if (de_u64_compare(&value.fat_bytes, &required) < 0)
            value.issues |= DE_EXFAT_TABLE_SIZE;
    }
    if (de_u64_compare(&heap, &value.volume_sectors) < 0) {
        de_u64_sub(&value.volume_sectors, &heap, &sectors);
        divisor = de_u64_from_u32(value.cluster_sectors);
        de_u64_divmod(&sectors, &divisor, &quotient, &remainder);
        limit = de_u64_from_u32(DE_EXFAT_MAX_CLUSTERS);
        if (de_u64_compare(&quotient, &limit) > 0)
            expected_clusters = DE_EXFAT_MAX_CLUSTERS;
        else
            de_u64_to_u32(&quotient, &expected_clusters);
        if (value.cluster_count != expected_clusters)
            value.issues |= DE_EXFAT_COUNTERS;
    }
    if (value.root_cluster < 2 || value.cluster_count > DE_EXFAT_MAX_CLUSTERS ||
        value.root_cluster > value.cluster_count + 1)
        value.issues |= DE_EXFAT_ROOT;
    value.usable_geometry = !value.issues;
    value.active_fat_known = !backup && value.usable_geometry;
    *out = value;
    return DE_OK;
}

int de_exfat_cell_read(const de_view *cell, de_u32 clusters, de_u32 index, de_exfat_cell *out) {
    de_exfat_cell value;
    if (!cell || !out || (!cell->data && cell->size) || !clusters ||
        clusters > DE_EXFAT_MAX_CLUSTERS || index > clusters + 1)
        return DE_INVALID;
    if (cell->size != 4)
        return DE_BOUNDS;
    value.index = index;
    value.value = le32(cell->data);
    value.kind = DE_EXFAT_CELL_INVALID;
    if (index < 2)
        value.kind = DE_EXFAT_CELL_HEADER;
    else if (!value.value)
        value.kind = DE_EXFAT_CELL_ZERO_UNINTERPRETED;
    else if (value.value == 0xffffffffUL)
        value.kind = DE_EXFAT_CELL_END;
    else if (value.value == 0xfffffff7UL)
        value.kind = DE_EXFAT_CELL_BAD;
    else if (value.value >= 2 && value.value <= clusters + 1)
        value.kind = DE_EXFAT_CELL_NEXT;
    *out = value;
    return DE_OK;
}
