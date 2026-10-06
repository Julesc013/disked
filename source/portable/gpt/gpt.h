#ifndef DISKED_GPT_H
#define DISKED_GPT_H
#include "view.h"
#include "extent.h"

/* Private borrowed C API. Inputs/output workspace are disjoint caller objects. */
#define DE_GPT_TRUNCATED       0x000001UL
#define DE_GPT_SIGNATURE       0x000002UL
#define DE_GPT_REVISION        0x000004UL
#define DE_GPT_HEADER_SIZE     0x000008UL
#define DE_GPT_HEADER_CRC      0x000010UL
#define DE_GPT_RESERVED        0x000020UL
#define DE_GPT_LOCATION        0x000040UL
#define DE_GPT_USABLE          0x000080UL
#define DE_GPT_ARRAY_SHAPE     0x000100UL
#define DE_GPT_ARRAY_RANGE     0x000200UL
#define DE_GPT_ARRAY_CRC       0x000400UL
#define DE_GPT_ENTRY_RANGE     0x000800UL
#define DE_GPT_OVERLAP         0x001000UL
#define DE_GPT_DUPLICATE_GUID  0x002000UL
#define DE_GPT_ZERO_GUID       0x004000UL
#define DE_GPT_NAME_UTF16      0x008000UL
#define DE_GPT_NAME_TERMINATOR 0x010000UL
#define DE_GPT_UNUSED_DATA     0x020000UL

enum de_gpt_role { DE_GPT_PRIMARY = 1, DE_GPT_BACKUP = 2 };
enum de_gpt_comparison { DE_GPT_INCOMPARABLE, DE_GPT_AGREE, DE_GPT_DISAGREE };
typedef struct de_gpt_limits {
    de_u32 entries, entry_bytes, array_bytes;
} de_gpt_limits;
typedef struct de_gpt_header {
    const de_block_space *space;
    de_view raw;
    int role, consistent;
    de_u64 observed_lba, my_lba, alternate_lba, first_usable, last_usable;
    de_u64 array_lba, array_bytes, array_blocks;
    de_block_extent array_extent;
    de_u32 revision, header_size, header_crc, count, entry_size, array_crc, issues;
    unsigned char disk_guid[16];
} de_gpt_header;
typedef struct de_gpt_entry {
    de_view raw;
    de_u64 first, last, attributes;
    de_block_extent extent;
    de_u32 issues;
    int active, range_valid, name_terminated;
} de_gpt_entry;
typedef struct de_gpt_candidate {
    const de_gpt_header *header;
    de_view raw_array;
    de_gpt_entry *entries;
    size_t count;
    de_u32 issues;
    int complete, consistent;
} de_gpt_candidate;

#ifdef __cplusplus
extern "C" {
#endif
int de_gpt_crc32(const de_view *bytes, de_u32 *out);
int de_gpt_guid_text(const de_view *bytes, char *out, size_t capacity);
int de_gpt_name_utf8(const de_view *bytes, char *out, size_t capacity, int *terminated);
int de_gpt_header_read(const de_view *bytes, const de_block_space *space,
                       const de_u64 *lba, int role, de_gpt_header *out);
/* DE_BUFFER denotes a profile budget refusal; no output is published. */
int de_gpt_request_array(const de_gpt_header *header, const de_gpt_limits *limits,
                         de_block_extent *out);
int de_gpt_array_read(const de_gpt_header *header, const de_gpt_limits *limits,
                      const de_view *bytes, de_gpt_entry *entries, size_t capacity,
                      de_gpt_candidate *out);
int de_gpt_compare(const de_gpt_candidate *primary, const de_gpt_candidate *backup,
                    int *out);
#ifdef __cplusplus
}
#endif
#endif
