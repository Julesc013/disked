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
