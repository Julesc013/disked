#include "ntfs.h"

static int table_check(const de_ntfs_upcase *table) {
    size_t page;
    if (!table || !table->pages || table->major != 3 || table->minor > 1)
        return DE_INVALID;
    if (table->page_count != DE_NTFS_UPCASE_PAGES)
        return DE_BOUNDS;
    for (page = 0; page < table->page_count; ++page) {
        const de_view *view = &table->pages[page];
        if (!view->data && view->size)
            return DE_INVALID;
        if (view->size != DE_NTFS_UPCASE_PAGE_BYTES)
            return DE_BOUNDS;
    }
    return DE_OK;
}

static unsigned short word(const unsigned char *bytes) {
    return (unsigned short)((unsigned int)bytes[0] | ((unsigned int)bytes[1] << 8));
}

static unsigned short mapped(const de_ntfs_upcase *table, unsigned short unit) {
    size_t page = (size_t)(unit >> 8);
    size_t offset = (size_t)(unit & 255U) * 2;
    return word(table->pages[page].data + offset);
}

int de_ntfs_upcase_init(const de_view *pages, size_t page_count, unsigned int major,
                        unsigned int minor, de_ntfs_upcase *out) {
    de_ntfs_upcase value;
    int result;
    if (!out)
        return DE_INVALID;
    value.pages = pages;
    value.page_count = page_count;
    value.major = major;
    value.minor = minor;
    result = table_check(&value);
    if (result != DE_OK)
        return result;
    *out = value;
    return DE_OK;
}

int de_ntfs_upcase_read(const de_ntfs_upcase *table, de_u32 code_unit, unsigned short *out) {
    int result;
    if (!out)
        return DE_INVALID;
    result = table_check(table);
    if (result != DE_OK)
        return result;
    if (code_unit >= DE_NTFS_UPCASE_UNITS)
        return DE_BOUNDS;
    *out = mapped(table, (unsigned short)code_unit);
    return DE_OK;
}

static int name_check(const de_view *name) {
    if (!name || (!name->data && name->size))
        return DE_INVALID;
    if (name->size > 510U || (name->size & 1U))
        return DE_BOUNDS;
    return DE_OK;
}

static int unit_order(unsigned short left, unsigned short right) {
    return left < right ? -1 : left > right ? 1 : 0;
}

int de_ntfs_name_compare(const de_ntfs_upcase *table, const de_view *left, const de_view *right,
                         de_ntfs_name_order *out) {
    de_ntfs_name_order value;
    size_t offset, common;
    unsigned short a, b;
    int result, length_order;
    if (!out)
        return DE_INVALID;
    result = table_check(table);
    if (result != DE_OK)
        return result;
    result = name_check(left);
    if (result != DE_OK)
        return result;
    result = name_check(right);
    if (result != DE_OK)
        return result;
    common = left->size < right->size ? left->size : right->size;
    value.raw_order = 0;
    value.upcase_order = 0;
    for (offset = 0; offset < common; offset += 2) {
        a = word(left->data + offset);
        b = word(right->data + offset);
        if (!value.raw_order)
            value.raw_order = unit_order(a, b);
        if (!value.upcase_order)
            value.upcase_order = unit_order(mapped(table, a), mapped(table, b));
        if (value.raw_order && value.upcase_order)
            break;
    }
    length_order = left->size < right->size ? -1 : left->size > right->size ? 1 : 0;
    if (!value.raw_order)
        value.raw_order = length_order;
    if (!value.upcase_order)
        value.upcase_order = length_order;
    *out = value;
    return DE_OK;
}
