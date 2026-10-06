#ifndef DISKED_PRIMITIVE_CHECKED_H
#define DISKED_PRIMITIVE_CHECKED_H
#include <limits.h>
#include <stddef.h>

#if CHAR_BIT != 8 || USHRT_MAX != 65535U
#error DiskEd primitive probe requires 8-bit bytes and 16-bit unsigned short
#endif
#if UINT_MAX == 4294967295UL
typedef unsigned int de_probe_u32;
#elif ULONG_MAX == 4294967295UL
typedef unsigned long de_probe_u32;
#else
#error DiskEd primitive probe requires an exactly 32-bit unsigned type
#endif

/* Private probe representation, not a serialized struct or public SDK ABI. */
typedef struct de_probe_u64 { unsigned short limb[4]; } de_probe_u64;
enum de_probe_status { DE_PROBE_OK, DE_PROBE_INVALID, DE_PROBE_OVERFLOW,
    DE_PROBE_BUFFER, DE_PROBE_WIDTH };

int de_probe_parse(const char *text, size_t length, de_probe_u64 *out);
int de_probe_format(const de_probe_u64 *value, char *out, size_t capacity);
int de_probe_add(const de_probe_u64 *a, const de_probe_u64 *b, de_probe_u64 *out);
int de_probe_narrow(const de_probe_u64 *value, de_probe_u32 *out);
int de_probe_load_le(const unsigned char *bytes, size_t length, de_probe_u64 *out);
int de_probe_store_le(const de_probe_u64 *value, unsigned char *out, size_t capacity);
int de_probe_escape(const unsigned char *bytes, size_t length, char *out, size_t capacity);
#endif
