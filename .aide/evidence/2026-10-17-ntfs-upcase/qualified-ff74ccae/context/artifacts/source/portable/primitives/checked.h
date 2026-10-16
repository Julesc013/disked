#ifndef DISKED_PRIMITIVE_CHECKED_H
#define DISKED_PRIMITIVE_CHECKED_H
#include <limits.h>
#include <stddef.h>

#if CHAR_BIT != 8 || USHRT_MAX != 65535U
#error DiskEd portable primitives require 8-bit bytes and 16-bit unsigned short
#endif
#if UINT_MAX == 4294967295UL
typedef unsigned int de_u32;
#elif ULONG_MAX == 4294967295UL
typedef unsigned long de_u32;
#else
#error DiskEd portable primitives require an exactly 32-bit unsigned type
#endif

/* Private internal representation, not a serialized struct or public SDK ABI. */
typedef struct de_u64 { unsigned short limb[4]; } de_u64;
enum de_status { DE_OK, DE_INVALID, DE_OVERFLOW,
    DE_BUFFER, DE_WIDTH, DE_UNDERFLOW, DE_DIVZERO, DE_BOUNDS,
    DE_EMPTY, DE_UNIT, DE_SPACE, DE_ALIGNMENT };

#ifdef __cplusplus
extern "C" {
#endif

int de_u64_parse(const char *text, size_t length, de_u64 *out);
int de_u64_format(const de_u64 *value, char *out, size_t capacity);
int de_u64_add(const de_u64 *a, const de_u64 *b, de_u64 *out);
int de_u64_compare(const de_u64 *a, const de_u64 *b);
int de_u64_sub(const de_u64 *a, const de_u64 *b, de_u64 *out);
int de_u64_mul(const de_u64 *a, const de_u64 *b, de_u64 *out);
int de_u64_divmod(const de_u64 *a, const de_u64 *b, de_u64 *quotient, de_u64 *remainder);
int de_u64_from_size(size_t value, de_u64 *out);
int de_u64_to_size(const de_u64 *value, size_t *out);
de_u64 de_u64_from_u32(de_u32 value);
int de_u64_to_u32(const de_u64 *value, de_u32 *out);
int de_u64_load_le(const unsigned char *bytes, size_t length, de_u64 *out);
int de_u64_store_le(const de_u64 *value, unsigned char *out, size_t capacity);
int de_bytes_escape(const unsigned char *bytes, size_t length, char *out, size_t capacity);
#ifdef __cplusplus
}
#endif
#endif
