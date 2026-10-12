# Implementer review: FAT allocation metadata

Reviewed the bounded C90 volume, allocation-entry and chain implementations against
the predeclared profile. Geometry uses checked byte quantities and cluster-count
classification. Packed entries preserve neighboring/high-nibble raw data. Caller
workspace and an explicit cap bound chain work; missing/budget/cycle outcomes are
distinct. No provider I/O, allocation, authoritative-copy selection, effect path or
shipping command is introduced. Inputs and output/workspace error behavior are
tested independently, including inaccessible read boundaries and competing copies.

The exact clean Windows build, 1,335 independent cases, protected-memory checks,
87 native groups and eight headers pass. GCC 15.2 confirms strict C90 syntax only.
The first partial-build dependency diagnostics were resolved by generating existing
headers in the complete build; no checks, provider/effect or resource rules changed.

This is implementer review, not independent-person or owner acceptance. Directory,
name, extraction, global allocation, provider/frontend and host qualifications stay
open; it does not establish full FAT or DiskEd 0.1.0 completion. Continue concrete
filesystem and recovery work under the full programme and separate storage/release
gates. Preserve original spec IDs, source ownership and historical evidence.
