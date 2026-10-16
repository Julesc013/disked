#ifndef DISKED_PRIMITIVE_VIEW_H
#define DISKED_PRIMITIVE_VIEW_H
#include "checked.h"
typedef struct de_view { const unsigned char *data; size_t size; } de_view;
typedef struct de_buffer { unsigned char *data; size_t size; } de_buffer;
enum de_byte_order { DE_LITTLE_ENDIAN, DE_BIG_ENDIAN };
#ifdef __cplusplus
extern "C" {
#endif
int de_view_init(const unsigned char *data, size_t size, de_view *out);
int de_view_slice(const de_view *view, size_t offset, size_t length, de_view *out);
int de_view_slice_u64(const de_view *view, const de_u64 *offset, const de_u64 *length, de_view *out);
int de_view_read_uint(const de_view *view, size_t offset, unsigned int width, int order, de_u64 *out);
int de_buffer_write_uint(const de_buffer *buffer, size_t offset, unsigned int width, int order, const de_u64 *value);
#ifdef __cplusplus
}
#endif
#endif
