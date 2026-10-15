#ifndef DISKED_NTFS_H
#define DISKED_NTFS_H
#include "portable/primitives/view.h"

/* Private NTFS3 supplied-byte envelopes; no filesystem or source authority.
 * Views borrow stable original bytes. API/control/result objects must be valid
 * and disjoint from those byte spans. No public ABI or hostile C-caller boundary.
 */
#define DE_NTFS_MAX_RECORD 49152U
#define DE_NTFS_STRIDE 512U
#define DE_NTFS_TRUNCATED 0x0001UL
#define DE_NTFS_LENGTH 0x0002UL
#define DE_NTFS_SIGNATURE 0x0004UL
#define DE_NTFS_VERSION 0x0008UL
#define DE_NTFS_USA_OFFSET 0x0010UL
#define DE_NTFS_USA_COUNT 0x0020UL
#define DE_NTFS_TORN 0x0040UL
#define DE_NTFS_HEADER 0x0080UL

#define DE_NTFS_BOOT_TRUNCATED 0x0001UL
#define DE_NTFS_BOOT_OEM 0x0002UL
#define DE_NTFS_BOOT_SECTOR 0x0004UL
#define DE_NTFS_BOOT_CLUSTER 0x0008UL
#define DE_NTFS_BOOT_BPB 0x0010UL
#define DE_NTFS_BOOT_RECORD 0x0020UL
#define DE_NTFS_BOOT_INDEX 0x0040UL
#define DE_NTFS_BOOT_SIZE 0x0080UL
#define DE_NTFS_BOOT_ADDRESS 0x0100UL
#define DE_NTFS_BOOT_CAPACITY 0x0200UL
#define DE_NTFS_BOOT_OVERFLOW 0x0400UL
#define DE_NTFS_BOOT_VERSION 0x0800UL
#define DE_NTFS_BOOT_UNSUPPORTED 0x1000UL
#define DE_NTFS_BOOT_MARKER 0x2000UL
#define DE_NTFS_BOOT_CHECKSUM 0x4000UL
#define DE_NTFS_BOOT_LENGTH 0x8000UL
#define DE_NTFS_MAX_CLUSTER 2097152UL

typedef struct de_ntfs_boot {
    de_view raw;
    de_u64 available_bytes, sector_field, mft_lcn, mirror_lcn, serial;
    de_u64 data_bytes, media_span_bytes, clusters, mft0_offset, mirror0_offset;
    de_u32 issues, sectors_per_cluster, cluster_bytes, record_bytes, index_bytes;
    de_u32 checksum, calculated_checksum, hidden_sectors;
    unsigned short bytes_per_sector, marker, sectors_per_track, heads;
    unsigned char cluster_code, record_code, index_code, media_type;
    int fields_present, complete_sector, data_bound_known, media_span_known;
    int record_size_known, index_size_known, record_budget_supported;
    int mft0_offset_known, mirror0_offset_known, seed_addresses_valid;
    int checksum_present, checksum_matches, geometry_valid, bootstrap_usable;
} de_ntfs_boot;

typedef struct de_ntfs_record {
    de_view raw;
    de_u64 log_sequence, base_reference;
    de_u32 issues, used_bytes, allocated_bytes;
    unsigned short usa_offset, usa_count, update_sequence, sequence;
    unsigned short links, attribute_offset, flags, next_attribute_id;
    unsigned int strides, mismatched_tails;
    int fields_present, fixups_valid, envelope_valid;
    int in_use, name_index_present;
} de_ntfs_record;

#ifdef __cplusplus
extern "C" {
#endif
int de_ntfs_boot_read(const de_view *raw, const de_u64 *available, unsigned int major,
                      unsigned int minor, de_ntfs_boot *out);
int de_ntfs_record_read(const de_view *raw, unsigned int major, unsigned int minor,
                        de_ntfs_record *out);
/* Validate before writing. Source and written output spans must be disjoint. */
int de_ntfs_record_restore(const de_view *raw, unsigned int major, unsigned int minor,
                           const de_buffer *output, de_ntfs_record *out);
#ifdef __cplusplus
}
#endif
#endif
