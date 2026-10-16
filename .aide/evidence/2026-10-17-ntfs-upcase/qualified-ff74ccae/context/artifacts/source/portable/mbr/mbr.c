#include "mbr.h"
#include <string.h>

int de_mbr_nonzero(const unsigned char *data, size_t size)
{
    size_t i;
    for (i = 0; i < size; ++i) if (data[i]) return 1;
    return 0;
}

int de_mbr_geometry_valid(const de_mbr_geometry *g)
{
    return g && ((!g->heads && !g->sectors) ||
        (g->heads >= 1 && g->heads <= 256 && g->sectors >= 1 && g->sectors <= 63));
}

int de_mbr_decode(const de_view *bytes, const de_block_space *space, de_mbr_table *out)
{
    de_mbr_table value;
    de_block_space check;
    de_u64 unit;
    size_t native_unit;
    unsigned int i;
    int status;
    de_view entry;
    de_mbr_entry *e;
    if (!bytes || !space || !out || (!bytes->data && bytes->size)) return DE_INVALID;
    if (de_space_init(space->name, space->name_length, &space->blocks,
                      space->logical_block_bytes, &check) || space->logical_block_bytes < 512)
        return DE_UNIT;
    unit = de_u64_from_u32(0);
    if (!de_u64_compare(&space->blocks, &unit)) return DE_BOUNDS;
    unit = de_u64_from_u32(space->logical_block_bytes);
    if (de_u64_to_size(&unit, &native_unit)) return DE_WIDTH;
    if (bytes->size > native_unit) return DE_BOUNDS;
    memset(&value, 0, sizeof(value));
    value.raw = *bytes;
    if (bytes->size < native_unit) value.issues = DE_MBR_TRUNCATED;
    else if (bytes->data[510] != 0x55 || bytes->data[511] != 0xaa)
        value.issues = DE_MBR_SIGNATURE;
    else {
        value.signature = 1;
        for (i = 0; i < 4; ++i) {
            e = &value.entries[i];
            /* Bounds derive from the already checked complete block. */
            status = de_view_slice(bytes, 446 + (size_t)i * 16, 16, &entry);
            if (status) return status;
            memcpy(e->raw, entry.data, 16);
            status = de_view_read_uint(&entry, 8, 4, DE_LITTLE_ENDIAN, &e->relative_start);
            if (status) return status;
            status = de_view_read_uint(&entry, 12, 4, DE_LITTLE_ENDIAN, &e->blocks);
            if (status) return status;
            e->active = e->raw[4] != 0 && de_mbr_nonzero(e->raw + 12, 4);
            if (!e->active) {
                if (de_mbr_nonzero(e->raw, 16)) e->issues |= DE_MBR_INACTIVE;
            } else {
                e->kind = DE_MBR_DATA;
                if (e->raw[4] == 5 || e->raw[4] == 15 || e->raw[4] == 0x85)
                    e->kind = DE_MBR_EXTENDED;
                if (e->raw[4] == 0xee) e->kind = DE_MBR_GPT;
            }
            if (e->raw[0] != 0 && e->raw[0] != 0x80) e->issues |= DE_MBR_BOOT;
            value.issues |= e->issues;
        }
    }
    *out = value;
    return DE_OK;
}

static void compare_chs(const unsigned char *raw, const de_u64 *lba,
                         const de_mbr_geometry *g, de_mbr_entry *entry)
{
    de_u32 cylinder, head, sector, address;
    de_u64 expected;
    if (!g->heads || !de_mbr_nonzero(raw, 3) ||
        ((raw[0] == 0xfe || raw[0] == 0xff) && raw[1] == 0xff && raw[2] == 0xff))
        return;
    ++entry->chs_compared;
    head = raw[0]; sector = (de_u32)(raw[1] & 63);
    cylinder = (de_u32)raw[2] + (de_u32)(raw[1] & 192) * 4;
    if (head >= g->heads || !sector || sector > g->sectors) {
        entry->issues |= DE_MBR_CHS; return;
    }
    address = (cylinder * g->heads + head) * g->sectors + sector - 1;
    expected = de_u64_from_u32(address);
    if (de_u64_compare(&expected, lba)) entry->issues |= DE_MBR_CHS;
}

void de_mbr_resolve(const de_block_space *space, const de_u64 *base,
                    const de_mbr_geometry *geometry, de_mbr_entry *entry)
{
    de_u64 start, last, one;
    if (!entry->active) return;
    if (de_u64_add(base, &entry->relative_start, &start) ||
        de_extent_make(space, &start, &entry->blocks, &entry->extent)) {
        entry->issues |= DE_MBR_RANGE; return;
    }
    entry->range_valid = 1;
    one = de_u64_from_u32(1);
    de_u64_sub(&entry->extent.end, &one, &last);
    compare_chs(entry->raw + 1, &start, geometry, entry);
    compare_chs(entry->raw + 5, &last, geometry, entry);
}

int de_mbr_read(const de_view *bytes, const de_block_space *space,
                const de_mbr_geometry *geometry, de_mbr_table *out)
{
    de_mbr_table value;
    de_u64 zero, one, expected, maximum;
    unsigned int i, j, protective = 0, ordinary_active = 0;
    int status, overlap;
    de_mbr_entry *e;
    if (!out || !de_mbr_geometry_valid(geometry)) return DE_INVALID;
    status = de_mbr_decode(bytes, space, &value);
    if (status) return status;
    zero = de_u64_from_u32(0); one = de_u64_from_u32(1);
    maximum = de_u64_from_u32((de_u32)0xffffffffUL);
    for (i = 0; i < 4; ++i) {
        e = &value.entries[i];
        de_mbr_resolve(space, &zero, geometry, e);
        if (e->active && e->raw[4] != 0xee) ++ordinary_active;
        if (e->range_valid && !de_u64_compare(&e->extent.start, &zero))
            e->issues |= DE_MBR_METADATA;
        if (e->raw[4] == 0xee) {
            ++protective;
            expected = zero;
            if (de_u64_compare(&space->blocks, &zero)) de_u64_sub(&space->blocks, &one, &expected);
            if (de_u64_compare(&expected, &maximum) > 0) expected = maximum;
            if (e->raw[0] || e->raw[1] || e->raw[2] != 2 || e->raw[3] ||
                de_u64_compare(&e->relative_start, &one) ||
                de_u64_compare(&e->blocks, &expected) || !e->active)
                e->issues |= DE_MBR_PROTECTIVE;
            for (j = 0; j < 4; ++j)
                if (j != i && de_mbr_nonzero(value.entries[j].raw, 16))
                    e->issues |= DE_MBR_PROTECTIVE;
            if (de_mbr_nonzero(bytes->data + 440, 6) ||
                de_mbr_nonzero(bytes->data + 512, bytes->size - 512))
                e->issues |= DE_MBR_PROTECTIVE;
        }
        for (j = 0; j < i; ++j) {
            if (e->range_valid && value.entries[j].range_valid &&
                !de_extent_overlap(&e->extent, &value.entries[j].extent, &overlap) && overlap) {
                e->issues |= DE_MBR_OVERLAP;
                value.entries[j].issues |= DE_MBR_OVERLAP;
            }
        }
    }
    if (protective && (protective != 1 || ordinary_active)) value.issues |= DE_MBR_HYBRID;
    for (i = 0; i < 4; ++i) value.issues |= value.entries[i].issues;
    *out = value;
    return DE_OK;
}
