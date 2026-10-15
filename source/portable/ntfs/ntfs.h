#ifndef DISKED_NTFS_H
#define DISKED_NTFS_H
#include "portable/primitives/view.h"

/* Private NTFS3 supplied-byte envelopes; no filesystem or source authority.
 * Views borrow stable original bytes. API/control/result objects must be valid
 * and disjoint from those byte spans. No public ABI or hostile C-caller boundary.
 */
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
#define DE_NTFS_BLOCK_FLAGS 0x0100UL
#define DE_NTFS_BLOCK_VBN 0x0200UL

#define DE_NTFS_BOOT_TRUNCATED 0x0001UL
#define DE_NTFS_BOOT_OEM 0x0002UL
#define DE_NTFS_BOOT_SECTOR 0x0004UL
#define DE_NTFS_BOOT_CLUSTER 0x0008UL
#define DE_NTFS_BOOT_BPB 0x0010UL
#define DE_NTFS_BOOT_RECORD 0x0020UL
#define DE_NTFS_BOOT_INDEX 0x0040UL
#define DE_NTFS_BOOT_SIZE 0x0080UL
#define DE_NTFS_BOOT_ADDRESS 0x0100UL
#define DE_NTFS_BOOT_CAPACITY 0x0200UL
#define DE_NTFS_BOOT_OVERFLOW 0x0400UL
#define DE_NTFS_BOOT_VERSION 0x0800UL
#define DE_NTFS_BOOT_UNSUPPORTED 0x1000UL
#define DE_NTFS_BOOT_MARKER 0x2000UL
#define DE_NTFS_BOOT_CHECKSUM 0x4000UL
#define DE_NTFS_BOOT_LENGTH 0x8000UL
#define DE_NTFS_MAX_CLUSTER 2097152UL
#define DE_NTFS_MAX_ITEMS 4096U
#define DE_NTFS_ATTR_TRUNCATED 0x0001UL
#define DE_NTFS_ATTR_LENGTH 0x0002UL
#define DE_NTFS_ATTR_FORM 0x0004UL
#define DE_NTFS_ATTR_NAME 0x0008UL
#define DE_NTFS_ATTR_VALUE 0x0010UL
#define DE_NTFS_ATTR_FEATURE 0x0020UL
#define DE_NTFS_ATTR_VCN 0x0040UL
#define DE_NTFS_ATTR_SIZE 0x0080UL
#define DE_NTFS_ATTR_MAPPING 0x0100UL
#define DE_NTFS_ATTR_TYPE 0x0200UL
#define DE_NTFS_ATTR_BUDGET 0x0400UL
#define DE_NTFS_ATTR_END 0x0800UL
#define DE_NTFS_RUN_TRUNCATED 0x0001UL
#define DE_NTFS_RUN_WIDTH 0x0002UL
#define DE_NTFS_RUN_LENGTH 0x0004UL
#define DE_NTFS_RUN_OVERFLOW 0x0008UL
#define DE_NTFS_RUN_RANGE 0x0010UL
#define DE_NTFS_RUN_COVERAGE 0x0020UL
#define DE_NTFS_RUN_SPARSE 0x0040UL
#define DE_NTFS_RUN_BUDGET 0x0080UL
#define DE_NTFS_LIST_TRUNCATED 0x0001UL
#define DE_NTFS_LIST_LENGTH 0x0002UL
#define DE_NTFS_LIST_ALIGNMENT 0x0004UL
#define DE_NTFS_LIST_NAME 0x0008UL
#define DE_NTFS_LIST_VCN 0x0010UL
#define DE_NTFS_LIST_TYPE 0x0020UL
#define DE_NTFS_LIST_BUDGET 0x0040UL
#define DE_NTFS_NAME_TRUNCATED 0x0001UL
#define DE_NTFS_NAME_LENGTH 0x0002UL
#define DE_NTFS_NAME_NAMESPACE 0x0004UL
#define DE_NTFS_NAME_REFERENCE 0x0008UL
#define DE_NTFS_INDEX_TRUNCATED 0x0001UL
#define DE_NTFS_INDEX_LENGTH 0x0002UL
#define DE_NTFS_INDEX_ALIGNMENT 0x0004UL
#define DE_NTFS_INDEX_PROFILE 0x0008UL
#define DE_NTFS_INDEX_GEOMETRY 0x0010UL
#define DE_NTFS_INDEX_FLAGS 0x0020UL
#define DE_NTFS_INDEX_KEY 0x0040UL
#define DE_NTFS_INDEX_REFERENCE 0x0080UL
#define DE_NTFS_INDEX_CHILD 0x0100UL
#define DE_NTFS_INDEX_END 0x0200UL
#define DE_NTFS_INDEX_BUDGET 0x0400UL

