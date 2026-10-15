#ifndef DISKED_NTFS_FIXUP_H
#define DISKED_NTFS_FIXUP_H
#include "portable/primitives/view.h"

/* Internal mechanics only. Callers validate the record size, USA extent,
 * stride count and every protected tail before restoration. Views/control
 * objects are valid and disjoint; restore rejects overlapping byte spans.
 */
#ifdef __cplusplus
extern "C" {
#endif
unsigned int de_ntfs_fixup_mismatches(const de_view *raw, unsigned short usa_offset,
                                      unsigned int strides);
int de_ntfs_fixup_restore(const de_view *raw, unsigned short usa_offset, const de_buffer *output);
#ifdef __cplusplus
}
#endif
#endif
