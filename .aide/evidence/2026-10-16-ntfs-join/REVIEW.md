# Implementing-agent review: captured NTFS stream joining

DE-W085, base `f2ad2fc8a9156f9c2512aae1b6eec885dc6183f5`.
Tested source `23ceeb24bfca3cce9b2a06eaeca2a9d5f18f5a7a`. Implementing-agent review is under the existing local
development/test/repair and dev/main source-synchronization grant. Owner
acceptance, physical/elevation/customer/install/signing/publication authority
remain separate. Original all-platform/storage 0.1.0 remains unfinished.

The private C++14 `runtime/capture/ntfs_stream.*` joins captured base/extension
FILE records for one exact type/raw-name ordinary stream. It reuses the existing
C90 FILE restoration, attribute, resident-list and run decoders. Context assertions
are checked independently of reference sequence, base owner, attribute instance,
exact original name and lowVCN. Unknown unrelated attributes remain opaque;
ambiguous, omitted, stale or missing selected records cannot produce a usable
stream. Missing input reports every unique selected full 48/16 reference only
after complete list and present-record validation;
it is neither an acquisition grant nor an automatic retry after stale data.

Resident results own exact value bytes. Nonresident results preserve separate
allocated/data/initialized sizes, reset mapping deltas per extent, require exact
contiguous VCN coverage and reject sparse/flagged mappings and physical overlap
in this ordinary profile. Continuation counters are not treated as first-extent
authority. No typed stream exists until all checks and report serialization
succeed. Partial facts remain observational; snapshot/current-source/effect
authority stay false. No provider, OS I/O, callback or public ABI is introduced.

Bounds/ownership review: request controls are validated before construction;
the supplied record array is borrowed, so count rejection does not copy it.
Selected count/byte quotas precede parsing. Original FILE buffers remain stable
and readonly; every decoded record owns its restored RAM. Per-record attributes
are frozen before selection keeps their addresses. The returned stream contains
owned vectors/scalars only. Record/part/run report charges precede retention and
checked arithmetic precedes allocation comparisons. The probe frees every input
guard before reading a successful result, exercising output lifetime directly.

The clean Windows x64 Release campaign passes **298 protected-record join cases**,
**25 selected native groups**, **9 standalone headers** and
**244 tooling tests with two skips**. All **1055
registered/build inputs** remain unchanged in the clean checkout. Actual
compiler/SDK/static-runtime configuration, probe imports/PE flags, build/header
usage, source-map, strict C90 regressions, manifest and context checks pass.
[Exact commands, results and artifact hashes](qualified-23ceeb24/summary.json).
The build and test selection is explicit; neither the complete product test
suite nor every header/ABI/platform is claimed. Previous complete campaigns
remain bound to their own source revisions. No deadlines or resource limits
were relaxed to obtain a pass.

Three development fixture errors remain in `working/`: a duplicate Python name
keyword stopped fixture construction before invoking the native probe; a random
used_bytes change remained bounded and was wrongly expected to invalidate FILE.
The latter now has separate passing bounded-slack and failing out-of-bounds
cases, preserving the original DE-W076 envelope rule. An added positive case
also mutated a previously yielded request; the fixture factory now freezes each
request/expectation, preserving the separate missing and complete cases. All
original snapshots/logs remain. Pre-integration review found first-only dependency
discovery insufficient for reordered MFT lists. The revised contract requires the
complete validated missing set, deduplicates record fetches and clears suggestions
after known invalidity. The original 287-case qualification remains retained at
`first-reference-qualified-20eedfb7`; it passes its original contract and does
not qualify the stronger discovery model or actual source acquisition.

Two tooling symlink cases skip. Actual native file-symlink evidence remains
unavailable with Windows error1314 in the selected file fixtures. Native record
acquisition and its provenance, nonresident attribute-list acquisition,
arbitrary MFT discovery, namespace/content, physical storage, other hosts,
production writer/recovery, Setup, owner and release qualification remain open.
The existing public NTFS command is still bootstrap-scoped. Supplied-context
matching does not establish source freshness or allocation ownership.

Conclusion: eligible for ordinary source integration after current metadata and
staged-byte closure; record actual Git writes separately. Next connect bounded
source-bound MFT record/nonresident-list acquisition through the existing reader
and contained-worker lifecycle, with independent generated-image fixtures and
exact original-source rereads. Preserve the full original0.1.0 scope and gates.
