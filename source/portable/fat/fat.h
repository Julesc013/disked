#ifndef DISKED_FAT_H
#define DISKED_FAT_H
#include "portable/primitives/view.h"

/* Private borrowed metadata observations; no host I/O or admitted SDK ABI. */
#define DE_FAT_TRUNCATED 0x0001UL
#define DE_FAT_SIGNATURE 0x0002UL
#define DE_FAT_SECTOR 0x0004UL
#define DE_FAT_CLUSTER 0x0008UL
#define DE_FAT_COUNTERS 0x0010UL
#define DE_FAT_REGIONS 0x0020UL
#define DE_FAT_CAPACITY 0x0040UL
#define DE_FAT_TABLE_SIZE 0x0080UL
#define DE_FAT_TYPE_SHAPE 0x0100UL
#define DE_FAT_VERSION 0x0200UL
#define DE_FAT_FLAGS 0x0400UL
#define DE_FAT_ROOT 0x0800UL
#define DE_FAT_AUXILIARY 0x1000UL
#define DE_FAT_RESERVED 0x2000UL
#define DE_FAT_MAX_CHAIN 1024U

typedef struct de_fat_volume {
    de_view raw;
    de_u64 available_bytes, volume_bytes, fat_bytes, data_offset_bytes;
    de_u32 issues, bytes_per_sector, sectors_per_cluster, reserved_sectors;
    de_u32 fat_count, fat_sectors, total_sectors, root_entries, root_sectors;
    de_u32 first_data_sector, data_sectors, cluster_count, cluster_bytes;
    de_u32 root_cluster, flags, version, fsinfo_sector, backup_sector;
    int bits, usable_layout, mirrored;
} de_fat_volume;

enum de_fat_entry_kind {
    DE_FAT_ENTRY_UNKNOWN,
    DE_FAT_ENTRY_HEADER,
    DE_FAT_ENTRY_FREE,
    DE_FAT_ENTRY_NEXT,
    DE_FAT_ENTRY_RESERVED,
    DE_FAT_ENTRY_BAD,
    DE_FAT_ENTRY_END
};
typedef struct de_fat_entry {
    de_u32 index, raw_value, value;
    int kind;
} de_fat_entry;

enum de_fat_chain_disposition {
    DE_FAT_CHAIN_EMPTY,
    DE_FAT_CHAIN_END,
    DE_FAT_CHAIN_FREE,
    DE_FAT_CHAIN_BAD,
    DE_FAT_CHAIN_RESERVED,
    DE_FAT_CHAIN_INVALID_START,
    DE_FAT_CHAIN_CYCLE,
    DE_FAT_CHAIN_TRUNCATED,
    DE_FAT_CHAIN_BUDGET,
    DE_FAT_CHAIN_WIDTH
};
typedef struct de_fat_chain {
    size_t count;
    de_u32 stopped_cluster, terminal_value;
    int disposition, terminal_kind;
} de_fat_chain;

#ifdef __cplusplus
extern "C" {
#endif
/* Error statuses do not publish output. Content issues publish raw observations.
   Caller owns disjoint input/output and keeps borrowed bytes immutable. */
int de_fat_volume_read(const de_view *boot, const de_u64 *available_bytes, de_fat_volume *out);
/* Type/count come from independently established geometry; copy choice is
   explicit. This reads one cell, not a complete or reconciled allocation map. */
int de_fat_entry_read(const de_view *fat, int bits, de_u32 cluster_count, de_u32 index,
                      de_fat_entry *out);
/* Workspace has capacity >= budget, budget in 1..DE_FAT_MAX_CHAIN. Prefix cells
   [0,count) are published for all content dispositions; the remainder is untouched.
   Known cycles take precedence over a budget for the next unseen cluster. */
int de_fat_chain_read(const de_view *fat, int bits, de_u32 cluster_count, de_u32 start,
                      de_u32 *workspace, size_t capacity, size_t budget, de_fat_chain *out);
#ifdef __cplusplus
}
#endif
#endif
