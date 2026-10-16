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
static int scaled(const de_u64 *value, de_u32 factor, de_u64 *out) {
    de_u64 multiplier;
    multiplier = de_u64_from_u32(factor);
    return de_u64_mul(value, &multiplier, out);
}
static int nonzero(const de_u64 *value) {
    return value->limb[0] || value->limb[1] || value->limb[2] || value->limb[3];
}
static int record_size(unsigned char code, de_u32 cluster, de_u32 *out, int *known) {
    de_u64 product, factor;
    *known = 0;
    if (code >= 225 && code <= 247) {
        *out = (de_u32)1 << (256U - code);
        *known = 1;
        return 1;
    }
    if (!code || code > 127 || !power_two(code))
        return 0;
    if (!cluster)
        return 1;
    factor = de_u64_from_u32(code);
    if (scaled(&factor, cluster, &product) || de_u64_to_u32(&product, out))
        return 0;
    *known = 1;
    return 1;
}

int de_ntfs_boot_read(const de_view *raw, const de_u64 *available, unsigned int major,
                      unsigned int minor, de_ntfs_boot *out) {
    de_ntfs_boot value;
    const unsigned char *p;
    de_u64 unit, divisor, remainder, mft_end, mirror_end, product;
    de_u32 geometry_errors;
    size_t i;
    int sector_known, geometry_supported, addresses, geometry_overflow;
    if (!raw || !available || !out || (!raw->data && raw->size))
        return DE_INVALID;
    if (raw->size > 4096)
        return DE_BOUNDS;
    memset(&value, 0, sizeof(value));
    geometry_overflow = 0;
    value.raw = *raw;
    value.available_bytes = *available;
    if (major != 3 || minor > 1)
        value.issues |= DE_NTFS_BOOT_VERSION;
    if (raw->size < 512) {
        value.issues |= DE_NTFS_BOOT_TRUNCATED;
        *out = value;
        return DE_OK;
    }
    p = raw->data;
    value.fields_present = 1;
    if (memcmp(p + 3, "NTFS    ", 8))
        value.issues |= DE_NTFS_BOOT_OEM;
    value.bytes_per_sector = word(p + 11);
    value.cluster_code = p[13];
    value.media_type = p[21];
    value.sectors_per_track = word(p + 24);
    value.heads = word(p + 26);
    value.hidden_sectors = dword(p + 28);
    de_u64_load_le(p + 40, 8, &value.sector_field);
    de_u64_load_le(p + 48, 8, &value.mft_lcn);
    de_u64_load_le(p + 56, 8, &value.mirror_lcn);
    value.record_code = p[64];
    value.index_code = p[68];
    de_u64_load_le(p + 72, 8, &value.serial);
    value.checksum = dword(p + 80);
    value.marker = word(p + 510);
    if (value.marker != 0xaa55)
        value.issues |= DE_NTFS_BOOT_MARKER;
    for (i = 0; i < 80; i += 4)
        value.calculated_checksum += dword(p + i);
    value.checksum_present = value.checksum != 0;
    value.checksum_matches = value.checksum_present && value.checksum == value.calculated_checksum;
    if (value.checksum_present && !value.checksum_matches)
        value.issues |= DE_NTFS_BOOT_CHECKSUM;
    for (i = 14; i < 36; ++i)
        if ((i <= 20 || i == 22 || i == 23 || i >= 32) && p[i])
            value.issues |= DE_NTFS_BOOT_BPB;
    sector_known = value.bytes_per_sector >= 512 && value.bytes_per_sector <= 4096 &&
                   power_two(value.bytes_per_sector);
    if (!sector_known)
        value.issues |= DE_NTFS_BOOT_SECTOR;
    else if (raw->size != value.bytes_per_sector) {
        value.issues |= DE_NTFS_BOOT_LENGTH;
        if (raw->size < value.bytes_per_sector)
            value.issues |= DE_NTFS_BOOT_TRUNCATED;
    } else
        value.complete_sector = 1;
    if (value.cluster_code && value.cluster_code <= 128 && power_two(value.cluster_code))
        value.sectors_per_cluster = value.cluster_code;
    else if (value.cluster_code >= 244)
        value.sectors_per_cluster = (de_u32)1 << (256U - value.cluster_code);
    else
        value.issues |= DE_NTFS_BOOT_CLUSTER;
    if (sector_known && value.sectors_per_cluster) {
        unit = de_u64_from_u32(value.bytes_per_sector);
        if (scaled(&unit, value.sectors_per_cluster, &product) ||
            de_u64_to_u32(&product, &value.cluster_bytes)) {
            value.issues |= DE_NTFS_BOOT_OVERFLOW;
            geometry_overflow = 1;
        }
    }
    geometry_supported = value.cluster_bytes && value.cluster_bytes <= DE_NTFS_MAX_CLUSTER;
    if (value.cluster_bytes > DE_NTFS_MAX_CLUSTER)
        value.issues |= DE_NTFS_BOOT_UNSUPPORTED;
    if (!record_size(value.record_code, value.cluster_bytes, &value.record_bytes,
                     &value.record_size_known))
        value.issues |= DE_NTFS_BOOT_RECORD;
    if (!record_size(value.index_code, value.cluster_bytes, &value.index_bytes,
                     &value.index_size_known))
        value.issues |= DE_NTFS_BOOT_INDEX;
    value.record_budget_supported =
        value.record_size_known && value.record_bytes <= DE_NTFS_MAX_RECORD;
    if (value.record_size_known && !value.record_budget_supported)
        value.issues |= DE_NTFS_BOOT_UNSUPPORTED;
    if (!nonzero(&value.sector_field))
        value.issues |= DE_NTFS_BOOT_SIZE;
    if (sector_known) {
        if (scaled(&value.sector_field, value.bytes_per_sector, &value.data_bytes)) {
            value.issues |= DE_NTFS_BOOT_OVERFLOW;
            geometry_overflow = 1;
        } else {
            value.data_bound_known = 1;
            unit = de_u64_from_u32(value.bytes_per_sector);
            if (de_u64_add(&value.data_bytes, &unit, &value.media_span_bytes)) {
                value.issues |= DE_NTFS_BOOT_OVERFLOW;
                geometry_overflow = 1;
            } else {
                value.media_span_known = 1;
                if (de_u64_compare(&value.media_span_bytes, available) > 0)
                    value.issues |= DE_NTFS_BOOT_CAPACITY;
            }
        }
    }
    if (value.sectors_per_cluster) {
        divisor = de_u64_from_u32(value.sectors_per_cluster);
        de_u64_divmod(&value.sector_field, &divisor, &value.clusters, &remainder);
        if (!nonzero(&value.clusters))
            value.issues |= DE_NTFS_BOOT_SIZE;
    }
    addresses = 0;
    if (value.cluster_bytes && value.record_size_known && value.data_bound_known) {
        addresses = 1;
        if (scaled(&value.mft_lcn, value.cluster_bytes, &value.mft0_offset)) {
            value.issues |= DE_NTFS_BOOT_OVERFLOW;
            addresses = 0;
        } else
            value.mft0_offset_known = 1;
        if (scaled(&value.mirror_lcn, value.cluster_bytes, &value.mirror0_offset)) {
            value.issues |= DE_NTFS_BOOT_OVERFLOW;
            addresses = 0;
        } else
            value.mirror0_offset_known = 1;
        unit = de_u64_from_u32(value.record_bytes);
        if (addresses) {
            if (de_u64_add(&value.mft0_offset, &unit, &mft_end) ||
                de_u64_add(&value.mirror0_offset, &unit, &mirror_end)) {
                value.issues |= DE_NTFS_BOOT_OVERFLOW;
                addresses = 0;
            } else {
                unit = de_u64_from_u32(value.bytes_per_sector);
                if (de_u64_compare(&value.mft_lcn, &value.clusters) >= 0 ||
                    de_u64_compare(&value.mirror_lcn, &value.clusters) >= 0 ||
                    de_u64_compare(&mft_end, &value.data_bytes) > 0 ||
                    de_u64_compare(&mirror_end, &value.data_bytes) > 0 ||
                    de_u64_compare(&value.mft0_offset, &unit) < 0 ||
                    de_u64_compare(&value.mirror0_offset, &unit) < 0 ||
                    (de_u64_compare(&value.mft0_offset, &mirror_end) < 0 &&
                     de_u64_compare(&value.mirror0_offset, &mft_end) < 0))
                    addresses = 0;
            }
        }
        if (!addresses)
            value.issues |= DE_NTFS_BOOT_ADDRESS;
    }
    value.seed_addresses_valid = addresses;
    geometry_errors = DE_NTFS_BOOT_TRUNCATED | DE_NTFS_BOOT_OEM | DE_NTFS_BOOT_SECTOR |
                      DE_NTFS_BOOT_CLUSTER | DE_NTFS_BOOT_BPB | DE_NTFS_BOOT_SIZE |
                      DE_NTFS_BOOT_CAPACITY | DE_NTFS_BOOT_VERSION | DE_NTFS_BOOT_LENGTH;
    value.geometry_valid =
        geometry_supported && !geometry_overflow && !(value.issues & geometry_errors);
    value.bootstrap_usable = value.geometry_valid && value.record_budget_supported && addresses;
    *out = value;
    return DE_OK;
}
