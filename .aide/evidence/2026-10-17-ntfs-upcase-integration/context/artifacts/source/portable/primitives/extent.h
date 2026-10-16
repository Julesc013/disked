#ifndef DISKED_PRIMITIVE_EXTENT_H
#define DISKED_PRIMITIVE_EXTENT_H
#include "checked.h"
/* Caller owns immutable space/name for the lifetime of every borrowing extent. */
typedef struct de_block_space {
    const char *name;
    size_t name_length;
    de_u64 blocks;
    de_u32 logical_block_bytes;
} de_block_space;
typedef struct de_block_extent { const de_block_space *space; de_u64 start, end; } de_block_extent;
typedef struct de_byte_extent { const de_block_space *space; de_u64 start, end; } de_byte_extent;
#ifdef __cplusplus
extern "C" {
#endif
int de_space_init(const char *name, size_t name_length, const de_u64 *blocks, de_u32 unit, de_block_space *out);
int de_space_from_bytes(const char *name, size_t name_length, const de_u64 *bytes, de_u32 unit, de_block_space *out);
int de_extent_make(const de_block_space *space, const de_u64 *start, const de_u64 *length, de_block_extent *out);
int de_extent_from_inclusive(const de_block_space *space, const de_u64 *start, const de_u64 *last, de_block_extent *out);
int de_extent_length(const de_block_extent *extent, de_u64 *out);
int de_extent_to_bytes(const de_block_extent *extent, de_byte_extent *out);
int de_extent_overlap(const de_block_extent *a, const de_block_extent *b, int *out);
int de_extent_contains(const de_block_extent *outer, const de_block_extent *inner, int *out);
#ifdef __cplusplus
}
#endif
#endif
