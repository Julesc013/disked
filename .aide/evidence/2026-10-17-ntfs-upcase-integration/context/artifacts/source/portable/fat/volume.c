#include "fat.h"
#include <string.h>

/* Called only after the complete fixed 512-byte metadata prefix is present. */
static de_u32 u16(const unsigned char *p) {
    return (de_u32)p[0] | ((de_u32)p[1] << 8);
}

static de_u32 u32(const unsigned char *p) {
    return u16(p) | (u16(p + 2) << 16);
}

static int multiply(de_u32 a, de_u32 b, de_u64 *out) {
    de_u64 left, right;
    left = de_u64_from_u32(a);
    right = de_u64_from_u32(b);
    return de_u64_mul(&left, &right, out);
}

int de_fat_volume_read(const de_view *boot, const de_u64 *available, de_fat_volume *out) {
    de_fat_volume value;
    const unsigned char *p;
    de_u32 short_total, long_total, short_fat, required_bytes, entries, i;
    de_u64 overhead, root, reserved, combined, required;
    int status, info_present, backup_present;
    if (!boot || !available || !out || (!boot->data && boot->size))
        return DE_INVALID;
    /* Reject overlong views before even consulting an inaccessible input. */
    if (boot->size > 4096)
        return DE_BOUNDS;
    memset(&value, 0, sizeof(value));
    value.raw = *boot;
    value.available_bytes = *available;
    if (boot->size < 512) {
        value.issues = DE_FAT_TRUNCATED;
        *out = value;
        return DE_OK;
    }
    p = boot->data;
    value.bytes_per_sector = u16(p + 11);
    value.sectors_per_cluster = p[13];
    value.reserved_sectors = u16(p + 14);
    value.fat_count = p[16];
    value.root_entries = u16(p + 17);
    short_total = u16(p + 19);
    long_total = u32(p + 32);
    short_fat = u16(p + 22);
    value.fat_sectors = short_fat ? short_fat : u32(p + 36);
    value.total_sectors = short_total ? short_total : long_total;
    if (p[510] != 0x55 || p[511] != 0xaa)
        value.issues |= DE_FAT_SIGNATURE;
    if (value.bytes_per_sector != 512 && value.bytes_per_sector != 1024 &&
        value.bytes_per_sector != 2048 && value.bytes_per_sector != 4096)
        value.issues |= DE_FAT_SECTOR;
    else {
        if (boot->size > value.bytes_per_sector)
            return DE_BOUNDS;
        if (boot->size < value.bytes_per_sector)
            value.issues |= DE_FAT_TRUNCATED;
    }
    if (!value.sectors_per_cluster || value.sectors_per_cluster > 128 ||
        (value.sectors_per_cluster & (value.sectors_per_cluster - 1)))
        value.issues |= DE_FAT_CLUSTER;
    if ((short_total && long_total) || !value.total_sectors)
        value.issues |= DE_FAT_COUNTERS;
    if (!value.reserved_sectors || !value.fat_count || !value.fat_sectors)
        value.issues |= DE_FAT_REGIONS;
    if (value.issues & (DE_FAT_SECTOR | DE_FAT_CLUSTER | DE_FAT_REGIONS)) {
        *out = value;
        return DE_OK;
    }
    value.cluster_bytes = value.bytes_per_sector * value.sectors_per_cluster;
    value.root_sectors =
        (value.root_entries * 32 + value.bytes_per_sector - 1) / value.bytes_per_sector;
    status = multiply(value.fat_count, value.fat_sectors, &overhead);
    if (status)
        return status;
    root = de_u64_from_u32(value.root_sectors);
    reserved = de_u64_from_u32(value.reserved_sectors);
    status = de_u64_add(&overhead, &root, &combined);
    if (status)
        return status;
    status = de_u64_add(&combined, &reserved, &overhead);
    if (status)
        return status;
    status = multiply(value.total_sectors, value.bytes_per_sector, &value.volume_bytes);
    if (status)
        return status;
    status = multiply(value.fat_sectors, value.bytes_per_sector, &value.fat_bytes);
    if (status)
        return status;
    if (de_u64_compare(&value.volume_bytes, available) > 0)
        value.issues |= DE_FAT_CAPACITY;
    combined = de_u64_from_u32(value.total_sectors);
    if (de_u64_compare(&overhead, &combined) >= 0) {
        value.issues |= DE_FAT_REGIONS;
        *out = value;
        return DE_OK;
    }
    status = de_u64_to_u32(&overhead, &value.first_data_sector);
    if (status)
        return status;
    status = multiply(value.first_data_sector, value.bytes_per_sector, &value.data_offset_bytes);
    if (status)
        return status;
    value.data_sectors = value.total_sectors - value.first_data_sector;
    value.cluster_count = value.data_sectors / value.sectors_per_cluster;
    if (!value.cluster_count || value.cluster_count > 268435445UL) {
        value.issues |= DE_FAT_TYPE_SHAPE;
        *out = value;
        return DE_OK;
    }
    value.bits = value.cluster_count < 4085 ? 12 : (value.cluster_count < 65525 ? 16 : 32);
    entries = value.cluster_count + 2;
    required_bytes = value.bits == 12 ? (entries * 3 + 1) / 2 : entries * (de_u32)(value.bits / 8);
    required = de_u64_from_u32(required_bytes);
    if (de_u64_compare(&value.fat_bytes, &required) < 0)
        value.issues |= DE_FAT_TABLE_SIZE;
    if (value.bits != 32) {
        if (!short_fat || !value.root_entries || (value.root_entries * 32) % value.bytes_per_sector)
            value.issues |= DE_FAT_TYPE_SHAPE;
    } else {
        if (short_fat || value.root_entries)
            value.issues |= DE_FAT_TYPE_SHAPE;
        value.flags = u16(p + 40);
        value.version = u16(p + 42);
        value.root_cluster = u32(p + 44);
        value.fsinfo_sector = u16(p + 48);
        value.backup_sector = u16(p + 50);
        value.mirrored = !(value.flags & 0x80);
        if (value.version)
            value.issues |= DE_FAT_VERSION;
        if ((value.flags & ~0x008fUL) || (!value.mirrored && (value.flags & 15) >= value.fat_count))
            value.issues |= DE_FAT_FLAGS;
        if (value.root_cluster < 2 || value.root_cluster > value.cluster_count + 1)
            value.issues |= DE_FAT_ROOT;
        info_present = value.fsinfo_sector != 65535UL;
        backup_present = value.backup_sector != 0 && value.backup_sector != 65535UL;
        if ((info_present &&
             (!value.fsinfo_sector || value.fsinfo_sector >= value.reserved_sectors)) ||
            (backup_present && value.backup_sector >= value.reserved_sectors) ||
            (info_present && backup_present && value.fsinfo_sector == value.backup_sector))
            value.issues |= DE_FAT_AUXILIARY;
        for (i = 52; i < 64; ++i)
            if (p[i])
                value.issues |= DE_FAT_RESERVED;
    }
    value.usable_layout = !value.issues;
    *out = value;
    return DE_OK;
}
