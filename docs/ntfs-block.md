# Protected NTFS index blocks

DE-W088 adds private supplied-byte INDX observation, separate-buffer restoration
and bounded entry-cursor initialization. The [execution contract](../spec/catalog/ntfs-block-prototype.json)
defines fields, expected block/VBN, USA spans, failure immutability and lifetimes.
`index_block.c` owns the format header; `fixup.c/.h` shares only actual FILE/INDX
tail mechanics. `index.c` retains entry semantics in the existing NTFS library.

Source `1a5f4f701d33f2311298392e20388c132bed844f` passes 1,230 guarded INDX cases,
964 FILE cases, 1,502 filename/index cases, all 159 registered x64 native
groups, 61 C++ headers, strict C90 sources/headers and 244 tooling
tests(two skipped). The isolated Win32/WOW64 fixture passes the same three
corpora and two headers. [Review and exact evidence](../.aide/evidence/2026-10-16-ntfs-block/REVIEW.md).

The block result borrows original bytes; a successful cursor borrows the
separate restored buffer. Both lifetimes belong to the caller. No source I/O,
filesystem lookup, namespace or physical-storage authority follows from framing.
Source-bound directory acquisition, full NTFS, original platform/storage 0.1.0,
owner acceptance and privilege/release gates remain open.
