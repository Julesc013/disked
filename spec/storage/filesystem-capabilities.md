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
  version: 0.1.7-proposed.1
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
  at: '2026-10-12T18:58:11.024491+00:00'
  scope: DE-W029 source-bound auxiliary FAT evidence; namespace, host, owner and release gates remain open
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
