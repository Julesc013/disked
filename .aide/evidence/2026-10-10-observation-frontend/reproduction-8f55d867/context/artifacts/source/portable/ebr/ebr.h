#ifndef DISKED_EBR_H
#define DISKED_EBR_H
#include "mbr.h"
#define DE_EBR_LIMIT 128
typedef struct de_ebr_node { de_u64 lba; de_mbr_table table; } de_ebr_node;
typedef struct de_ebr_walk {
    de_block_extent container;
    de_mbr_geometry geometry;
    de_ebr_node *nodes;
    size_t count, limit;
    de_u64 pending;
    de_u32 issues;
    int needs_block, complete;
} de_ebr_walk;
#ifdef __cplusplus
extern "C" {
#endif
int de_ebr_init(const de_mbr_table *mbr, unsigned int slot,
                const de_mbr_geometry *geometry, de_ebr_node *nodes,
                size_t capacity, size_t limit, de_ebr_walk *out);
/* Call only with the exact pending LBA; all input borrows stay immutable/alive. */
int de_ebr_feed(de_ebr_walk *walk, const de_u64 *lba, const de_view *bytes);
int de_ebr_unavailable(de_ebr_walk *walk);
#ifdef __cplusplus
}
#endif
#endif
