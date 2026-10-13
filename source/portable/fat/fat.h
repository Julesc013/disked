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
typedef struct de_fat_cell_request {
    de_u64 offset;
    de_u32 bytes;
} de_fat_cell_request;

#define DE_FAT_HEADER_TRUNCATED 0x01UL
#define DE_FAT_HEADER_MEDIA 0x02UL
#define DE_FAT_HEADER_ZERO 0x04UL
#define DE_FAT_HEADER_ONE 0x08UL
typedef struct de_fat_header {
    de_view raw;
    de_u32 issues, raw_zero, raw_one, zero, one;
    int fields_present, flags_supported, clean_shutdown, no_io_error;
} de_fat_header;

#define DE_FAT_FSINFO_TRUNCATED 0x01UL
#define DE_FAT_FSINFO_SIGNATURE 0x02UL
#define DE_FAT_FSINFO_RESERVED 0x04UL
#define DE_FAT_FSINFO_COUNT 0x08UL
#define DE_FAT_FSINFO_NEXT 0x10UL
typedef struct de_fat_fsinfo {
    de_view raw;
    de_u32 issues, lead_signature, structure_signature, trail_signature;
    de_u32 free_count, next_free, reserved_nonzero;
    int fields_present, free_count_known, next_free_known;
} de_fat_fsinfo;

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

/* Private in-process continuation. Caller keeps this object and its disjoint
   bitmap together, unmodified between calls. Not a serialized/source token. */
#define DE_FAT_WALK_PENDING (-1)
typedef struct de_fat_walk {
    unsigned char *visited;
    size_t visited_bytes;
    de_u32 cluster_count, current, count;
    int bits, running, disposition;
} de_fat_walk;
typedef struct de_fat_walk_step {
    de_fat_entry entry;
    de_u32 cluster, ordinal;
    int entry_present;
} de_fat_walk_step;

#define DE_FAT_DIR_TRUNCATED 0x0001UL
#define DE_FAT_DIR_ATTRIBUTES 0x0002UL
#define DE_FAT_DIR_CASE 0x0004UL
#define DE_FAT_DIR_CLUSTER 0x0008UL
#define DE_FAT_DIR_FILE_STATE 0x0010UL
#define DE_FAT_DIR_TIME 0x0020UL
#define DE_FAT_DIR_ORDINAL 0x0040UL
#define DE_FAT_DIR_SLOT 0x0080UL
#define DE_FAT_DIR_NAME 0x0100UL
#define DE_FAT_LFN_TRUNCATED 0x0001UL
#define DE_FAT_LFN_ORDINAL 0x0002UL
#define DE_FAT_LFN_SLOT 0x0004UL
#define DE_FAT_LFN_CHECKSUM 0x0008UL
#define DE_FAT_LFN_SHORT_ENTRY 0x0010UL
#define DE_FAT_LFN_PADDING 0x0020UL
#define DE_FAT_LFN_LENGTH 0x0040UL
#define DE_FAT_LFN_UTF16 0x0080UL
#define DE_FAT_LFN_CHARACTERS 0x0100UL
#define DE_FAT_LFN_NONCANONICAL 0x0200UL
#define DE_FAT_LFN_MAX_SLOTS 20U
#define DE_FAT_LFN_MAX_UNITS 260U

enum de_fat_dirent_kind {
    DE_FAT_DIRENT_UNKNOWN,
    DE_FAT_DIRENT_END,
    DE_FAT_DIRENT_DELETED,
    DE_FAT_DIRENT_FILE,
    DE_FAT_DIRENT_DIRECTORY,
    DE_FAT_DIRENT_VOLUME,
    DE_FAT_DIRENT_LONG,
    DE_FAT_DIRENT_INVALID
};
typedef struct de_fat_dirent {
    de_view raw, name_field;
    de_u32 issues, raw_cluster, cluster, file_bytes;
    unsigned short creation_time, creation_date, access_date, write_time, write_date;
    unsigned short lfn_units[13];
    unsigned char attributes, case_flags, creation_fraction, ordinal, checksum, lfn_type;
    int kind, dot, lead_byte_escape;
} de_fat_dirent;
typedef struct de_fat_lfn {
    de_view raw_slots, raw_short;
    de_u32 issues;
    size_t slots, unit_count, name_length;
    unsigned short units[DE_FAT_LFN_MAX_UNITS];
    int associated, unicode_valid, canonical_name, terminated, requires_escaping;
} de_fat_lfn;

