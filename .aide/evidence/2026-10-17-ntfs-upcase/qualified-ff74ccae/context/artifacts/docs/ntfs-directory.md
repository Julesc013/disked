# Source-bound NTFS directory indexes

DE-W089 connects the existing supplied-reader bootstrap/stream closure to
resident roots, multi-level INDX graphs, resident/nonresident bitmaps and
source-bound attribute-list extensions. Its [execution contract](../spec/catalog/ntfs-directory-prototype.json)
defines exact references, raw names, mappings, graph/bitmap and quota outcomes.
The source-owning capture Observer supplies checked streams/reads/budget charging;
`ntfs_directory.cpp` owns bounded graph collection in the existing capture target.

Exact source `7bb6153a9bc86710dff9972f493c9ff14280caed` passes 227 independently constructed guarded cases,
all 160 registered x64 native groups, 63 standalone C++ headers, strict C90/header
checks and 244 tooling tests (two skipped). The selected Win32/WOW64 supplement
passes four groups and four headers. Its original failed receipt and corrected
recipe provenance remain explicit. [Review and exact evidence](../.aide/evidence/2026-10-16-ntfs-directory/REVIEW.md).

Local collection/bitmap completeness, successful final source rereads and
applicability are separate properties. Supplied source identities are assertions,
finite equal rereads are not atomic snapshots, and no namespace/collation,
target membership, global cluster allocation or storage-effect authority follows.
Native held-file/replay/worker/frontend admission, complete namespace/content,
original platform/storage0.1.0 and owner/privilege/release gates remain required.
