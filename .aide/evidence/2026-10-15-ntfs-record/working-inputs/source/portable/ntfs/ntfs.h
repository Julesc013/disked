#ifndef DISKED_NTFS_H
#define DISKED_NTFS_H
#include "portable/primitives/view.h"

/* Private NTFS3 supplied-byte envelopes; no filesystem or source authority. */
#define DE_NTFS_MAX_RECORD 49152U
#define DE_NTFS_STRIDE 512U
#define DE_NTFS_TRUNCATED 0x0001UL
#define DE_NTFS_LENGTH 0x0002UL
#define DE_NTFS_SIGNATURE 0x0004UL
#define DE_NTFS_VERSION 0x0008UL
#define DE_NTFS_USA_OFFSET 0x0010UL
#define DE_NTFS_USA_COUNT 0x0020UL
#define DE_NTFS_TORN 0x0040UL
#define DE_NTFS_HEADER 0x0080UL

typedef struct de_ntfs_record {
    de_view raw;
    de_u64 log_sequence, base_reference;
    de_u32 issues, used_bytes, allocated_bytes;
    unsigned short usa_offset, usa_count, update_sequence, sequence;
    unsigned short links, attribute_offset, flags, next_attribute_id;
    unsigned int strides, mismatched_tails;
    int fields_present, fixups_valid, envelope_valid;
    int in_use, name_index_present;
} de_ntfs_record;

#ifdef __cplusplus
extern "C" {
#endif
int de_ntfs_record_read(const de_view *raw, unsigned int major, unsigned int minor,
                        de_ntfs_record *out);
/* Validate before writing. Source and written output spans must be disjoint. */
int de_ntfs_record_restore(const de_view *raw, unsigned int major, unsigned int minor,
                           const de_buffer *output, de_ntfs_record *out);
#ifdef __cplusplus
}
#endif
#endif
