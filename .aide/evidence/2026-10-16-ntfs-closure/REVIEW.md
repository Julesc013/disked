# Implementing-agent review: source-bound NTFS record closure

DE-W086; base `09d37ee3448016a56997c1621dea47012f35e728`.
Native source **`540043c3253d71a221f89428a0ad88534cd67c9c`**; dependency-declaration correction
**`fb562480671eb72a81d24d5b3b3b72fa06a205cb`**. Existing user authority permits local implementation,
testing, repair and reviewed dev/main source synchronization. This is
implementing-agent review. Owner acceptance and storage/release privileges
remain separate; original all-platform/storage0.1.0 remains unfinished.

The collector now resolves bounded MFT/Volume extension FILE dependencies through
resident or completely captured nonresident ATTRIBUTE_LIST values. The private
joiner binds an external list to the exact original-base hash, full reference,
attribute instance, source/window/epoch and initialized length. Original protected
records remain owned separately from restored buffers; no synthetic FILE replaces
source bytes. The owned join result is exercised after freeing guarded inputs.

Reads require complete known mapping coverage and initialized/data bounds. Any
reachable validated missing full reference can advance discovery; gaps are never
guessed. Stale generation, wrong owner, mapping/alias errors and unresolved cycles
cannot produce a usable whole MFT map. Boot seed, complete allocation, physical
disjointness, all copied-region overlaps and final exact rereads remain checked.
Native source/code/process/capture identities and strict ordered parent replay
continue through the same owned worker. No opener, scheduler, privilege or physical
device path is added. Equal observations are not atomic snapshots or effect grants.

All six capture controls and wire frame/request encoding remain unchanged.
Private quotas are derived from them. List and selected stream mapping runs now
share one global private quota and scratch reserve. Buffer bounds are algorithmic,
with existing worker memory/time enforcement kept separate. Projection preserves
the scalar MFT summary and adds bounded closure/extension/attribute/run/part and
missing-reference lists with original hashes/counts/omissions. The complete
response ceiling stays524288 bytes.

Validation has two explicit phases:

1. A clean source campaign completed **157 registered native groups**:
   **156 passed; `build.boundaries` failed**. All runtime tests, including
   CLI/stdio/GUI/TUI/shell, protected source/list binding, actual ordinary files,
   sparse offset above4GiB and exited-worker exact frame replay, passed. New
   closure coverage has134 cases; earlier stream cases remain298. All
   **60 standalone headers**, actual compiler/SDK/static-runtime, seven
   probe/product PE/import/dependency observations, full tooling(244 tests,
   two skips), source map, manifest and source-bound context stages were retained.
   The separate boundary-audit stage also failed on the same stale declarations.
   [Original complete campaign](full-campaign-540043c3/summary.json) remains
   **failed**, with its complete raw logs and JUnit report.
2. Only the three expected transitive file/snapshot/worker closures were missing
   `disked_ntfs_stream`, already linked through the collector. Corrected metadata
   at `fb562480` passes **both boundary groups**, a fresh actual
   graph/include audit, full tooling(two skips), structural/manifest checks and
   a fresh context. JSON normalization proves exactly those three additions;
   all other nonmetadata registered inputs, source paths, CMake/build/test/runtime
   parameters and native artifact hashes remain identical. The clean correction
   checkout reuses the exact composed binary; its reported source identity remains
   `540043c3`. It is not represented as a fresh binary build or full green
   campaign at a newer revision.
   [Correction commands and applicability](build-correction-fb562480/summary.json).

Together the original campaign and the metadata-only retest resolve every
registered group for this unchanged native composition. No original failure was
rewritten to pass and no deadline, test or resource limit was weakened. This
reuse follows DE-REQ-074-03's actual-input condition. A future fresh build still
uses the retained full-campaign recipe; broad writer/physical qualification is
not inferred from this reuse.

Development failures remain in `working/`: an old empty-list fixture reused an
attribute instance; the intended empty-list case now has a unique instance and
the original duplicate bytes remain a separate refusal. An overflow projection
fixture multiplied an empty list and now uses actual nonempty run rows. Review
also reproduced a real quota defect: a list run plus two stream runs succeeded
under runs=2. Corrected exact3 succeeds and2 refuses without a typed result. The
earlier9657c4d5 build was stopped before native tests and qualifies nothing.

The read-only CI observation found no Actions runs for dev, no check runs for
fb562480 and no active workflow directory in this checkout. These local results
are not remote CI evidence. Two tooling symlink cases skip; native file-symlink
limitations remain in the actual fixture reports. General MFT/namespace/content,
compressed/encrypted/sparse streams, other platforms, physical storage, production
writer/recovery, Setup, owner and release qualification remain open. Next-decoder
research is only preparation, not a new implementation or execution contract.

Eligible for ordinary source integration after current metadata, context and
exact staged-byte closure. Record successful Git writes separately. Continue the
full original goal with bounded NTFS record/namespace work through existing
source/worker ownership; no full0.1.0 completion or owner admission is claimed.
