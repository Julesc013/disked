# Supplied-byte NTFS directory envelopes

DE-W087 adds private FILE_NAME and directory INDEX_ROOT/entry decoders.
The [execution contract](../spec/catalog/ntfs-index-prototype.json) defines
name/reference preservation, geometry, framing, terminal and quota outcomes.
Exact source `3df1a1c7` passes 1,502 guarded cases, 27 selected native
groups, 9 standalone C++ headers and strict C90 sources/standalone C header.
The original campaign failed only tooling fixture capacity checks. Correction
`cd65edcc` passes all 244 tooling tests(two skipped)
with native source/build/domain test inputs and artifacts unchanged.
[Evidence and implementing-agent review](../.aide/evidence/2026-10-16-ntfs-index/REVIEW.md)
retain exact commands, hashes, preparation failures and the regression selection.

Names retain their original UTF16LE units and full references. Safe framing is
separate from supported namespace/reference semantics; no normalization or
lookup authority is inferred. Directory entries preserve key/padding/child
boundaries and require an exact terminal under a finite header quota. No native
I/O, allocation, INDX restoration or directory traversal is introduced.

Protected index blocks, source-bound record/index acquisition and namespace/
content remain required next work. The original all-platform/storage 0.1.0 and
separate owner/privilege/release gates remain open.
