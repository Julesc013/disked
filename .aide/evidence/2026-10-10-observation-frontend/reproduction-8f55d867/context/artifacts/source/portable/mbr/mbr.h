#ifndef DISKED_MBR_H
#define DISKED_MBR_H
#include "view.h"
#include "extent.h"

/* Internal borrowed observation API. No packed structs or on-disk ABI. */
#define DE_MBR_SIGNATURE 1U
#define DE_MBR_BOOT 2U
#define DE_MBR_INACTIVE 4U
#define DE_MBR_RANGE 8U
#define DE_MBR_OVERLAP 16U
#define DE_MBR_PROTECTIVE 32U
#define DE_MBR_HYBRID 64U
#define DE_MBR_CHS 128U
#define DE_MBR_TRUNCATED 256U
#define DE_MBR_LAYOUT 512U
#define DE_MBR_CYCLE 1024U
#define DE_MBR_BUDGET 2048U
#define DE_MBR_METADATA 4096U
#define DE_MBR_UNAVAILABLE 8192U

enum de_mbr_kind { DE_MBR_UNUSED, DE_MBR_DATA, DE_MBR_EXTENDED, DE_MBR_GPT };
typedef struct de_mbr_geometry { unsigned short heads, sectors; } de_mbr_geometry;
typedef struct de_mbr_entry {
    unsigned char raw[16];
    de_u64 relative_start, blocks;
    de_block_extent extent;
    int active, kind, range_valid;
    unsigned int chs_compared;
    de_u32 issues;
} de_mbr_entry;
typedef struct de_mbr_table {
    de_view raw;
    de_mbr_entry entries[4];
    int signature;
    de_u32 issues;
} de_mbr_table;

#ifdef __cplusplus
extern "C" {
#endif
int de_mbr_read(const de_view *bytes, const de_block_space *space,
                const de_mbr_geometry *geometry, de_mbr_table *out);
/* Shared private decoding helpers for the EBR reader. */
int de_mbr_geometry_valid(const de_mbr_geometry *geometry);
int de_mbr_decode(const de_view *bytes, const de_block_space *space, de_mbr_table *out);
void de_mbr_resolve(const de_block_space *space, const de_u64 *base,
                    const de_mbr_geometry *geometry, de_mbr_entry *entry);
int de_mbr_nonzero(const unsigned char *data, size_t size);
#ifdef __cplusplus
}
#endif
#endif
