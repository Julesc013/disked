---
type: DiskEd Specification
title: Filesystem features and media capabilities
description: Qualify each operation against exact format features, consumers and address-space semantics.
resource: disked://spec/de-037
tags:
- disked
- storage
generated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
status: draft
disked:
  id: DE-037
  profile: disked-spec/1
  version: 0.1.14-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-031
  - DE-035
  requirements:
  - DE-REQ-037-01
updated:
  by: codex
  at: '2026-10-13T04:52:33.524866+00:00'
  scope: DE-W047 complete mapped-file backend at 20ecddbd; public extraction and owner gates remain open
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Filesystem features and media capabilities

## Capability predicates

Support is a tuple of operation, format/version/features, medium, access path, provider, host, consumer compatibility, current state and evidence. Recognition, inspection, extraction, creation, check, repair, grow, shrink, move, mount and boot are distinct. A formatter does not install a filesystem driver or make the host able to mount its output.

Feature predicates record required/forbidden/unknown critical bits, sector and allocation-unit constraints, addressing ceiling, encryption/compression state and online/offline restrictions. Unknown critical features block mutation. Preserve arbitrary file contents opaquely unless a chosen operation requires content interpretation. Migration reports unrepresentable names, streams, ACLs, links and other metadata.

## Domain boundaries

Random-access byte sources, block devices, filesystem trees, sequential records, objects and device-control services expose different interfaces. Tape uses position/filemarks/records; optical media uses tracks/sessions/finalization; flux uses timings; zoned media uses zone/write-pointer constraints. None inherits ordinary partition writes by naming itself a drive.

Table conversion, filesystem conversion, image-container conversion, encryption transitions and pool reorganization require separate selected operation contracts. The future destructive-administration umbrella is routing only, not one unrestricted executor. Add concrete tape, optical, mounting and repair contracts with their implementation work and fault model, not as empty support badges.

## Normative requirements

### DE-REQ-037-01

Every filesystem/media capability MUST bind exact operation and feature predicates; recognition, creation, mounting and bootability MUST be reported independently.

**Verification:** Present known format with an unknown critical feature, a tape target and a consumer-incompatible format request; refuse the affected action without hiding inspection.

## DE-W076 supplied-byte NTFS FILE envelopes

The [private record contract](../catalog/ntfs-record-prototype.json) advances
NTFS inspection through the existing C90 checked layer. It observes a supplied
NTFS3.0/3.1 FILE envelope and validates every update-sequence tail before restoring
tail words into a separate caller-owned RAM buffer. Raw flags/identifiers and
malformed observations remain data. This is not boot/MFT addressing, attribute
or runlist traversal, volume recognition, mounting, creation or writer admission.

Repository evidence `.aide/evidence/2026-10-15-ntfs-record/applicability.json`
binds 964 independent cases, 11 selected portable groups, one header and 242
tooling tests/two skips to `c0749e22`. Its overall campaign failed byte-manifest
verification; `ce5efdae` corrects the LF manifest and passes fresh clean metadata
checks with all 989 registered/build/source inputs unchanged. Both failures and
the correction are retained. Other NTFS capabilities, original platforms/storage,
owner, physical writer/recovery and full release qualification remain open.

## DE-W077 supplied-byte NTFS boot geometry

The [boot contract](../catalog/ntfs-boot-prototype.json) separates the raw BPB
sector field, data/media/backup bounds, signed size encodings, record support
and checked initial MFT/mirror candidates. It reuses the existing C90 checked
layer; geometry is not complete volume recognition, current source authority,
mount/boot capability or writer admission. Later MFT records need validated
attributes and runlists, not a presumed contiguous layout.

Repository evidence `.aide/evidence/2026-10-15-ntfs-boot/qualified-aefee4cd/summary.json`
records exact clean `aefee4cd`: 1,729 boot/964 record cases, 12 selected portable
groups, one header and 242 tooling tests/two skips, with imports, C90 syntax and
source/context/manifest freshness. No full native, NTFS volume/provider/frontend,
other original platform/storage, owner or release qualification follows.

## DE-W078 supplied-byte NTFS attributes and mappings

The [attribute contract](../catalog/ntfs-attributes-prototype.json) reuses actual
FILE restoration before traversing attribute envelopes. It preserves opaque
features and continuation fields, validates applicable signed counters/VCNs,
bounds original names/values and keeps mapping prefixes, sparse encoding and
coverage distinct. A terminated bounded list is not a complete stream/namespace.

