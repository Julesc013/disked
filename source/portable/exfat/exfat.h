#ifndef DISKED_EXFAT_H
#define DISKED_EXFAT_H
#include "portable/primitives/view.h"

/* Private supplied-byte metadata observations; no host or writer authority. */
#define DE_EXFAT_TRUNCATED 0x0001UL
#define DE_EXFAT_SIGNATURE 0x0002UL
#define DE_EXFAT_NAME 0x0004UL
#define DE_EXFAT_ZERO 0x0008UL
#define DE_EXFAT_SECTOR 0x0010UL
#define DE_EXFAT_CLUSTER 0x0020UL
#define DE_EXFAT_REVISION 0x0040UL
#define DE_EXFAT_FLAGS 0x0080UL
#define DE_EXFAT_PERCENT 0x0100UL
#define DE_EXFAT_REGIONS 0x0200UL
#define DE_EXFAT_COUNTERS 0x0400UL
#define DE_EXFAT_TABLE_SIZE 0x0800UL
#define DE_EXFAT_ROOT 0x1000UL
#define DE_EXFAT_CAPACITY 0x2000UL
#define DE_EXFAT_OVERFLOW 0x4000UL
#define DE_EXFAT_CHECKSUM 0x8000UL
#define DE_EXFAT_EXTENDED 0x10000UL
#define DE_EXFAT_RESERVED 0x20000UL
#define DE_EXFAT_MAX_REGION 49152UL
#define DE_EXFAT_MAX_CLUSTERS 4294967285UL

typedef struct de_exfat_boot {
    de_view raw;
    de_u64 partition_offset, volume_sectors, volume_bytes, available_bytes;
    de_u64 fat_bytes, heap_offset_bytes, heap_bytes;
    de_u32 issues, fat_offset, fat_length, heap_offset, cluster_count;
    de_u32 root_cluster, serial, revision, flags, sector_shift, cluster_shift;
    de_u32 fat_count, drive_select, percent_in_use, sector_bytes, cluster_sectors, cluster_bytes;
    de_u32 checksum, checksum_word, checksum_mismatches;
    int fields_present, complete_region, checksum_valid, usable_geometry;
    int backup, mutable_fields_stale, texfat_structure, active_fat_known;
    de_u32 active_fat;
} de_exfat_boot;

enum de_exfat_cell_kind {
    DE_EXFAT_CELL_HEADER,
    DE_EXFAT_CELL_ZERO_UNINTERPRETED,
    DE_EXFAT_CELL_NEXT,
    DE_EXFAT_CELL_BAD,
    DE_EXFAT_CELL_END,
    DE_EXFAT_CELL_INVALID
};
typedef struct de_exfat_cell {
    de_u32 index, value;
    int kind;
} de_exfat_cell;

#ifdef __cplusplus
extern "C" {
#endif
/* backup is exactly 0 (main) or 1 (backup). Borrowed raw bytes are unchanged.
   API errors preserve output; malformed/truncated media returns issue facts. */
int de_exfat_boot_read(const de_view *region, const de_u64 *available, int backup,
                       de_exfat_boot *out);
/* Exactly one supplied little-endian cell, never an allocation/free verdict. */
int de_exfat_cell_read(const de_view *cell, de_u32 clusters, de_u32 index, de_exfat_cell *out);
#ifdef __cplusplus
}
#endif
#endif