#ifdef __cplusplus
extern "C" {
#endif
/* Error statuses do not publish output. Content issues publish raw observations.
   Caller owns disjoint input/output and keeps borrowed bytes immutable. */
int de_fat_volume_read(const de_view *boot, const de_u64 *available_bytes, de_fat_volume *out);
/* Exact header maximum is 3/4/8 bytes; short content publishes observations.
   Recorded driver flags are not current health or recovery authority. */
int de_fat_header_read(const de_view *header, int bits, unsigned char media, de_fat_header *out);
/* FAT32 advisory sector: preserve unknown sentinels and original bytes. Fixed
   fields require512 bytes; a missing declared-sector tail is still truncated. */
int de_fat_fsinfo_read(const de_view *sector, de_u32 sector_bytes, de_u32 cluster_count,
                       de_fat_fsinfo *out);
/* Type/count come from independently established geometry; copy choice is
   explicit. This reads one cell, not a complete or reconciled allocation map. */
int de_fat_entry_read(const de_view *fat, int bits, de_u32 cluster_count, de_u32 index,
                      de_fat_entry *out);
/* Streamable table-relative request and exact-cell decode; no resident FAT needed.
   Type/count/index remain independently established inputs. Errors preserve output. */
int de_fat_entry_request(int bits, de_u32 cluster_count, de_u32 index, de_fat_cell_request *out);
int de_fat_cell_read(const de_view *cell, int bits, de_u32 cluster_count, de_u32 index,
                     de_fat_entry *out);
/* Workspace has capacity >= budget, budget in 1..DE_FAT_MAX_CHAIN. Prefix cells
   [0,count) are published for all content dispositions; the remainder is untouched.
   Known cycles take precedence over a budget for the next unseen cluster. */
int de_fat_chain_read(const de_view *fat, int bits, de_u32 cluster_count, de_u32 start,
                      de_u32 *workspace, size_t capacity, size_t budget, de_fat_chain *out);
/* No whole-chain step cap. Nonempty valid starts need ceil(cluster_count/8)
   addressable bitmap bytes; clear only that prefix. Refusal changes nothing. */
int de_fat_walk_init(int bits, de_u32 cluster_count, de_u32 start,
                     unsigned char *visited, size_t capacity, de_fat_walk *out);
/* Request is repeatable and does not advance. Feed consumes just that cell.
   A short cell publishes one terminal truncated observation; an overlong cell
   or invalid argument changes nothing. Completed cursors refuse further feeds.
   Each successful feed publishes a unique cluster; cycles span all pages. */
int de_fat_walk_request(const de_fat_walk *walk, de_fat_cell_request *out);
int de_fat_walk_feed(de_fat_walk *walk, const de_view *cell, de_fat_walk_step *out);
/* Exactly one borrowed record; short content is an observation, not a live entry.
   Unknown OEM encoding stays raw; dot values 1/2 observe names, not path traversal. */
int de_fat_dirent_read(const de_view *record, int bits, de_fat_dirent *out);
int de_fat_short_checksum(const de_view *stored_name, unsigned char *out);
/* Caller supplies a complete contiguous reverse-ordered set immediately before
   its short record. Pure correlation is not provider/lookup/file-access authority. */
int de_fat_lfn_read(const de_view *slots, const de_view *short_record, int bits, de_fat_lfn *out);
/* ASCII display of original units, including malformed UTF-16; not a lookup key.
   Disjoint output remains unchanged on invalid/budget/capacity failure. */
int de_fat_name_display(const unsigned short *units, size_t count, char *out, size_t capacity);
#ifdef __cplusplus
}
#endif
#endif