typedef struct de_ntfs_filename {
    de_view raw, duplicated_information, name, suffix;
    de_u64 parent_reference, parent_record;
    de_u32 issues;
    unsigned short parent_sequence;
    unsigned char name_length, namespace_code;
    int fields_present, envelope_valid, namespace_known;
} de_ntfs_filename;

typedef struct de_ntfs_index_root {
    de_view raw;
    de_u32 type, collation, index_bytes, first_offset, used_bytes, allocated_bytes;
    de_u32 child_unit_bytes, issues;
    unsigned char units_per_index, flags;
    int fields_present, envelope_valid, geometry_matches, directory_profile;
} de_ntfs_index_root;

typedef struct de_ntfs_index_entry {
    de_view raw, key, padding;
    de_ntfs_filename filename;
    de_u64 segment_reference, record_number, child_vbn;
    de_u32 issues;
    unsigned short record_length, key_length, flags, sequence;
    int present, end_marker, has_child, envelope_valid;
} de_ntfs_index_entry;

typedef struct de_ntfs_index_block {
    de_view raw;
    de_u64 log_sequence, vbn;
    de_u32 first_offset, used_bytes, allocated_bytes, issues;
    unsigned short usa_offset, usa_count, update_sequence;
    unsigned int strides, mismatched_tails;
    unsigned char flags;
    int fields_present, fixups_valid, envelope_valid;
} de_ntfs_index_block;

typedef struct de_ntfs_index_cursor {
    de_view value;
    size_t offset;
    unsigned int major, minor, limit, count;
    de_u32 issues;
    int has_children, terminated, stopped;
} de_ntfs_index_cursor;

typedef struct de_ntfs_attr_list_entry {
    de_view raw, name;
    de_u64 lowest_vcn, segment_reference, record_number;
    de_u32 type, issues;
    unsigned short record_length, sequence, attribute_id;
    unsigned char name_length, name_offset;
    int present, envelope_valid;
} de_ntfs_attr_list_entry;

typedef struct de_ntfs_attr_list_cursor {
    de_view value;
    size_t offset;
    unsigned int limit, count;
    de_u32 issues;
    int terminated, stopped;
} de_ntfs_attr_list_cursor;

typedef struct de_ntfs_attribute {
    de_view raw, name, value, mapping;
    de_u64 lowest_vcn, highest_vcn, cluster_span;
    de_u64 allocated_size, data_size, initialized_size, total_allocated;
    de_u32 type, record_length, value_length, issues;
    unsigned short flags, instance, name_offset, value_offset, mapping_offset;
    unsigned short compression_unit;
    unsigned char form, name_length, resident_flags;
    int present, end_marker, variant_fields, envelope_valid;
    int sizes_applicable, has_total_allocated, empty_stream, ordinary_mapping;
} de_ntfs_attribute;

typedef struct de_ntfs_attr_cursor {
    de_view logical;
    size_t offset;
    unsigned int limit, count;
    de_u32 issues;
    int terminated, stopped;
} de_ntfs_attr_cursor;

typedef struct de_ntfs_run {
    de_view raw;
    de_u64 vcn, next_vcn, length, lcn, lcn_end;
    de_u32 issues;
    unsigned char length_width, offset_width;
    int present, end_marker, sparse, negative_delta, valid;
} de_ntfs_run;

