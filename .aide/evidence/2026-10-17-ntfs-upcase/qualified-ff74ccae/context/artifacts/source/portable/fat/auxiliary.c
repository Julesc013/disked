#include "fat.h"
#include <string.h>

static de_u32 u16(const unsigned char *p) {
    return (de_u32)p[0] | ((de_u32)p[1] << 8);
}
static de_u32 u32(const unsigned char *p) {
    return u16(p) | (u16(p + 2) << 16);
}

int de_fat_header_read(const de_view *header, int bits, unsigned char media, de_fat_header *out) {
    de_fat_header value;
    de_u32 mask, flags, clean, error;
    size_t required;
    const unsigned char *p;
    if (!header || !out || (!header->data && header->size) ||
        (bits != 12 && bits != 16 && bits != 32))
        return DE_INVALID;
    required = bits == 12 ? 3 : (bits == 16 ? 4 : 8);
    if (header->size > required)
        return DE_BOUNDS;
    memset(&value, 0, sizeof(value));
    value.raw = *header;
    value.flags_supported = bits != 12;
    if (media != 0xf0 && media < 0xf8)
        value.issues |= DE_FAT_HEADER_MEDIA;
    if (header->size < required) {
        value.issues |= DE_FAT_HEADER_TRUNCATED;
        *out = value;
        return DE_OK;
    }
    p = header->data;
    mask = bits == 12 ? 0xfffUL : (bits == 16 ? 0xffffUL : 0x0fffffffUL);
    value.raw_zero = bits == 32 ? u32(p) : u16(p);
    value.raw_one = bits == 32 ? u32(p + 4) : u16(p + (bits == 12 ? 1 : 2));
    value.zero = value.raw_zero & mask;
    value.one = (bits == 12 ? value.raw_one >> 4 : value.raw_one) & mask;
    value.fields_present = 1;
    if (value.zero != ((mask & ~255UL) | media))
        value.issues |= DE_FAT_HEADER_ZERO;
    if (bits == 12) {
        if (value.one < mask - 7)
            value.issues |= DE_FAT_HEADER_ONE;
    } else {
        clean = bits == 16 ? 0x8000UL : 0x08000000UL;
        error = bits == 16 ? 0x4000UL : 0x04000000UL;
        flags = clean | error;
        if ((value.one & ~flags) != (mask & ~flags))
            value.issues |= DE_FAT_HEADER_ONE;
        value.clean_shutdown = (value.one & clean) != 0;
        value.no_io_error = (value.one & error) != 0;
    }
    *out = value;
    return DE_OK;
}

int de_fat_fsinfo_read(const de_view *sector, de_u32 sector_bytes, de_u32 clusters,
                       de_fat_fsinfo *out) {
    de_fat_fsinfo value;
    const unsigned char *p;
    size_t i;
    if (!sector || !out || (!sector->data && sector->size) ||
        (sector_bytes != 512 && sector_bytes != 1024 && sector_bytes != 2048 &&
         sector_bytes != 4096) ||
        clusters < 65525 || clusters > 268435445UL)
        return DE_INVALID;
    if (sector->size > sector_bytes)
        return DE_BOUNDS;
    memset(&value, 0, sizeof(value));
    value.raw = *sector;
    if (sector->size < sector_bytes)
        value.issues |= DE_FAT_FSINFO_TRUNCATED;
    if (sector->size < 512) {
        *out = value;
        return DE_OK;
    }
    p = sector->data;
    value.fields_present = 1;
    value.lead_signature = u32(p);
    value.structure_signature = u32(p + 484);
    value.trail_signature = u32(p + 508);
    value.free_count = u32(p + 488);
    value.next_free = u32(p + 492);
    if (value.lead_signature != 0x41615252UL || value.structure_signature != 0x61417272UL ||
        value.trail_signature != 0xaa550000UL)
        value.issues |= DE_FAT_FSINFO_SIGNATURE;
    for (i = 4; i < 484; ++i)
        if (p[i])
            ++value.reserved_nonzero;
    for (i = 496; i < 508; ++i)
        if (p[i])
            ++value.reserved_nonzero;
    if (value.reserved_nonzero)
        value.issues |= DE_FAT_FSINFO_RESERVED;
    value.free_count_known = value.free_count != 0xffffffffUL;
    value.next_free_known = value.next_free != 0xffffffffUL;
    if (value.free_count_known && value.free_count > clusters)
        value.issues |= DE_FAT_FSINFO_COUNT;
    if (value.next_free_known && (value.next_free < 2 || value.next_free > clusters + 1))
        value.issues |= DE_FAT_FSINFO_NEXT;
    *out = value;
    return DE_OK;
}
