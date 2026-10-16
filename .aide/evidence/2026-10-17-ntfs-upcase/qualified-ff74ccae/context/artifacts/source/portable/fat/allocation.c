#include "fat.h"
#include <string.h>

static int shape(int bits, de_u32 clusters) {
    return (bits == 12 && clusters >= 1 && clusters < 4085) ||
           (bits == 16 && clusters >= 4085 && clusters < 65525) ||
           (bits == 32 && clusters >= 65525 && clusters <= 268435445UL);
}

int de_fat_entry_request(int bits, de_u32 clusters, de_u32 index, de_fat_cell_request *out) {
    de_fat_cell_request value;
    de_u32 offset;
    if (!out || !shape(bits, clusters))
        return DE_INVALID;
    if (index > clusters + 1)
        return DE_BOUNDS;
    memset(&value, 0, sizeof(value));
    offset = bits == 12 ? index + index / 2 : index * (de_u32)(bits / 8);
    value.offset = de_u64_from_u32(offset);
    value.bytes = bits == 32 ? 4 : 2;
    *out = value;
    return DE_OK;
}

int de_fat_cell_read(const de_view *cell, int bits, de_u32 clusters, de_u32 index,
                     de_fat_entry *out) {
    de_fat_entry value;
    de_u32 mask;
    de_u64 raw;
    de_fat_cell_request request;
    int status;
    if (!cell || !out || (!cell->data && cell->size))
        return DE_INVALID;
    status = de_fat_entry_request(bits, clusters, index, &request);
    if (status)
        return status;
    if (cell->size != request.bytes)
        return DE_BOUNDS;
    status = de_view_read_uint(cell, 0, request.bytes, DE_LITTLE_ENDIAN, &raw);
    if (status)
        return status;
    memset(&value, 0, sizeof(value));
    value.index = index;
    status = de_u64_to_u32(&raw, &value.raw_value);
    if (status)
        return status;
    mask = bits == 12 ? 0xfffUL : (bits == 16 ? 0xffffUL : 0x0fffffffUL);
    value.value = bits == 12 && (index & 1) ? value.raw_value >> 4 : value.raw_value;
    value.value &= mask;
    if (index < 2)
        value.kind = DE_FAT_ENTRY_HEADER;
    else if (!value.value)
        value.kind = DE_FAT_ENTRY_FREE;
    else if (value.value >= mask - 7)
        value.kind = DE_FAT_ENTRY_END;
    else if (value.value == mask - 8)
        value.kind = DE_FAT_ENTRY_BAD;
    else if (value.value >= 2 && value.value <= clusters + 1)
        value.kind = DE_FAT_ENTRY_NEXT;
    else
        value.kind = DE_FAT_ENTRY_RESERVED;
    *out = value;
    return DE_OK;
}

int de_fat_entry_read(const de_view *fat, int bits, de_u32 clusters, de_u32 index,
                      de_fat_entry *out) {
    de_fat_cell_request request;
    de_view cell;
    de_u64 length;
    int status;
    if (!fat || !out || (!fat->data && fat->size))
        return DE_INVALID;
    status = de_fat_entry_request(bits, clusters, index, &request);
    if (status)
        return status;
    length = de_u64_from_u32(request.bytes);
    status = de_view_slice_u64(fat, &request.offset, &length, &cell);
    if (status)
        return status;
    return de_fat_cell_read(&cell, bits, clusters, index, out);
}

int de_fat_chain_read(const de_view *fat, int bits, de_u32 clusters, de_u32 start,
                      de_u32 *workspace, size_t capacity, size_t budget, de_fat_chain *out) {
    de_fat_chain value;
    de_fat_entry entry;
    de_u32 current;
    size_t i;
    int status;
    if (!fat || !out || !workspace || (!fat->data && fat->size) || !shape(bits, clusters) ||
        !budget || budget > DE_FAT_MAX_CHAIN)
        return DE_INVALID;
    if (capacity < budget)
        return DE_BUFFER;
    memset(&value, 0, sizeof(value));
    value.terminal_kind = DE_FAT_ENTRY_UNKNOWN;
    current = start;
    value.stopped_cluster = current;
    if (!current)
        value.disposition = DE_FAT_CHAIN_EMPTY;
    else if (current < 2 || current > clusters + 1)
        value.disposition = DE_FAT_CHAIN_INVALID_START;
    else
        for (;;) {
            value.stopped_cluster = current;
            for (i = 0; i < value.count; ++i)
                if (workspace[i] == current)
                    break;
            if (i < value.count) {
                value.disposition = DE_FAT_CHAIN_CYCLE;
                break;
            }
            if (value.count == budget) {
                value.disposition = DE_FAT_CHAIN_BUDGET;
                break;
            }
            workspace[value.count++] = current;
            status = de_fat_entry_read(fat, bits, clusters, current, &entry);
            if (status == DE_BOUNDS || status == DE_WIDTH) {
                value.disposition =
                    status == DE_WIDTH ? DE_FAT_CHAIN_WIDTH : DE_FAT_CHAIN_TRUNCATED;
                value.terminal_kind = DE_FAT_ENTRY_UNKNOWN;
                value.terminal_value = 0;
                break;
            }
            if (status)
                return status;
            value.terminal_kind = entry.kind;
            value.terminal_value = entry.value;
            if (entry.kind == DE_FAT_ENTRY_NEXT) {
                current = entry.value;
                continue;
            }
            value.disposition =
                entry.kind == DE_FAT_ENTRY_END
                    ? DE_FAT_CHAIN_END
                    : (entry.kind == DE_FAT_ENTRY_FREE
                           ? DE_FAT_CHAIN_FREE
                           : (entry.kind == DE_FAT_ENTRY_BAD ? DE_FAT_CHAIN_BAD
                                                             : DE_FAT_CHAIN_RESERVED));
            break;
        }
    *out = value;
    return DE_OK;
}

