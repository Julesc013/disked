# Private exFAT root and system observation

DE-W067 combines the existing supplied-byte decoders through
`runtime/capture/exfat_capture.*`. The [owning profile](../spec/catalog/exfat-capture-prototype.json)
defines the expected behaviour. This private observer does not open a source,
mount a volume, traverse every file, extract content or admit a writer.

The caller supplies a source/window/epoch binding, an explicit compressed or
literal upcase representation, finite budgets and the existing `RegionReader`.
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

Next work binds held ordinary sources and contained readers, then paged
directory/name and file-content observations including ValidDataLength zero
filling. The original full platform/storage 0.1.0 programme remains unchanged;
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
