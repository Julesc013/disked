# Supplied-reader NTFS bootstrap

DE-W079 connects the existing boot, FILE, attribute and mapping primitives through
the shared `RegionReader`. Its [execution contract](../spec/catalog/ntfs-capture-prototype.json)
defines expected behaviour independently of the implementation and tests. This is
a private observation collector, not a native file opener or admitted NTFS provider.

The caller supplies an exact source/window/epoch context and an explicit NTFS3.0
or3.1 parser profile. The collector owns a copy of that request and reader before
the first callback, checks every absolute extent, copies returned bytes, retains
region hashes and rechecks all observed regions. Finite budgets cover attempted
reads, returned bytes, raw retention, attributes, runs and output. Equal rereads
do not establish an atomic snapshot or current-source authority.

Primary and mirror FILE0 candidates remain independent observations. Valid USA
tails are restored into separate RAM; original bytes are never changed. Mirror
comparison uses meaningful used bytes after restoration and excludes the USA
array, so differing update sequences or unused slack do not select a winner or
invent a conflict. A differing payload or invalid mirror withdraws applicability;
it never triggers fallback, repair or a write.

One valid ordinary unnamed primary MFT DATA mapping must account for its allocated
cluster span, initialized records and physical placement without self-aliasing,
boot/mirror overlap or disagreement with the seed record. Logical FILE3 is read
through that mapping, including run splits. Its resident VOLUME_INFORMATION value
provides observed version and raw flags; the version must match the requested
profile. Header record numbers are bound when that optional header field exists.

Malformed/unsupported metadata, changed source bytes, failed/short callbacks and
budgets retain an explicit observation prefix and diagnostic. The source-bound
[record closure](ntfs-closure.md) extends supported MFT/Volume list dependencies.
Held ordinary sources, contained workers and common frontends have their separate
revision-bound evidence. General MFT payloads and namespace/content remain work.
Dirty flags and an applicable bootstrap are not filesystem health or recovery
qualification. Native/platform/physical writer and release claims require their
own applicable evidence.

Pre-qualification review found three cases where `e37848a5` reported applicability
despite retaining a failed mapping in an additional metadata attribute. The
[original probe results](../.aide/evidence/2026-10-16-ntfs-capture/mapping-baseline-e37848a5/summary.json)
remain retained. The correction distinguishes completed attribute headers from
valid ordinary mappings and propagates failure to the selected record. Exact clean `000ecb77` passes 154 bootstrap cases, all 16 selected x64 native
groups, three headers, 242 tooling tests/two skips and dependency/import/context
checks. GCC/Clang syntax checks cover the C90 primitives and C++14 collector.
Supplementary x86 probes pass the same 154 bootstrap cases, five NTFS groups and
two headers on the recorded Windows x64 host/WOW64. Both architectures also pass
259 attribute/632 mapping/1,729 boot/964 record cases. This is not a complete native
campaign, full Win32 product or older-host qualification.
[Evidence and implementing-agent review](../.aide/evidence/2026-10-16-ntfs-capture/REVIEW.md).