int de_fat_walk_init(int bits, de_u32 clusters, de_u32 start,
                     unsigned char *visited, size_t capacity, de_fat_walk *out) {
    de_fat_walk value;
    de_u32 needed;
    de_u64 wide;
    size_t addressable;
    int status;
    if (!out || !shape(bits, clusters))
        return DE_INVALID;
    memset(&value, 0, sizeof(value));
    value.bits = bits;
    value.cluster_count = clusters;
    value.current = start;
    if (!start)
        value.disposition = DE_FAT_CHAIN_EMPTY;
    else if (start < 2 || start > clusters + 1)
        value.disposition = DE_FAT_CHAIN_INVALID_START;
    else {
        needed = clusters / 8 + (clusters % 8 != 0);
        wide = de_u64_from_u32(needed);
        status = de_u64_to_size(&wide, &addressable);
        if (status)
            return status;
        if (capacity < addressable)
            return DE_BUFFER;
        if (!visited)
            return DE_INVALID;
        value.visited = visited;
        value.visited_bytes = addressable;
        value.running = 1;
        value.disposition = DE_FAT_WALK_PENDING;
        memset(visited, 0, value.visited_bytes);
    }
    *out = value;
    return DE_OK;
}

int de_fat_walk_request(const de_fat_walk *walk, de_fat_cell_request *out) {
    if (!walk || !out || !walk->running || !walk->visited ||
        !shape(walk->bits, walk->cluster_count) || walk->current < 2 ||
        walk->current > walk->cluster_count + 1 || walk->count >= walk->cluster_count ||
        walk->visited_bytes != walk->cluster_count / 8 + (walk->cluster_count % 8 != 0))
        return DE_INVALID;
    return de_fat_entry_request(walk->bits, walk->cluster_count, walk->current, out);
}

int de_fat_walk_feed(de_fat_walk *walk, const de_view *cell, de_fat_walk_step *out) {
    de_fat_cell_request request;
    de_fat_walk value;
    de_fat_walk_step step;
    de_u32 bit, next_bit;
    unsigned char mask;
    int status;
    if (!cell || !out || (!cell->data && cell->size))
        return DE_INVALID;
    status = de_fat_walk_request(walk, &request);
    if (status)
        return status;
    if (cell->size > request.bytes)
        return DE_BOUNDS;
    bit = walk->current - 2;
    mask = (unsigned char)(1U << (bit % 8));
    if (walk->visited[bit / 8] & mask)
        return DE_INVALID;
    value = *walk;
    memset(&step, 0, sizeof(step));
    step.cluster = value.current;
    step.ordinal = value.count;
    if (cell->size < request.bytes) {
        value.running = 0;
        value.disposition = DE_FAT_CHAIN_TRUNCATED;
    } else {
        status = de_fat_cell_read(cell, value.bits, value.cluster_count, value.current,
                                  &step.entry);
        if (status)
            return status;
        step.entry_present = 1;
        if (step.entry.kind == DE_FAT_ENTRY_NEXT) {
            value.current = step.entry.value;
            next_bit = value.current - 2;
            if (value.current == step.cluster ||
                (value.visited[next_bit / 8] & (unsigned char)(1U << (next_bit % 8)))) {
                value.running = 0;
                value.disposition = DE_FAT_CHAIN_CYCLE;
            }
        } else {
            value.running = 0;
            value.disposition = step.entry.kind == DE_FAT_ENTRY_END ? DE_FAT_CHAIN_END
                                : step.entry.kind == DE_FAT_ENTRY_FREE ? DE_FAT_CHAIN_FREE
                                : step.entry.kind == DE_FAT_ENTRY_BAD ? DE_FAT_CHAIN_BAD
                                                                    : DE_FAT_CHAIN_RESERVED;
        }
    }
    ++value.count;
    value.visited[bit / 8] |= mask;
    *walk = value;
    *out = step;
    return DE_OK;
}
