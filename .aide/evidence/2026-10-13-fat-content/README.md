# Private FAT content evidence

Native source `b1a6772ea258a698419d22a72e113c0d16298e01`, development base
`895c6c93bcb9c7407068593bbd65e36a99102a3e`. Source freeze and evidence/integration
revisions are separate. The user permits local implementation/testing/agent review
and tested dev/main synchronization; owner and release/storage privileges remain
separate.

The recorded clean Windows campaign passes 102 native test groups, 209 independent
content cases in 14 methods and 19 standalone header compilations. It retains
actual source blobs, build configuration, launch/import observations, artifact
hashes and complete tooling/native command logs. The summary states the exact
tooling count/skips. GCC checks are strict C90 syntax only, not runtime/ABI evidence.

The new private component maps captured FAT file metadata into checked logical
windows through a supplied reader. Cases include FAT12/16/32 fragmentation,
sector/allocation units, excluded slack, EOF, malformed/binding/copy refusals,
reader errors/short/invalid views, maximum windows and read budgets, a sparse
512-MiB logical file and source extents near unsigned64 maximum. Expected bytes
and physical positions are independently generated; source input remains intact.

Development diagnostics retain the initial fixture byte-cast compile error and
initial content failures. The product decoder was corrected to consume original
packed FAT12 windows once and full 512..4096-byte boot-sector receipts. Test
expectations were preserved. Those dirty development results are not clean-source
qualification or evidence that the earlier failed run passed.

This library is absent from the product executable's link closure. It admits no
public command, native source freshness, contained payload worker, destination
extraction, mount, writer or hardware claim. Retained metadata is not source-opening
authority. Other hosts, complete FAT extraction, production recovery, owner
acceptance and the original all-platform/storage 0.1.0 remain unfinished.

Reproduce with `reproduce.py`, the exact source, a clean owned local clone, fresh
output and the recorded GCC path. `audit_retention.py` checks retained integrity
and source binding; it does not rerun native tests.