Repository evidence `.aide/evidence/2026-10-15-ntfs-attributes/qualified-6daed9fd/summary.json`
records exact clean `6daed9fd`: 259 attribute/632 mapping/1,729 boot/964 record
cases, 14 selected portable groups, one header and 242 tooling tests/two skips.
The baseline signed-field false positives and correction remain retained.
Attribute-list joining, payload interpretation, coherent source/provider/frontend,
original platforms/storage, owner, physical writer/recovery and full release
qualification remain open. There is no new source or effect authority.

## DE-W058 supplied-byte exFAT metadata

After local DE-W057 qualification, the [exFAT reader contract](../catalog/exfat-reader-prototype.json)
defines the next bounded format capability. Its expected boot-region/geometry/
checksum and allocation-cell observations use the existing C90 checked byte
layer. Main/backup provenance, exact raw values and unsupported features remain
separate. The official [Microsoft exFAT specification](https://learn.microsoft.com/en-us/windows/win32/fileio/exfat-specification)
owns format semantics; this private contract owns implementation limits and tests.
Checkpoint `38b6683a` implements the private decoder; working independent
oracle2320cases, protected/read-only input and focused native/C90/boundary checks
pass. Exact clean-source full qualification is running; working evidence is
retained under `.aide/evidence/2026-10-14-exfat-working/`. Allocation bitmap, upcase table,
directory sets, traversal, provider/frontend and actual host/storage qualification
remain subsequent capabilities. No mount, TexFAT transaction or writer claim follows.

## DE-W064 supplied-byte exFAT directory metadata

W058's final clean-source campaign at `1e938369` passed130native groups,
42standalone header compilations,242tooling tests with2skips and all four local
criteria. Exact source/build/import/context/artifact identities and local agent
review are retained under `.aide/evidence/2026-10-14-exfat-qualification/qualified-1e938369/`.
Original failed runs remain retained. Owner and full product acceptance remain separate.

The [directory contract](../catalog/exfat-directory-prototype.json) follows local
DE-W058 review. It binds fixed slots and complete entry sets, lossless original
UTF-16 units, exact entry-set checksums, calendar/offset observations and checked
stream extents. Expected outputs precede implementation. Unknown critical members
remain unsupported; benign secondary bytes and reserved fields remain preserved.
Stored name hashes do not establish equality without the volume's qualified
upcase mapping, and stream extents do not establish allocation without a matching
bitmap. Bitmap/upcase, coherent paging/source identity, public provider/frontend,
ValidDataLength zero filling and all original storage/platform release gates
remain separate required capabilities. The private C90 decoder and independent
native probe/oracle are now implemented after recorded W058 native-stage review.
Scratch checks passed2316cases/9methods; integrated native/header/import/source
qualification at `44c8b090` passed2316cases/9methods, tenparser/guardgroups,
oneboundaryfollowup, oneprivateheader and C90/import/context/source checks. The
initial missing-generated-registry failure and separate repair are retained in
`.aide/evidence/2026-10-14-exfat-directory-qualified/`. Prior130native results at
`1e938369` apply only to unchanged sources; this is not a freshfullsuite claim.
Neither scratch success nor directory association
establishes allocation, name equality, current source authority or public use.

## DE-W065 supplied-byte exFAT bitmap intervals

The [allocation contract](../catalog/exfat-allocation-prototype.json) closes the
next expected bitmap descriptor/interval behavior before implementation. It
observes exactly requested cluster bits from a checked bounded supplied window.
Root cardinality, active FAT/bitmap source pairing, present-source coherence and
ownership remain runtime gates; reserved tail bits do not enter interval counts.
Upcase validation and full name comparison remain required before lookup claims.
The private C90 descriptor/interval decoder is implemented. Working checks pass
2554independent cases/4methods and11focused native groups, including read-only/
protected bounds. Exact clean-source `be410d95` qualification passed13fresh
native groups, oneheader and C90/import/source/context plus localreview. Tooling
freshness checks need a fixed-source follow-up after concurrent specification edits;
these supplied-byte counts do not establish current free-space or ownership.

## DE-W066 volume-specific upcase and names

The [upcase contract](../catalog/exfat-upcase-prototype.json) binds original
table bytes/checksum, complete code-unit mappings and mandatory ASCII behavior.
Compressed and uncompressed decoding remain explicitly selected representations;
all names retain original units. NameHash narrows search but never establishes
equality without comparing the full volume-mapped units. Root/chain/source/epoch
binding and coherent directory uniqueness remain later runtime qualification.
The private C90 descriptor/stream/mapping/hash/fullcomparison is implemented.
Working checks pass244scenarios/9methods and13focusednativegroups, including
independent complete-map/checksum/namecomparison and protected/read-only output
capacity checks. Exactclean/source/import/context/tooling qualification and local
review remain; these facts do not establish source-bound lookup or uniqueness.

## DE-W025 supplied-byte FAT allocation reader

The [private FAT profile](../catalog/fat-reader-prototype.json) defines bounded
FAT12/16/32 layout, allocation-entry and chain observations before native
evaluation. Reuse the portable C90 byte/checked-arithmetic layer. No native I/O,
allocation, mount, write or public command is admitted by this work. Exact raw
values and partial/corrupt/budget outcomes remain distinct. Sector size, volume
capacity and caller-selected FAT copies are explicit; format labels are not
classification authority. Directory/name, extraction, whole-allocation, provider,
frontend and actual host compatibility require subsequent evidence. The full
all-platform/storage 0.1.0 scope is unchanged.

The allocation metadata slice is implementer-reviewed at source `97a377d7`, with
1,335 independent byte cases, protected bounds, 87 native regression groups, eight
headers and strict GCC 15.2 C90 syntax checks. Retained evidence is under
`.aide/evidence/2026-10-13-fat-allocation/`; owner acceptance remains pending.
This qualifies the supplied-byte metadata scope on the recorded Windows host,
not complete FAT inspection, GCC runtime, directories, extraction, mounting,
frontend dispatch, historical targets or a writer. Continue the remaining
filesystem and recovery capabilities under the full programme.

## DE-W026 lossless FAT directory and name observations

The [directory/name profile](../catalog/fat-directory-prototype.json) extends the
existing supplied-byte FAT reader. Keep exact OEM short-name bytes, UTF-16 units,
structural association, encoding validity, character issues and escaped display
separate. No normalization, guessed code page, timezone, lookup uniqueness or
file access follows from a checksum-matched name. Bound complete long-name sets
and retain malformed/deleted/end observations without effects. Traversal, whole
allocation, extraction, providers/frontends and actual consumer/host admission
remain unfinished work within the full all-platform/storage 0.1.0 programme.

The directory/name slice is implementer-reviewed at source `205e6cd8`, with
6,790 independent byte cases, protected records/name sets and 89 native groups.
Evidence under `.aide/evidence/2026-10-13-fat-directory/` retains original
representations and separate correlation/encoding/canonical/display outcomes.
This does not close traversal, global allocation, lookup, extraction, provider/
frontend, actual consumer/host or full 0.1.0 admission. Header-using task contexts
bind both the allocation and directory/name contracts.

## DE-W027 bounded FAT volume capture

The [volume capture profile](../catalog/fat-capture-prototype.json) connects the
existing FAT decoders to bounded directory-tree and file-extent observations.
Explicit volume windows, FAT copies, positive budgets and record/slot provenance
are required. Retain incomplete, conflicting and cross-linked observations without
claiming global allocation health or extraction rights. A separate ordinary-file
read-only adapter binds actual file generations and repeated region observations;
it does not establish an atomic filesystem snapshot or physical/media safety.
Worker/command/frontend, extraction, actual consumer/host and writer qualification
remain separate work within the full all-platform/storage 0.1.0 programme.
The bounded capture slice is implementer-reviewed at source `f98712a4`, with
149 independent supplied-reader/cell/ordinary-file cases and 91 native groups.
Evidence under `.aide/evidence/2026-10-13-fat-capture/` binds streaming allocation
cells, tree/name/extent provenance and actual repeated ordinary-file observations.
Global allocation, lookup/extraction, worker/frontend admission, other hosts and
production storage/recovery/release gates remain open; owner acceptance is pending.

## DE-W028 global FAT allocation observation

The [allocation scan profile](../catalog/fat-allocation-scan-prototype.json) adds
optional paged data-cluster scanning and bounded graph analysis to existing volume
capture. Tree coverage, allocation coverage, FAT-copy agreement and finding-detail
completeness remain separate. Unreferenced allocations do not imply recoverable
content, repair authority or filesystem health. Default tree-only capture remains
unchanged. Auxiliary metadata, namespace/consumer, extraction and worker/frontend
admission are further capabilities in the full all-platform/storage programme.

The global allocation slice is implementer-reviewed at source `0e414ccd`, with
86 independent cases/21 actual ordinary-file cases and 92 native regression groups.
`.aide/evidence/2026-10-13-fat-allocation-scan/` retains exact prefix/category/graph/
comparison/detail dimensions. Auxiliary metadata, namespace, extraction, actual
worker/frontend/host and owner/storage/release qualification remain unfinished.

## DE-W029 auxiliary FAT metadata

The [auxiliary profile](../catalog/fat-auxiliary-prototype.json) defines header
flags, advisory FSInfo and backup-record observations before evaluation. Preserve
raw values and separate shape, historical driver state, allocation comparison and
backup agreement. No implicit source selection, repair or filesystem-health claim
follows. Existing default capture remains unchanged; namespace, extraction,
worker/frontend, consumer/host and full release gates stay in the programme.

The auxiliary slice is implementer-reviewed at `87e7e246`, with 257 independent
cases/24 ordinary-file cases and 94 native groups. Evidence is under
`.aide/evidence/2026-10-13-fat-auxiliary/`. Driver history, advisory applicability
and byte/record agreement remain separate from source snapshots, recovery and
filesystem-health authority. Namespace, extraction, actual worker/frontend/host,
owner and full 0.1.0 qualification remain unfinished.

## DE-W036 namespace and consumer-name observations

The [namespace profile](../catalog/fat-namespace-prototype.json) binds original
OEM/UTF-16 representations to explicit local name models. Preserve aliases,
encoding/eligibility uncertainty and directory coverage. Unique model lookup
returns capture-local IDs, with no path, access, mount or consumer admission.
Windows text API evidence does not qualify every FAT driver/host. Additional
consumer, chunked coverage, extraction, worker/frontend and release work remain
in the full programme.

The namespace slice is implementer-reviewed at `330c223c`, with 171 independent
cases (21 ordinary-file observations), 95 native groups and 12 headers. Evidence
is retained in `.aide/evidence/2026-10-13-fat-namespace/`. Original names, consumer
eligibility, collision/lookup observations and source applicability remain separate.
Mounted-consumer, larger/chunked coverage, extraction, actual worker/frontend,
host/owner and full all-platform/storage 0.1.0 qualification remain unfinished.

## DE-W037 contained FAT reader observations

The [contained reader profile](../catalog/fat-worker-prototype.json) binds exact
ordinary-file expectations, bounded captured regions and actual owned processes.
Parent verification reconstructs original observations before the session creates
an immutable snapshot. Completion, source applicability and actual exit remain
separate. Existing host quotas are preserved. Shared commands/frontends, larger
coverage, extraction and full platform/storage/owner/release admission remain open.

The contained reader slice is implementer-reviewed at `56effc8f`, with 109 cases,
96 native groups and 15 headers. Evidence is retained in
`.aide/evidence/2026-10-13-fat-worker/`. Exact file/window, process/domain and
independent region reconstruction do not admit public consumers or storage effects.
Shared commands/frontends, larger coverage, extraction, additional hosts and
owner/full all-platform/storage 0.1.0 qualification remain open.

## DE-W038 shared FAT image inspection

The [command profile](../catalog/fat-command-prototype.json) adds explicit byte-window
FAT inspection to the existing image.inspect identity. Map mode remains the default.
Canonical mode-specific controls and prototype results separate full observations,
coverage, display omissions, model outcomes and actual process/source context.
Qualification requires real CLI/stdio/GUI/TUI/shell evidence. This contract alone
admits no source effects, public storage ABI, additional platform or full 0.1.0.

DE-W038 shared FAT image commands at `57cfd113` have 62 focused cases, 97 native groups and 17 independent headers. Explicit window/lookup/model controls, captures and omitted-detail bindings are shared across five frontends. Evidence is retained in `.aide/evidence/2026-10-13-fat-command/`. Larger coverage, retained capture retrieval, extraction, mounted consumers and further hosts/storage/recovery remain open.

DE-W039 defines explicit bounded allocation windows in
`catalog/fat-allocation-window-prototype.json`. Requested interval and complete
volume coverage are distinct. A partial interval cannot qualify global allocation,
FSInfo free-count agreement, filesystem health or source snapshot. Existing
default global scan and source/process/wire budgets remain unchanged. Native
implementation and evidence are pending.

DE-W039 source 543826fe qualifies explicit allocation windows with 34 interval cases / 44 actual command cases and 99 native groups. Evidence: `.aide/evidence/2026-10-13-fat-window/`. Requested range, all-volume coverage, consumer/source applicability and authority remain distinct; larger directory/namespace/session coverage, retrieval/extraction and other platforms/storage are unfinished.

DE-W044 defines explicit bounded in-process retention and byte retrieval of
original verified FAT metadata frames in `catalog/fat-retention-prototype.json`.
Retained observations grant no source freshness, authenticated custody or
extraction/storage authority. Native implementation and qualification are pending.

## DE-W045 supplied-reader file-content windows

The [private content profile](../catalog/fat-content-prototype.json) defines expected
file-record, geometry, chain/copy and extent validation before payload callbacks.
A logical window returns exact owned content bytes and explicit short/error prefixes;
slack and excess allocation are excluded. Cross-links and unrelated incomplete
traversal remain observations, not source freshness or filesystem-health claims.
This is the payload-reading algorithm needed for extraction; exact native source
binding, containment, public commands and destination effects require their own
subsequent qualification. The all-platform/storage 0.1.0 objective is unchanged.

Source-bound DE-W045 qualification at `b1a6772e` retains 209 independent content
cases, 102 native groups and 19 standalone headers in
`.aide/evidence/2026-10-13-fat-content/`. Supplied-reader byte correctness is
separate from current source identity/freshness, contained public extraction,
other hosts and full product/storage/release admission.

## DE-W046 held ordinary-file content and owned readers

The [held-content profile](../catalog/fat-content-file-prototype.json) binds the
selected window to expected native source metadata and an exact metadata comparison
digest. Capture, payload and recapture share the held ordinary-file handle. The
parent reconstructs payload from ordered copied regions; actual owned worker
context remains necessary for snapshot provenance. Preserve partial prefixes and
late recapture disagreement without a future-freshness or atomic-snapshot claim.
Public extraction, destination effects, other hosts and the full all-platform/
storage 0.1.0 programme remain unverified.

Source-bound DE-W046 qualification at `955e26f3` retains 59 native content and 209 independent map
cases, 103 native groups and 20 standalone headers in
`.aide/evidence/2026-10-13-fat-content-file/`. Measured held-source byte correctness does not establish future freshness,
public extraction,
other hosts and full product/storage/release admission.

## DE-W047 complete mapped-file extraction

The [extraction profile](../catalog/fat-extraction-prototype.json) defines full
logical file copying through the existing ordinary-file acquisition engine.
Private plan2 binds logical source bytes and an explicit read-only backing image;
plan1 remains unchanged. Exact grants, no-clobber destination/map creation,
checkpoint flush/readback and resume checks apply. This is byte-content backend
work, not public command, recursive metadata-fidelity or physical writer admission.
The full all-platform/storage 0.1.0 scope remains unchanged.

Source-bound DE-W047 qualification at `20ecddbd` retains complete-file extraction and prior content/map
cases, 104 native groups and 20 standalone headers in
`.aide/evidence/2026-10-13-fat-extraction/`. Measured held-source byte correctness does not establish future freshness,
public extraction,
other hosts and full product/storage/release admission.


## DE-W052 resumable allocation-chain traversal

The [private cursor profile](../catalog/fat-walk-prototype.json) extends the existing
portable FAT owner with exact-cell request/feed continuation. Its caller-owned
visited bitmap spans page boundaries; cycle detection emits unique clusters and
does not reset when a page ends. The cursor has no whole-chain step cap, while
bitmap addressability/capacity and caller work budgets remain explicit. No host
I/O or trusted persisted continuation is introduced. Existing bounded capture,
selectors and extraction formats remain unchanged. Source/capture binding, paged
directory traversal and recursive extraction require subsequent integration;
this primitive does not admit a filesystem, provider or historical host.


## DE-W053 source-bound directory pages

The [private traversal profile](../catalog/fat-traversal-prototype.json) uses the
qualified allocation cursor and existing lossless directory/name decoders to
traverse larger trees through bounded pages. Source/window/copy/capture/epoch
binding, mandatory applicability observations, explicit memory/queue/depth and
page budgets, unique source-offset identities and retained partial name records
are part of this prototype. Pages are historical observations rather than a
trusted serialized continuation, native source-opening right or extraction grant.
Held native sources, contained workers and recursive destination metadata effects
remain separate work. Existing capture/selector/plan versions remain unchanged.


## DE-W054 held-file and contained tree pages

The [native paging profile](../catalog/fat-tree-file-prototype.json) binds one
ordinary read-only source and ancestor generation closure across pages. Native
region rereads/checks, pure parent replay and actual owned process/code/request/
epoch context are separate evidence layers. One bounded anonymous slot uses
copy/validation/acknowledgement before reuse; aggregate tree size is not its cap.
Cancellation/publication and confirmed process exit remain separate. Retained
pages confer no present access, atomicity or mutation authority. Normal readers
reject fixture controls; public traversal/recursive destination work remains.


DE-W066 reaches local implementing-agent review at exact clean source `e43f00fb`.
Its private supplied-byte upcase descriptor, streaming map and complete name
comparison pass 244 independent scenarios, 15 selected native groups, one header,
strict C90/import/context/source checks and 242 tooling tests with two skips.
Repository evidence at `.aide/evidence/2026-10-14-exfat-upcase-qualified/`
separates this result from the prior complete native suite.
Continue bounded root/active-FAT/bitmap/upcase source coherence, then tree/content
and native integration. The original full platform/storage 0.1.0 and owner,
production writer/recovery, privilege and release gates remain unfinished.


DE-W067 binds the existing exFAT decoders into bounded root/system observations
through the existing RegionReader; [its expected profile](../catalog/exfat-capture-prototype.json)
fixes main-boot/active-copy selection, root cardinality, checked system chains,
bitmap membership and exact upcase mapping before implementation. Inactive bitmap
descriptors are historical candidates, never substitutes for active bitmap data.
Partial coverage or reread disagreement withdraws applicability. Held native
source, recursive tree/content, frontend and original full release remain later work.


DE-W067 reaches local implementing-agent review at exact `bba3d600`: 121 image
cases in nine methods, 19 selected native groups, one private header, imports,
context/input hashes and 242 tooling tests with two skips pass. The clean sparse
checkout contains every registered/build input and all current implementation,
tests, spec, docs, tools and external files; unused historical evidence is
excluded. This is not a fresh full native suite or complete archive checkout.
Repository evidence is `.aide/evidence/2026-10-14-exfat-capture-qualified/`.
Continue actual held source/worker and coherent namespace/tree/content integration;
owner, other-platform/storage, production and full original release remain.


DE-W068 binds the qualified supplied-reader observer to held ordinary image files.
[Its expected contract](../catalog/exfat-file-prototype.json) reuses local_file
parent/path/generation checks and requires actual retained-region replay and
source preservation. The synchronous adapter is not admitted to shared frontends;
contained worker, coherent namespace/tree/content and the full original
platform/storage0.1.0 remain. No native implementation result is claimed here.


DE-W068's available ordinary-file scope reaches local agent review at exact
`c73c6870`: 60 native cases/seven methods, 20 selected regression groups, one
header, normal/fault imports/context/source hashes and 242 tooling tests with
two skips pass. Actual file-symlink creation remains unverified without privilege;
leaf/ancestor junction and hardlink checks pass. The clean sparse checkout contains
every registered/build input and current source/tests/spec/docs/tools/external
files, excluding unused historical evidence. No fresh full native-suite or archive
checkout claim. Repository evidence: `.aide/evidence/2026-10-14-exfat-file-qualified/`.
Contained worker, coherent namespace/tree/content and original full0.1.0 remain.


DE-W069 uses the [existing owned-reader host](../catalog/exfat-worker-prototype.json)
for bounded exFAT frames and parent replay. Typed publication requires actual
owned process/creation/attempt/code/request/capture binding, not passive schema
or hash validity. Cancellation/completion and confirmed exit remain separate.
This expected contract does not claim worker implementation; namespace/tree/content,
other platforms/storage and original full release remain subsequent required work.

The private NTFS [bootstrap capture contract](../catalog/ntfs-capture-prototype.json)
connects supplied-byte decoders through `RegionReader`. Primary/mirror FILE0 and
mapped FILE3 volume information retain exact region hashes, finite budgets and
mandatory rereads. This bounded observation does not replace a damaged primary
with its mirror or prove allocation ownership/current-source authority. Original
attribute-list/payload/namespace/content, held-source/worker/frontend and target
qualification remain required; a bootstrap is not admission of full NTFS support.

The private [NTFS ordinary-file contract](../catalog/ntfs-file-prototype.json)
holds the exact source and ancestor bindings through native bootstrap reads,
supported profile selection and retained replay. No source/effect authority or
atomicity follows from a stable finite observation. Synchronous native waits
remain outside public frontend admission until actual process containment is
qualified. Full attribute-list/namespace/content and original target scope remain.
