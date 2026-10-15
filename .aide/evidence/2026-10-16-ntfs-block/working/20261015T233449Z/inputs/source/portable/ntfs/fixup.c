#include "fixup.h"
#include "ntfs.h"
#include <string.h>

unsigned int de_ntfs_fixup_mismatches(const de_view *raw, unsigned short usa_offset,
                                      unsigned int strides) {
    size_t i, tail;
    unsigned int mismatches = 0;
    for (i = 0; i < strides; ++i) {
        tail = (i + 1) * DE_NTFS_STRIDE - 2;
        if (raw->data[tail] != raw->data[usa_offset] ||
            raw->data[tail + 1] != raw->data[usa_offset + 1])
            ++mismatches;
    }
    return mismatches;
}

int de_ntfs_fixup_restore(const de_view *raw, unsigned short usa_offset, const de_buffer *output) {
    size_t i, tail;
    if (output->size < raw->size)
        return DE_BUFFER;
    /* Pointer equality is defined across unrelated objects; ordering is not. */
    for (i = 0; i < raw->size; ++i)
        if (raw->data + i == output->data || output->data + i == raw->data)
            return DE_INVALID;
    memcpy(output->data, raw->data, raw->size);
    for (i = 0; i < raw->size / DE_NTFS_STRIDE; ++i) {
        tail = (i + 1) * DE_NTFS_STRIDE - 2;
        output->data[tail] = raw->data[usa_offset + (i + 1) * 2];
        output->data[tail + 1] = raw->data[usa_offset + (i + 1) * 2 + 1];
    }
    return DE_OK;
}
