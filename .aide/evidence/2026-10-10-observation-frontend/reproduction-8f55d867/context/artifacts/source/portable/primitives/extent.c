#include "extent.h"
#include <string.h>

static int space_valid(const de_block_space *space)
{
    if (!space || !space->name || !space->name_length || space->name_length > 128 ||
        memchr(space->name, '\0', space->name_length)) return DE_INVALID;
    if (!space->logical_block_bytes || space->logical_block_bytes > 1048576UL) return DE_UNIT;
    return DE_OK;
}
int de_space_init(const char *name, size_t name_length, const de_u64 *blocks, de_u32 unit, de_block_space *out)
{
    de_block_space candidate;
    int status;
    candidate.name = name; candidate.name_length = name_length;
    candidate.blocks = *blocks; candidate.logical_block_bytes = unit;
    status = space_valid(&candidate);
    if (status) return status;
    *out = candidate;
    return DE_OK;
}
int de_space_from_bytes(const char *name, size_t name_length, const de_u64 *bytes, de_u32 unit, de_block_space *out)
{
    de_block_space candidate;
    de_u64 count, remainder, divisor = de_u64_from_u32(unit), zero = {{0, 0, 0, 0}};
    int status = de_space_init(name, name_length, &zero, unit, &candidate);
    if (status) return status;
    status = de_u64_divmod(bytes, &divisor, &count, &remainder);
    if (status) return status;
    if (de_u64_compare(&remainder, &zero)) return DE_ALIGNMENT;
    candidate.blocks = count; *out = candidate;
    return DE_OK;
}
int de_extent_make(const de_block_space *space, const de_u64 *start, const de_u64 *length, de_block_extent *out)
{
    de_block_extent candidate;
    de_u64 zero = {{0, 0, 0, 0}};
    int status = space_valid(space);
    if (status) return status;
    if (!de_u64_compare(length, &zero)) return DE_EMPTY;
    status = de_u64_add(start, length, &candidate.end);
    if (status) return status;
    if (de_u64_compare(&candidate.end, &space->blocks) > 0) return DE_BOUNDS;
    candidate.space = space; candidate.start = *start; *out = candidate;
    return DE_OK;
}
int de_extent_from_inclusive(const de_block_space *space, const de_u64 *start, const de_u64 *last, de_block_extent *out)
{
    de_u64 end, length, one = {{1, 0, 0, 0}};
    int status = space_valid(space);
    if (status) return status;
    if (de_u64_compare(last, start) < 0) return DE_UNDERFLOW;
    status = de_u64_add(last, &one, &end);
    if (status) return status;
    de_u64_sub(&end, start, &length);
    return de_extent_make(space, start, &length, out);
}
static int extent_valid(const de_block_extent *extent)
{
    int status = space_valid(extent->space);
    if (status) return status;
    if (de_u64_compare(&extent->start, &extent->end) >= 0) return DE_EMPTY;
    if (de_u64_compare(&extent->end, &extent->space->blocks) > 0) return DE_BOUNDS;
    return DE_OK;
}
int de_extent_length(const de_block_extent *extent, de_u64 *out)
{
    int status = extent_valid(extent);
    if (status) return status;
    return de_u64_sub(&extent->end, &extent->start, out);
}
int de_extent_to_bytes(const de_block_extent *extent, de_byte_extent *out)
{
    de_byte_extent candidate;
    de_u64 unit;
    int status = extent_valid(extent);
    if (status) return status;
    unit = de_u64_from_u32(extent->space->logical_block_bytes);
    status = de_u64_mul(&extent->start, &unit, &candidate.start);
    if (status) return status;
    status = de_u64_mul(&extent->end, &unit, &candidate.end);
    if (status) return status;
    candidate.space = extent->space; *out = candidate;
    return DE_OK;
}
static int same_space(const de_block_extent *a, const de_block_extent *b)
{
    int status = extent_valid(a);
    if (status) return status;
    status = extent_valid(b);
    if (status) return status;
    return a->space == b->space ? DE_OK : DE_SPACE;
}
int de_extent_overlap(const de_block_extent *a, const de_block_extent *b, int *out)
{
    int status = same_space(a, b);
    if (status) return status;
    *out = de_u64_compare(&a->start, &b->end) < 0 && de_u64_compare(&b->start, &a->end) < 0;
    return DE_OK;
}
int de_extent_contains(const de_block_extent *outer, const de_block_extent *inner, int *out)
{
    int status = same_space(outer, inner);
    if (status) return status;
    *out = de_u64_compare(&outer->start, &inner->start) <= 0 && de_u64_compare(&outer->end, &inner->end) >= 0;
    return DE_OK;
}
