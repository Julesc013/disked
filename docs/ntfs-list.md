# NTFS attribute-list parser development

DE-W084 implements the bounded supplied-byte entry cursor needed for later
attribute-list/MFT extension support. The [execution contract](../spec/catalog/ntfs-list-prototype.json)
defines framing, raw values, EOF and stopped-prefix outcomes before evaluation.
Source `65ca67d9` passes 561 protected-byte cases, 24 selected native
groups, 59 standalone headers, strict C90 syntax and 244 tooling tests
(two skips). [Exact results](../.aide/evidence/2026-10-16-ntfs-list/qualified-65ca67d9/summary.json) and
[implementing-agent review](../.aide/evidence/2026-10-16-ntfs-list/REVIEW.md) retain the scope and
limitations. The complete product suite was not rerun for this private decoder;
the selected regressions include existing NTFS/reader/frontend contracts.

An entry observation does not establish live reference/sequence validity or a
complete attribute stream. Borrowed names retain exact UTF16LE bytes. The parser
has no source/provider callbacks or storage effects; the existing NTFS command
remains bootstrap-scoped until source-bound joining is implemented and verified.

The first clean campaign rejected the new file through the explicit build-source
contract: 23 of24 selected groups passed; `build.boundaries` failed. The approved
NTFS source list is corrected without changing decoder code, limits or checker
rules. Its 32 negative fixtures pass. The original failure and contract are
retained in the [correction receipt](../.aide/evidence/2026-10-16-ntfs-list/build-contract-correction.json).
The corrected exact-source campaign above passes; the original failure remains retained.
