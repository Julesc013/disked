# Resumable FAT allocation traversal

DE-W052 adds a private cursor to the existing portable FAT owner, in `fat.h` and
`allocation.c`. `init` establishes geometry and clears a caller-owned visited
bitmap. `request` reports the next exact table-relative cell without advancing.
`feed` decodes supplied bytes and emits one unique cluster observation. The
caller can suspend between any two cells and resume without resetting history.

Each step takes constant work and two or four supplied bytes. The visited bitmap
uses one bit per data cluster; initialization and memory capacity are explicit.
There is no 1,024-cluster whole-chain cap. A host whose address width or memory
budget cannot accommodate the bitmap must refuse or select a future separately
qualified strategy. This implementation does not claim all historical hosts can
walk every volume.

`running` and the pending disposition distinguish unfinished traversal from a
terminal result. End, free, bad, reserved, invalid start, cycle and truncated cell
remain separate outcomes. Cycle detection includes every earlier page and emits
no duplicate cluster. Short input terminates as truncated. Overlong/invalid feeds
and insufficient initialization capacity leave caller state unchanged.

The cursor and bitmap are paired private in-process objects. They are not a
serialized continuation, a provider identity, a freshness guarantee or an
execution grant. Supplied bytes must belong to a coherent selected FAT captured
by the caller. Runtime integration must bind source identity, capture epoch,
copy selection and metadata observations before using traversal for extraction.

The old bounded `chain_read`, monolithic volume capture, public file selector and
extraction formats retain their existing semantics. No public command changes
in this step. Larger directory trees, lossless names across page boundaries,
recursive extraction and metadata fidelity remain implementation work.

The expected [contract](../spec/catalog/fat-walk-prototype.json) precedes the
implementation. [Exact-source qualification](../.aide/evidence/2026-10-13-fat-walk/README.md)
at `112aa1e9` passes 109 native groups and 20 selected headers in the recorded
Windows lane. Tests compare FAT12/16/32 byte oracles across different page sizes,
chains up to 33,000 clusters, cross-page cycles and every terminal marker. Native
protected-page tests check short/exact cells, unchanged errors and bitmap tails.
These results qualify neither a complete filesystem nor physical operations.
