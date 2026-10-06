#include "gpt.h"
#include <string.h>

de_u32 de_gpt_header_checksum(const de_view *bytes, size_t size);

static int nonzero(const unsigned char *data, size_t size)
{
    size_t i;
    for (i = 0; i < size; ++i) if (data[i]) return 1;
    return 0;
}

static de_u64 field64(const de_view *bytes, size_t offset)
{
    de_u64 value = {{0,0,0,0}};
    de_view_read_uint(bytes, offset, 8, DE_LITTLE_ENDIAN, &value);
    return value;
}

static de_u32 field32(const de_view *bytes, size_t offset)
{
    de_u64 value = {{0,0,0,0}};
    de_u32 result = 0;
    de_view_read_uint(bytes, offset, 4, DE_LITTLE_ENDIAN, &value);
    de_u64_to_u32(&value, &result);
    return result;
}

static int round_blocks(const de_u64 *bytes, de_u32 unit, de_u64 *out)
{
    de_u64 divisor, q, r, zero, one;
    int status;
    divisor = de_u64_from_u32(unit); zero = de_u64_from_u32(0); one = de_u64_from_u32(1);
    status = de_u64_divmod(bytes, &divisor, &q, &r);
    if (status) return status;
    if (de_u64_compare(&r, &zero) && de_u64_add(&q, &one, &q)) return DE_OVERFLOW;
    *out = q; return DE_OK;
}

int de_gpt_header_read(const de_view *bytes, const de_block_space *space,
                       const de_u64 *lba, int role, de_gpt_header *out)
{
    de_gpt_header h;
    de_block_space check;
    de_u64 zero, one, two, last, expected, alternate, unit, count, size;
    de_u64 minimum, reserve, required_first, usable_end, backup_gap;
    size_t block_size;
    if (!bytes || !space || !lba || !out || (!bytes->data && bytes->size) ||
        (role != DE_GPT_PRIMARY && role != DE_GPT_BACKUP)) return DE_INVALID;
    if (de_space_init(space->name, space->name_length, &space->blocks, space->logical_block_bytes, &check) ||
        space->logical_block_bytes < 512) return DE_UNIT;
    zero = de_u64_from_u32(0); one = de_u64_from_u32(1); two = de_u64_from_u32(2);
    if (!de_u64_compare(&space->blocks, &zero) || de_u64_compare(lba, &space->blocks) >= 0) return DE_BOUNDS;
    de_u64_sub(&space->blocks, &one, &last);
    expected = role == DE_GPT_PRIMARY ? one : last;
    alternate = role == DE_GPT_PRIMARY ? last : one;
    if (de_u64_compare(lba, &expected)) return DE_BOUNDS;
    unit = de_u64_from_u32(space->logical_block_bytes);
    if (de_u64_to_size(&unit, &block_size)) return DE_WIDTH;
    if (bytes->size > block_size) return DE_BOUNDS;
    memset(&h, 0, sizeof(h)); h.space = space; h.raw = *bytes; h.role = role; h.observed_lba = *lba;
    if (bytes->size < block_size) { h.issues = DE_GPT_TRUNCATED; *out = h; return DE_OK; }
    if (memcmp(bytes->data, "EFI PART", 8)) { h.issues = DE_GPT_SIGNATURE; *out = h; return DE_OK; }
    h.revision = field32(bytes, 8); h.header_size = field32(bytes, 12); h.header_crc = field32(bytes, 16);
    h.my_lba = field64(bytes, 24); h.alternate_lba = field64(bytes, 32);
    h.first_usable = field64(bytes, 40); h.last_usable = field64(bytes, 48);
    memcpy(h.disk_guid, bytes->data + 56, 16);
    h.array_lba = field64(bytes, 72); h.count = field32(bytes, 80);
    h.entry_size = field32(bytes, 84); h.array_crc = field32(bytes, 88);
    if (h.revision != 0x10000UL) h.issues |= DE_GPT_REVISION;
    if (h.header_size < 92 || h.header_size > space->logical_block_bytes) h.issues |= DE_GPT_HEADER_SIZE;
    else if (de_gpt_header_checksum(bytes, (size_t)h.header_size) != h.header_crc) h.issues |= DE_GPT_HEADER_CRC;
    if (field32(bytes, 20) || nonzero(bytes->data + 92, bytes->size - 92)) h.issues |= DE_GPT_RESERVED;
    if (!nonzero(h.disk_guid, 16)) h.issues |= DE_GPT_ZERO_GUID;
    if (de_u64_compare(&last, &two) < 0 || de_u64_compare(&h.my_lba, &expected) ||
        de_u64_compare(&h.alternate_lba, &alternate)) h.issues |= DE_GPT_LOCATION;
    if (de_u64_compare(&h.first_usable, &one) <= 0 ||
        de_u64_compare(&h.first_usable, &h.last_usable) > 0 ||
        de_u64_compare(&h.last_usable, &last) >= 0) h.issues |= DE_GPT_USABLE;
    if (!h.count || h.entry_size < 128 || (h.entry_size & (h.entry_size - 1))) h.issues |= DE_GPT_ARRAY_SHAPE;
    if (!(h.issues & DE_GPT_ARRAY_SHAPE)) {
        count = de_u64_from_u32(h.count); size = de_u64_from_u32(h.entry_size);
        if (de_u64_mul(&count, &size, &h.array_bytes) ||
            round_blocks(&h.array_bytes, space->logical_block_bytes, &h.array_blocks) ||
            de_extent_make(space, &h.array_lba, &h.array_blocks, &h.array_extent)) h.issues |= DE_GPT_ARRAY_RANGE;
        else {
            if (role == DE_GPT_PRIMARY) {
                if (de_u64_compare(&h.array_lba, &one) <= 0 ||
                    de_u64_compare(&h.array_extent.end, &h.first_usable) > 0) h.issues |= DE_GPT_ARRAY_RANGE;
            } else if (de_u64_compare(&h.array_lba, &h.last_usable) <= 0 ||
                       de_u64_compare(&h.array_extent.end, &last) > 0) h.issues |= DE_GPT_ARRAY_RANGE;
            minimum = de_u64_from_u32(16384);
            round_blocks(&minimum, space->logical_block_bytes, &reserve);
            if (de_u64_compare(&h.array_blocks, &reserve) > 0) reserve = h.array_blocks;
            if (de_u64_add(&two, &reserve, &required_first) ||
                de_u64_compare(&h.first_usable, &required_first) < 0 ||
                de_u64_add(&h.last_usable, &one, &usable_end) ||
                de_u64_sub(&last, &usable_end, &backup_gap) ||
                de_u64_compare(&backup_gap, &reserve) < 0) h.issues |= DE_GPT_USABLE;
        }
    }
    h.consistent = h.issues == 0; *out = h; return DE_OK;
}

