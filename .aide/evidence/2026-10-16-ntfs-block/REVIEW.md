# Implementing-agent review: protected NTFS INDX blocks

DE-W088; base `f2a00aaa9f4b771ac7a70afd404093de71d6be12`.
Exact tested native source `1a5f4f701d33f2311298392e20388c132bed844f`. Existing authority permits local
implementation, test/repair and reviewed dev/main synchronization across units.
This is implementing-agent review. Owner acceptance, release and storage
privileges remain separate; the original all-platform/storage 0.1.0 is unfinished.

`portable/ntfs/index_block.c` validates supplied INDX fixed fields, explicit
expected block size/VBN, the index-header span and supported flags. It checks
the bounded USA extent and every protected stride tail before copying anything.
The original bytes remain intact; restoration writes a separate caller buffer,
then initializes the existing entry cursor over its restored used span. Header,
array, size, signature, VBN and flag failures remain distinguishable. Invalid
controls, short buffers and overlapping spans preserve outputs. Fixup validity
and complete envelope validity have separate meanings. Reserved bytes/LSN stay
opaque. No source opener, I/O, allocation, lookup or public command is introduced.

`fixup.c/.h` shares only tail comparison, portable pointer-equality overlap
rejection and replacement from the original USA between actual FILE/INDX
consumers. Format-specific headers remain separate. Existing FILE signatures,
fields, issue semantics and validation-before-write ordering are preserved. The
existing NTFS library owns all of it; no parallel format implementation, new
library, speculative hierarchy or public SDK ABI is created. The source map
explains all 314 current files once.

The independent corpus passes **1,230 INDX cases**: supported sizes/profiles,
all byte truncations through two strides, per-stride and multiple torn tails,
USA extent/entry overlap, exact terminal space, bounded header fields/flags,
full VBNs, invalid controls, short buffers, alias directions, quota/terminal
semantics and names/child trailers crossing protected tails. Readonly guard
sources and destination sentinels establish bounds and failure immutability.
All **964 FILE** and **1,502 filename/index** cases also pass.

The clean Windows x64 Release campaign passes **159/159 registered
native groups**, **61 standalone C++ headers**, all nine NTFS C sources
and both private headers under strict GCC C90, and **244 tooling tests
(two symlink cases skipped)**. Build boundaries, source map, imports/PE flags,
manifest/context and all 1078 original registered/build
input hashes pass with a clean checkout before/after. The
[full campaign](qualified-1a5f4f70/summary.json) retains commands, logs, compiler,
SDK/runtime, artifact identities and actual results. There is no selected-suite
substitution or changed deadline to obtain this result.

An isolated Win32/WOW64 fixture derived from the exact x64 codemodel passes the
same three corpora, two standalone headers and import/PE checks. Its
[supplement](win32-1a5f4f70/summary.json) binds the exact source and generator
hashes. It is three parser probes on this host, not a full Win32 product,
historical Windows/DOS or public ABI qualification. The normal product x64 gate
is unchanged. The supplementary generator is subsequently registered for
retrieval; post-campaign metadata/context checks and that explicit registry-only
exception are recorded separately from the clean native input hashes.

The original working run passed 1,227 cases; three extra boundary cases were
added and passed before the exact-source campaign. Both working snapshots are
retained. Earlier failed campaigns remain failed at their original revisions;
their historical report/acquisition delay cause is not established here.

The code is suitable for ordinary source integration after metadata/staged-byte
closure. Next, define and implement source-bound directory acquisition with
exact record/name/stream bindings and finite quotas. Supplied framing alone
does not qualify index allocation, membership, collation, namespace/content,
physical media, writer/recovery, Setup or the complete original 0.1.0 scope.
No owner acceptance or release is recorded by this review.
