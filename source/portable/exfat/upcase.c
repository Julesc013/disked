#include "exfat.h"
#include <string.h>

static de_u32 le32(const unsigned char *p) {
    return (de_u32)p[0] | ((de_u32)p[1] << 8) | ((de_u32)p[2] << 16) | ((de_u32)p[3] << 24);
}
int de_exfat_upcase_descriptor_read(const de_view *record, de_u32 clusters,
                                    unsigned int cluster_shift, de_exfat_upcase_descriptor *out) {
    de_exfat_upcase_descriptor value;
    de_u64 count, size, maximum, zero;
    size_t i;
    if (!record || !out || (!record->data && record->size) || !clusters ||
        clusters > DE_EXFAT_MAX_CLUSTERS || cluster_shift < 9 || cluster_shift > 25)
        return DE_INVALID;
    if (record->size != 32)
        return DE_BOUNDS;
    memset(&value, 0, sizeof(value));
    value.raw = *record;
    value.table_checksum = le32(record->data + 4);
    value.first_cluster = le32(record->data + 20);
    de_u64_load_le(record->data + 24, 8, &value.data_length);
    count = de_u64_from_u32(clusters);
    size = de_u64_from_u32((de_u32)1 << cluster_shift);
    de_u64_mul(&count, &size, &value.heap_bytes);
    maximum = de_u64_from_u32(262144UL);
    zero = de_u64_from_u32(0);
    if (record->data[0] != 0x82)
        value.issues |= DE_EXFAT_DIR_TYPE;
    for (i = 1; i < 20; ++i)
        if ((i < 4 || i >= 8) && record->data[i])
            value.issues |= DE_EXFAT_DIR_RESERVED;
    if (value.first_cluster < 2 || value.first_cluster > clusters + 1)
        value.issues |= DE_EXFAT_DIR_CLUSTER;
    if (!de_u64_compare(&value.data_length, &zero) || (value.data_length.limb[0] & 1) ||
        de_u64_compare(&value.data_length, &maximum) > 0 ||
        de_u64_compare(&value.data_length, &value.heap_bytes) > 0)
        value.issues |= DE_EXFAT_DIR_LENGTH;
    value.valid = !(value.issues & ~DE_EXFAT_DIR_RESERVED);
    *out = value;
    return DE_OK;
}