int de_gpt_request_array(const de_gpt_header *header, const de_gpt_limits *limits,
                         de_block_extent *out)
{
    de_u64 limit, unit, rounded;
    size_t native_count, native_bytes;
    if (!header || !limits || !out || !header->consistent || !limits->entries ||
        limits->entries > 1024 || limits->entry_bytes < 128 || limits->entry_bytes > 4096 ||
        (limits->entry_bytes & (limits->entry_bytes - 1)) ||
        !limits->array_bytes || limits->array_bytes > 1048576UL) return DE_INVALID;
    limit = de_u64_from_u32(limits->array_bytes);
    if (header->count > limits->entries || header->entry_size > limits->entry_bytes ||
        de_u64_compare(&header->array_bytes, &limit) > 0) return DE_BUFFER;
    unit = de_u64_from_u32(header->space->logical_block_bytes);
    limit = de_u64_from_u32(header->count);
    if (de_u64_mul(&header->array_blocks, &unit, &rounded) ||
        de_u64_to_size(&rounded, &native_bytes) || de_u64_to_size(&limit, &native_count) ||
        native_count > ((size_t)-1) / sizeof(de_gpt_entry)) return DE_WIDTH;
    *out = header->array_extent; return DE_OK;
}

int de_gpt_array_read(const de_gpt_header *header, const de_gpt_limits *limits,
                      const de_view *bytes, de_gpt_entry *entries, size_t capacity,
                      de_gpt_candidate *out)
{
    de_gpt_candidate c;
    de_block_extent request;
    de_u64 unit, rounded;
    de_gpt_entry *entry;
    de_view name;
    size_t count, total, padded, i, j, k;
    de_u32 crc;
    int status, overlap, terminated;
    char name_text[109];
    if (!bytes || !out || (!bytes->data && bytes->size)) return DE_INVALID;
    status = de_gpt_request_array(header, limits, &request);
    if (status) return status;
    count = (size_t)header->count;
    if (!entries || capacity < count) return DE_BUFFER;
    unit = de_u64_from_u32(header->space->logical_block_bytes);
    de_u64_mul(&header->array_blocks, &unit, &rounded);
    de_u64_to_size(&rounded, &padded); de_u64_to_size(&header->array_bytes, &total);
    if (bytes->size > padded) return DE_BOUNDS;
    memset(&c, 0, sizeof(c)); c.header = header; c.raw_array = *bytes; c.entries = entries;
    if (bytes->size < padded) { c.issues = DE_GPT_TRUNCATED; *out = c; return DE_OK; }
    name.data = bytes->data; name.size = total;
    de_gpt_crc32(&name, &crc);
    if (crc != header->array_crc) c.issues |= DE_GPT_ARRAY_CRC;
    if (nonzero(bytes->data + total, padded - total)) c.issues |= DE_GPT_RESERVED;
    for (i = 0; i < count; ++i) {
        entry = &entries[i]; memset(entry, 0, sizeof(*entry));
        /* Product and native-size bounds were established before workspace writes. */
        de_view_slice(bytes, i * (size_t)header->entry_size, (size_t)header->entry_size, &entry->raw);
        entry->active = nonzero(entry->raw.data, 16);
        if (!entry->active) {
            if (nonzero(entry->raw.data, entry->raw.size)) entry->issues |= DE_GPT_UNUSED_DATA;
            c.issues |= entry->issues; continue;
        }
        if (!nonzero(entry->raw.data + 16, 16)) entry->issues |= DE_GPT_ZERO_GUID;
        entry->first = field64(&entry->raw, 32); entry->last = field64(&entry->raw, 40);
        entry->attributes = field64(&entry->raw, 48);
        if (de_extent_from_inclusive(header->space, &entry->first, &entry->last, &entry->extent) ||
            de_u64_compare(&entry->first, &header->first_usable) < 0 ||
            de_u64_compare(&entry->last, &header->last_usable) > 0) entry->issues |= DE_GPT_ENTRY_RANGE;
        else entry->range_valid = 1;
        if ((entry->attributes.limb[0] & 0xfff8U) || entry->attributes.limb[1] || entry->attributes.limb[2] ||
            nonzero(entry->raw.data + 128, entry->raw.size - 128)) entry->issues |= DE_GPT_RESERVED;
        de_view_slice(&entry->raw, 56, 72, &name);
        for (k = 0; k < 36; ++k)
            if (!name.data[k * 2] && !name.data[k * 2 + 1]) { entry->name_terminated = 1; break; }
        if (!entry->name_terminated) entry->issues |= DE_GPT_NAME_TERMINATOR;
        terminated = 0;
        if (de_gpt_name_utf8(&name, name_text, sizeof(name_text), &terminated)) entry->issues |= DE_GPT_NAME_UTF16;
        for (j = 0; j < i; ++j) {
            if (!entries[j].active) continue;
            if (!memcmp(entry->raw.data + 16, entries[j].raw.data + 16, 16)) {
                entry->issues |= DE_GPT_DUPLICATE_GUID; entries[j].issues |= DE_GPT_DUPLICATE_GUID;
            }
            if (entry->range_valid && entries[j].range_valid &&
                !de_extent_overlap(&entry->extent, &entries[j].extent, &overlap) && overlap) {
                entry->issues |= DE_GPT_OVERLAP; entries[j].issues |= DE_GPT_OVERLAP;
            }
        }
        c.issues |= entry->issues;
    }
    c.count = count; c.complete = 1; c.consistent = c.issues == 0; *out = c; return DE_OK;
}

int de_gpt_compare(const de_gpt_candidate *primary, const de_gpt_candidate *backup, int *out)
{
    const de_gpt_header *a, *b;
    size_t size;
    int same;
    if (!primary || !backup || !out || !primary->header || !backup->header) return DE_INVALID;
    a = primary->header; b = backup->header;
    if (a->role != DE_GPT_PRIMARY || b->role != DE_GPT_BACKUP) return DE_INVALID;
    if (a->space != b->space || !a->consistent || !b->consistent ||
        !primary->complete || !backup->complete || !primary->consistent || !backup->consistent) {
        *out = DE_GPT_INCOMPARABLE; return DE_OK;
    }
    same = a->header_size == b->header_size && a->count == b->count && a->entry_size == b->entry_size &&
        !memcmp(a->disk_guid, b->disk_guid, 16) && !de_u64_compare(&a->first_usable, &b->first_usable) &&
        !de_u64_compare(&a->last_usable, &b->last_usable);
    if (same) {
        if (de_u64_to_size(&a->array_bytes, &size)) return DE_WIDTH;
        same = !memcmp(primary->raw_array.data, backup->raw_array.data, size);
    }
    *out = same ? DE_GPT_AGREE : DE_GPT_DISAGREE; return DE_OK;
}
