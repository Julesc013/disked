# Private exFAT root and system observation

DE-W067 combines the existing supplied-byte decoders through
`runtime/capture/exfat_capture.*`. The [owning profile](../spec/catalog/exfat-capture-prototype.json)
defines the expected behaviour. This private observer does not open a source,
mount a volume, traverse every file, extract content or admit a writer.

The caller supplies a source/window/epoch binding, a single typed upcase format,
finite budgets and the existing `RegionReader`. Compressed and literal choices
retain the private v1 observation shape. DE-W072 adds automatic interpretation
with a private v2 shape; the [command profile](../spec/catalog/exfat-command-prototype.json)
owns that extension. Existing held-file and worker v1 adapters still select an
explicit representation until automatic frames are implemented and verified.
Invalid requests are refused before calling the reader. Borrowed views follow
that port's immutable-lifetime contract; returned JSON owns its observations.

The reader validates the main boot region and follows its active FAT. It requires
complete root/system chains, exactly the required bitmap identities and one
upcase descriptor. Inactive bitmap descriptors remain candidates; their backing
data and inactive FAT entries are not substituted for active observations.
Known File sets can cross root clusters; their structural association is checked
without claiming NameHash verification or namespace uniqueness. Unknown critical
records and orphan secondaries prevent applicability. Benign unknown primaries
remain raw records; associated unsupported structures are not admitted.

The selected bitmap covers exactly the declared cluster bits, excluding reserved
tail bits. Root/active-bitmap/upcase clusters must be unavailable for allocation
and cannot cross-link. Upcase checksum, mapping count and mandatory mappings
must pass before publishing the little-endian mapping digest. Neither an
allocation bit nor a name hash proves ownership or filesystem health.

Automatic interpretation evaluates at most two candidates over the same copied
table bytes. A sole valid map is selected; two exactly equal maps are equivalent.
Different valid maps yield `exfat_upcase_representation_ambiguous`, without a
selected digest or applicability. Candidate initialization, completed evaluation
and validity remain separate. Resource exhaustion retains completed candidate
facts and accurately labels unfinished evaluation. Both candidates are charged
under the existing finite limits; choosing an encoding causes no extra source reads.

Every captured region retains its source offset, length and content digest.
Overlapping bytes must agree, and all regions are reread within the same request
budgets before applicability. This measures repeated agreement; it does not
establish an atomic snapshot, future freshness or physical source identity.
Returned applicability is explicitly scoped to root and active system metadata.

Read requests/bytes, total unique system-chain clusters, root records, copied
byte buffers and encoded output have finite limits. Retained-byte accounting is
conservative and cumulative: region copies, boot/system buffers, raw records,
the decoded map and its digest encoding are charged. Metadata containers are
separately bounded by the request/cluster/record limits. Budget or media failure
keeps accurately labeled prefixes and withdraws applicability.

The native `exfat_capture_probe` consumes generated sparse image fixtures only.
`tests/images/test_exfat_capture.py` independently checks geometry, exact read
order and offsets, original records, bitmap counts and complete mapping digests.
It exercises fragmented and inactive-copy fixtures, malformed chains/descriptors,
finite budgets, faulty readers, changed bytes and real protected/read-only views.
Working results and later exact-source qualification are separate evidence.

Held ordinary sources and contained explicit-format readers now have separate
local qualification. Current work binds automatic interpretation and the common
exFAT command/frontends, then paged directory/name and file-content observations
including ValidDataLength zero filling. The original full platform/storage 0.1.0 programme remains unchanged;
owner, physical-device, production recovery/writer and release gates stay separate.


DE-W067 reaches local implementing-agent review at exact `bba3d600`: 121 image
cases in nine methods, 19 selected native groups, one private header, imports,
context/input hashes and 242 tooling tests with two skips pass. The clean sparse
checkout contains every registered/build input and all current implementation,
tests, spec, docs, tools and external files; unused historical evidence is
excluded. This is not a fresh full native suite or complete archive checkout.
Repository evidence is `.aide/evidence/2026-10-14-exfat-capture-qualified/`.
Continue actual held source/worker and coherent namespace/tree/content integration;
owner, other-platform/storage, production and full original release remain.


DE-W072's automatic supplied-region stage is locally reviewed at exact clean
sparse `6edabcc7`: 146 image cases/13 methods, four selected native groups/four
headers, 63 file/69 worker regressions and 242 tooling tests with two skips pass.
[Evidence and stage review](../.aide/evidence/2026-10-14-exfat-auto-qualified/README.md)
retain the complete registered/build input closure and excluded unused archive.
Automatic file/frame/worker transport and normal command/frontends remain;
no fresh full native suite, whole W072 acceptance or original full0.1.0 claim.


The automatic transport stage is locally reviewed at exact clean sparse
`33ee364a`: four selected native groups/four headers, 146 observer, 89 file and
94 worker cases plus 242 tooling tests/two skips pass. [Transport evidence](../.aide/evidence/2026-10-14-exfat-transport-qualified/README.md)
retains the typed v2 input/frame/file relationships, original logs and source
closure. That result does not qualify the subsequent command implementation.

The working Windows composition now supports:

```text
disked --json image inspect generated.img --view exfat --volume-offset 0 --volume-bytes 2126336
```

Supply the actual generated image's volume window. `--upcase-format` accepts
`auto` (default), `compressed` or `literal`. Automatic ambiguity is a failed
observation with both candidate findings; explicit selection remains recorded
and validated. No FAT controls or `--retain-capture` are admitted for this view.
The current private result covers root and active system metadata, with bounded
detail and explicit original/returned/omitted counts and full-array hashes.
It does not qualify a complete directory namespace, file content or extraction.

`runtime/capture/exfat_inspection.*` owns shared parameter validation, projection
and outcomes. `platform/windows/storage/exfat_reader.*` pins the ordinary file
and binds the owned process; `exfat_worker.*` owns that process protocol. These
are separate lifetimes and responsibilities within the existing short owners.
The same service feeds CLI/protocol/GUI/TUI/shell. Source handles and the callback
slot survive frontend wait expiry until actual worker exit; static commands and
inert review do not probe the image. Working frontend checks pass 33 cases,
including large-detail omissions, reader faults and retained source ownership.
Exact full-native qualification is pending.

W072 full exact60376a0e campaign failed:132/140native groups passed, eight failed. The command is not composition-qualified. [Retained failed campaign](../.aide/evidence/2026-10-14-exfat-command-exact-failed/README.md) records actual launch error5, directory-copy contrasts and unresolved causes. Working repairs and a new exact campaign remain; main was not promoted.
