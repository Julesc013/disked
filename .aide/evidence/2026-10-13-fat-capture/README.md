# Bounded FAT volume/tree and file capture: 2026-10-13

Native source `f98712a44ccf993c54e6d67b23a445ecdfa1725c`; base `41802dd2d38d4884244fcf3926a328ff04cb12d6`.
DE-W027's expected contract was committed before implementation at
`bfc0fb411de2ff765eb42a6128a2b40329d0a50e`. The standing local development,
tests/implementer-review and tested dev/main synchronization grant applies.
Owner acceptance and whole product/platform/storage/release gates remain separate.

## Result and boundaries

The existing C90 FAT allocation reader now supports checked table-relative
cell requests and exact two/four-byte decoding, preserving the previous full-view
API. A table need not be resident to inspect one entry. The private shared region
reader has one header/interface target; MapRegionReader remains its type alias.
Actual callback/view semantics are preserved and no unrelated map/GPT dependency
is added to FAT capture. Existing source ownership stays intact; 205 source files
are documented once. No second tree or manual source inventory was introduced.

`runtime/capture/fat_capture.*` observes selected-copy FAT volume geometry,
fixed/chained roots, breadth-first directory nodes, exact original name/record
provenance, chain outcomes and file-content versus allocated/slack extents.
Long-name sets can cross sectors/noncontiguous clusters of a logical directory.
Dot/dotdot, end markers, deleted/orphan sequences, cycles, repeated directory
starts, referenced-tree cross-links and conflicting/uncompared copies remain
distinct. Every observed cross-link owner is annotated. File payloads are not
read to list extents. Names are not lookup paths, normalized text or access rights.

Positive node/depth/chain/record/read/byte/orphan/output budgets are checked before
callbacks. Requests stay in an explicit volume/source window and are <=4096 bytes.
Returned data is owned; short/oversized/null/throw/overlap-changing readers stop
with prior partial observations and explicit diagnostics. Output accounting uses
conservative reserves and signals omitted nodes/budgets. This is bounded payload,
count and work policy, not a precise allocator/RSS or wall-clock guarantee.

`providers/image/fat_file.*` opens only ordinary Windows files with read rights,
held parent/file identities and no write/delete sharing. It recaptures each
accepted region and compares exact bytes, overlaps and metadata generations.
Region digests and offsets bind the source window. observed_stable is repeated
observation agreement; it is not an atomic filesystem snapshot, whole-file hash,
physical/media safety, extraction or write permission. Synchronous waits need
external containment before frontend admission. Empty captures cannot qualify
stability. Capture epochs refuse overflow without wrapping/reuse.

The code stays in private library/probe targets, outside disked.exe's generated
closure. Public command/version stays dev.42/21. No mount, extraction, customer,
physical, elevation, installation, signing or release effects were performed.

## Actual verification

- 20 independent methods execute 149 cases: 138 supplied-reader/cell and 11
  ordinary-file cases. They cover FAT12/16/32 roots, nonzero/wide sparse windows,
  cross-sector cells and names, nested/dot/end/deleted/orphan records, exact file
  extents/no payload reads, cycles/reuse/cross-links/copy conflicts, every exercised
  read failure and all declared budget families.
- Generated actual FAT image files preserve their complete before/after hashes;
  directory/hardlink sources refuse. Test-only reread/error/metadata faults deny
  stability; the normal build ignores those controls and preserves source bytes.
- Real protected stream-cell inputs and unchanged error-output boundaries pass.
  Prior 1,335 allocation and 6,790 directory/name cases remain in full regression.
- Exact clean unprivileged Windows x64 MSVC 19.44.35228/toolset 14.44.35207,
  SDK 10.0.19041.0, CMake 4.2.3 and Python 3.14.7 build/launch/import evidence.
- All 91 native groups pass; 10 independent headers compile. Generated checks
  cover 135 targets/3558 quoted edges.
- 215 tooling tests run: 213 pass,
  2 skip. Index/structural/manifest/context/source-map checks pass.
- GCC 15.2 validates strict C90 syntax of the three FAT C sources only; no GCC
  runtime/ABI or historical/other-host qualification follows.
- 500 SHA/Git-blob bindings and 454 build
  inputs retained. Hashing does not semantically review every bound source file.

Commands, raw logs/CMake projects/codemodel, header usage, context archive,
input/output case batch hashes, executable/library identities and import observations
are retained. Local artifacts: .aide-local/artifacts/DE-W027-fat-capture-f98712a4/.
No release artifacts were published or signed.

## Review findings and remaining work

Review caught a dimension inconsistency: a failed directory read could overwrite
an already established chain-end label while leaving its completion flag true.
The partial-result handler now preserves established end/empty/fixed-root status;
every actual read boundary has a failure case. Invalid geometry, unchanged output,
lookup/metadata/privilege rules and expected outcomes were not weakened.

Observed-tree allocation is not a global FAT sweep or lost-cluster proof. FSInfo,
backup metadata, namespace/consumer compatibility, extraction and command/worker/
frontend admission remain further capabilities. Other hosts and true storage
failures remain unverified. This implementer review does not supply independent-
person/owner acceptance, production journal/recovery, physical authority or full
all-platform/storage 0.1.0 completion. Earlier evidence retains its exact source.

## Reproduce and audit

```text
.aide-local/venv/Scripts/python.exe -X utf8 .aide/evidence/2026-10-13-fat-capture/reproduce.py --source-revision f98712a44ccf993c54e6d67b23a445ecdfa1725c --existing-clone .aide-local/owned-layout-clean-2c731a1c/checkout --output .aide-local/fat-capture-clean-new --gcc-executable PATH_TO_EXISTING_GCC_15_2
.aide-local/venv/Scripts/python.exe -X utf8 .aide/evidence/2026-10-13-fat-capture/audit_retention.py
```

Use a clean owned local clone, fresh output and pinned dependencies. Audit checks
retained applicability, not a fresh native run or authority. A later integration
head contains metadata/evidence; native qualification remains at the named source.
