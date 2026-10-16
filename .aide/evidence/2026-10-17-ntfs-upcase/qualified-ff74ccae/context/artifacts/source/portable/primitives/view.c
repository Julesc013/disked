#include "view.h"

int de_view_init(const unsigned char *data, size_t size, de_view *out)
{
    de_view candidate;
    if (!data && size) return DE_INVALID;
    candidate.data = data; candidate.size = size; *out = candidate;
    return DE_OK;
}
int de_view_slice(const de_view *view, size_t offset, size_t length, de_view *out)
{
    de_view candidate;
    if (!view->data && view->size) return DE_INVALID;
    if (offset > view->size || length > view->size - offset) return DE_BOUNDS;
    candidate.data = view->data ? view->data + offset : NULL;
    candidate.size = length; *out = candidate;
    return DE_OK;
}
int de_view_slice_u64(const de_view *view, const de_u64 *offset, const de_u64 *length, de_view *out)
{
    size_t native_offset, native_length;
    int status = de_u64_to_size(offset, &native_offset);
    if (status) return status;
    status = de_u64_to_size(length, &native_length);
    if (status) return status;
    return de_view_slice(view, native_offset, native_length, out);
}
static int format_valid(unsigned int width, int order)
{
    return (width == 1 || width == 2 || width == 4 || width == 8) &&
        (order == DE_LITTLE_ENDIAN || order == DE_BIG_ENDIAN);
}
int de_view_read_uint(const de_view *view, size_t offset, unsigned int width, int order, de_u64 *out)
{
    de_view part;
    unsigned char bytes[8] = {0, 0, 0, 0, 0, 0, 0, 0};
    unsigned int i;
    int status;
    if (!format_valid(width, order)) return DE_INVALID;
    status = de_view_slice(view, offset, width, &part);
    if (status) return status;
    for (i = 0; i < width; ++i) bytes[i] = part.data[order == DE_LITTLE_ENDIAN ? i : width - i - 1];
    return de_u64_load_le(bytes, 8, out);
}
int de_buffer_write_uint(const de_buffer *buffer, size_t offset, unsigned int width, int order, const de_u64 *value)
{
    unsigned char bytes[8];
    unsigned char *destination = buffer->data;
    unsigned int i;
    if (!format_valid(width, order) || (!buffer->data && buffer->size)) return DE_INVALID;
    if (offset > buffer->size || width > buffer->size - offset) return DE_BOUNDS;
    de_u64_store_le(value, bytes, 8);
    for (i = width; i < 8; ++i) if (bytes[i]) return DE_WIDTH;
    for (i = 0; i < width; ++i) destination[offset + i] = bytes[order == DE_LITTLE_ENDIAN ? i : width - i - 1];
    return DE_OK;
}