typedef struct de_ntfs_run_cursor {
    de_view pairs;
    de_u64 next_vcn, end_vcn, previous_lcn, volume_clusters;
    size_t offset;
    unsigned int limit, count;
    de_u32 issues;
    int allow_sparse, terminated, stopped;
} de_ntfs_run_cursor;

typedef struct de_ntfs_boot {
    de_view raw;
    de_u64 available_bytes, sector_field, mft_lcn, mirror_lcn, serial;
    de_u64 data_bytes, media_span_bytes, clusters, mft0_offset, mirror0_offset;
    de_u32 issues, sectors_per_cluster, cluster_bytes, record_bytes, index_bytes;
    de_u32 checksum, calculated_checksum, hidden_sectors;
    unsigned short bytes_per_sector, marker, sectors_per_track, heads;
    unsigned char cluster_code, record_code, index_code, media_type;
    int fields_present, complete_sector, data_bound_known, media_span_known;
    int record_size_known, index_size_known, record_budget_supported;
    int mft0_offset_known, mirror0_offset_known, seed_addresses_valid;
    int checksum_present, checksum_matches, geometry_valid, bootstrap_usable;
} de_ntfs_boot;

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
int de_ntfs_boot_read(const de_view *raw, const de_u64 *available, unsigned int major,
                      unsigned int minor, de_ntfs_boot *out);
int de_ntfs_record_read(const de_view *raw, unsigned int major, unsigned int minor,
                        de_ntfs_record *out);
/* Validate before writing. Source and written output spans must be disjoint. */
int de_ntfs_record_restore(const de_view *raw, unsigned int major, unsigned int minor,
                           const de_buffer *output, de_ntfs_record *out);
int de_ntfs_attributes_begin(const de_view *original, unsigned int major, unsigned int minor,
                             const de_buffer *restored, unsigned int limit,
                             de_ntfs_attr_cursor *out);
int de_ntfs_attributes_next(de_ntfs_attr_cursor *cursor, de_ntfs_attribute *out);
int de_ntfs_runs_begin(const de_view *pairs, const de_u64 *first_vcn, const de_u64 *count,
                       const de_u64 *volume_clusters, int allow_sparse, unsigned int limit,
                       de_ntfs_run_cursor *out);
int de_ntfs_runs_next(de_ntfs_run_cursor *cursor, de_ntfs_run *out);
/* Exact supplied-span exhaustion, not an attribute-record end marker. */
int de_ntfs_attr_list_begin(const de_view *value, unsigned int major, unsigned int minor,
                            unsigned int limit, de_ntfs_attr_list_cursor *out);
int de_ntfs_attr_list_next(de_ntfs_attr_list_cursor *cursor, de_ntfs_attr_list_entry *out);
/* Field framing is not name legality, lookup, membership or source authority. */
int de_ntfs_filename_read(const de_view *value, unsigned int major, unsigned int minor,
                          de_ntfs_filename *out);
int de_ntfs_index_root_begin(const de_view *value, unsigned int major, unsigned int minor,
                             de_u32 cluster_bytes, de_u32 expected_index_bytes, unsigned int limit,
                             de_ntfs_index_root *root, de_ntfs_index_cursor *cursor);
int de_ntfs_index_next(de_ntfs_index_cursor *cursor, de_ntfs_index_entry *out);
/* Expected block size/VBN are explicit assertions, not source authority. */
int de_ntfs_index_block_read(const de_view *raw, unsigned int major, unsigned int minor,
                             de_u32 expected_bytes, const de_u64 *expected_vbn,
                             de_ntfs_index_block *out);
int de_ntfs_index_block_restore(const de_view *raw, unsigned int major, unsigned int minor,
                                de_u32 expected_bytes, const de_u64 *expected_vbn,
                                const de_buffer *restored, de_ntfs_index_block *out);
int de_ntfs_index_block_begin(const de_view *raw, unsigned int major, unsigned int minor,
                              de_u32 expected_bytes, const de_u64 *expected_vbn,
                              const de_buffer *restored, unsigned int limit,
                              de_ntfs_index_block *out, de_ntfs_index_cursor *cursor);
#ifdef __cplusplus
}
#endif
#endif