int de_exfat_upcase_init(de_u32 length, de_u32 checksum, int compressed, de_exfat_upcase *out) {
    de_exfat_upcase value;
    if (!out || (compressed != 0 && compressed != 1) || !length || (length & 1) ||
        (!compressed && length != 131072UL) || (compressed && length > 262144UL))
        return DE_INVALID;
    memset(&value, 0, sizeof(value));
    value.length = length;
    value.expected_checksum = checksum;
    value.compressed = compressed;
    *out = value;
    return DE_OK;
}
static void emit(de_exfat_upcase *value, unsigned short n, unsigned short *out, de_u32 *emitted) {
    de_u32 expected = value->mapped;
    if (expected < 128) {
        if (expected >= 97 && expected <= 122)
            expected -= 32;
        if (n != expected)
            value->issues |= DE_EXFAT_UPCASE_ASCII;
    }
    if (out)
        out[*emitted] = n;
    ++*emitted;
    ++value->mapped;
}
static int feed(de_exfat_upcase *value, const de_view *chunk, de_u32 mapping_budget,
                unsigned short *out, size_t capacity, de_exfat_upcase_step *step) {
    size_t i;
    de_u32 emitted = 0;
    unsigned int word;
    step->first_mapping = value->mapped;
    while (value->pending_identity && emitted < mapping_budget) {
        if (out && emitted >= capacity)
            return DE_BUFFER;
        emit(value, (unsigned short)value->mapped, out, &emitted);
        --value->pending_identity;
    }
    if (value->pending_identity && chunk->size)
        return DE_BOUNDS;
    for (i = 0; i < chunk->size; ++i) {
        value->checksum = (value->checksum >> 1) | ((value->checksum & 1) ? 0x80000000UL : 0);
        value->checksum += chunk->data[i];
        ++value->consumed;
        if (!value->half_word) {
            value->low_byte = chunk->data[i];
            value->half_word = 1;
            continue;
        }
        word = value->low_byte | ((unsigned int)chunk->data[i] << 8);
        value->half_word = 0;
        if (value->issues & DE_EXFAT_UPCASE_FORMAT)
            continue;
        if (value->mapped >= 65536UL) {
            value->issues |= DE_EXFAT_UPCASE_FORMAT;
            continue;
        }
        if (value->need_count) {
            value->need_count = 0;
            if (!word || word > 65536UL - value->mapped) {
                value->issues |= DE_EXFAT_UPCASE_FORMAT;
                continue;
            }
            value->pending_identity = word;
            while (value->pending_identity && emitted < mapping_budget) {
                if (out && emitted >= capacity)
                    return DE_BUFFER;
                emit(value, (unsigned short)value->mapped, out, &emitted);
                --value->pending_identity;
            }
            if (value->pending_identity && i + 1 < chunk->size)
                return DE_BOUNDS;
        } else if (value->compressed && word == 65535U && value->mapped < 65535UL)
            value->need_count = 1;
        else {
            if (emitted >= mapping_budget)
                return DE_BOUNDS;
            if (out && emitted >= capacity)
                return DE_BUFFER;
            emit(value, (unsigned short)word, out, &emitted);
        }
    }
    step->consumed_bytes = (de_u32)chunk->size;
    step->emitted_mappings = emitted;
    return DE_OK;
}
int de_exfat_upcase_feed(de_exfat_upcase *state, const de_view *chunk, de_u32 offset,
                         de_u32 byte_budget, de_u32 mapping_budget, unsigned short *mappings,
                         size_t capacity, de_exfat_upcase_step *step) {
    de_exfat_upcase candidate, actual;
    de_exfat_upcase_step result;
    int code;
    if (!state || !chunk || !step || (!chunk->data && chunk->size) || state->final ||
        offset != state->consumed || state->consumed > state->length || state->mapped > 65536UL ||
        (!mappings && capacity) || state->pending_identity > 65536UL - state->mapped ||
        state->low_byte > 255 || (state->half_word != 0 && state->half_word != 1) ||
        (state->need_count != 0 && state->need_count != 1) ||
        (state->compressed != 0 && state->compressed != 1) || !state->length ||
        state->length > 262144UL || (state->length & 1) ||
        (!state->compressed && state->length != 131072UL))
        return DE_INVALID;
    if (chunk->size > 8192 || chunk->size > byte_budget ||
        chunk->size > state->length - state->consumed)
        return DE_BOUNDS;
    candidate = *state;
    memset(&result, 0, sizeof(result));
    code = feed(&candidate, chunk, mapping_budget, 0, 0, &result);
    if (code)
        return code;
    if (mappings && result.emitted_mappings > capacity)
        return DE_BUFFER;
    actual = *state;
    code = feed(&actual, chunk, mapping_budget, mappings, capacity, &result);
    if (code)
        return code;
    *state = actual;
    *step = result;
    return DE_OK;
}
int de_exfat_upcase_finish(de_exfat_upcase *state) {
    de_exfat_upcase value;
    if (!state || state->final || state->consumed != state->length || state->pending_identity ||
        state->mapped > 65536UL || !state->length || state->length > 262144UL ||
        (state->length & 1) || (state->compressed != 0 && state->compressed != 1) ||
        (!state->compressed && state->length != 131072UL))
        return DE_INVALID;
    value = *state;
    value.final = 1;
    if (value.half_word || value.need_count)
        value.issues |= DE_EXFAT_UPCASE_FORMAT;
    if (value.mapped != 65536UL)
        value.issues |= DE_EXFAT_UPCASE_COUNT;
    if (value.checksum != value.expected_checksum)
        value.issues |= DE_EXFAT_UPCASE_CHECKSUM;
    value.valid = !value.issues;
    *state = value;
    return DE_OK;
}
int de_exfat_name_hash(const unsigned short *mapping, size_t map_count, const unsigned short *units,
                       size_t count, unsigned short *out) {
    de_u32 value = 0, n;
    size_t i;
    if (!mapping || map_count != 65536UL || !units || !count || count > 255 || !out)
        return DE_INVALID;
    for (i = 0; i < count; ++i) {
        n = mapping[units[i]];
        value = (((value >> 1) | ((value & 1) ? 0x8000UL : 0)) + (n & 255)) & 65535UL;
        value = (((value >> 1) | ((value & 1) ? 0x8000UL : 0)) + (n >> 8)) & 65535UL;
    }
    *out = (unsigned short)value;
    return DE_OK;
}
int de_exfat_name_equal(const unsigned short *mapping, size_t map_count, const unsigned short *left,
                        size_t left_count, const unsigned short *right, size_t right_count,
                        int *out) {
    size_t i;
    int equal;
    if (!mapping || map_count != 65536UL || !left || !right || !left_count || !right_count ||
        left_count > 255 || right_count > 255 || !out)
        return DE_INVALID;
    equal = left_count == right_count;
    for (i = 0; equal && i < left_count; ++i)
        if (mapping[left[i]] != mapping[right[i]])
            equal = 0;
    *out = equal;
    return DE_OK;
}
