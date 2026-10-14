# Capture-local exFAT namespace

DE-W073 implements the [expected private contract](../spec/catalog/exfat-namespace-prototype.json).
The existing portable decoder already interprets file entry sets. The runtime
now combines those facts with the volume's upcase table for names and queries.

`exfat_upcase.*` shares the existing root observer's explicit/automatic selection
with an immutable supplied-table map. `exfat_namespace.*` associates directory
records, retains original UTF-16 units and distinguishes stored/calculated name
hashes from full comparison. Host Unicode normalization is not used.

A matching hash is only a candidate. Full mapped-unit comparison distinguishes
different names with the same hash. Two measured equal-name entries are ambiguous.
Missing records, invalid names, an unavailable map or incomplete comparison cannot
establish unique selection or absence. Timestamp and stream validity remain separate
from name matching; lookup gives no data-read or mutation authority.

Inputs are supplied capture facts, not live sources or permissions. This stage
does not collect directory chains, read file data, open paths or extend public
commands. Coherent tree collection, allocation/bitmap agreement, ValidDataLength
zero filling and held-source/worker/frontend admission follow. The original all
platform/storage 0.1.0 scope and owner/release gates remain unchanged.

Exact source `2545d078` passes the full 142 native groups, 50 standalone headers,
242 tooling tests/two skips and manifest/context/import/source checks. The corrected
private probe at `84d0c227` passes 303 namespace and 13 word-boundary cases on each
of x64/Win32, with two headers per architecture. The kernel and header inputs are
unchanged. An old-probe-only Win32 baseline measures 11 conversion mismatches.

[Retained evidence and implementing-agent review](../.aide/evidence/2026-10-15-exfat-namespace/README.md)
preserve initial failures and exact identities. This is local supplied-data
qualification; owner acceptance and full x86 product/platform/storage claims remain open.
