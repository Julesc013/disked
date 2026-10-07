---
type: DiskEd Specification
title: Read-only partition-map verification
description: Independent operation contract for table.verify.
resource: disked://spec/de-102
tags:
- disked
- operations
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-102
  profile: disked-spec/1
  version: 0.1.23-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-030
  - DE-042
  - DE-043
  - DE-044
  requirements:
  - DE-REQ-102-01
updated:
  by: codex
  at: '2026-10-07T21:27:06.800037+00:00'
  scope: DE-W024 bounded ordinary-file metadata capture contract; private prototype,
    command/frontend admission pending
---

# Read-only partition-map verification

## Identity and availability

Semantic ID: `table.verify`. Operation specification: `DE-OP-002`. Earliest phase: **M2**. Initial target scope: raw disposable images, later observed physical media. Status: specified, not implemented or qualified. No availability is implied by the presence of this document.

## Required inputs and preconditions

Explicit read-only source and device geometry. Resource limits bound all entry counts and walks. Source change during reading invalidates a coherent-state claim. A forensic source may require hardware write-blocker procedures.

## Planned procedure

Read independent candidate map copies; validate signature, checksums and extents; report competing interpretations. Run independent decoder or external oracle only if its read-only behavior is admitted. Produce proposed repair candidates as data, never automatic writes.

## Postconditions and evidence

Diagnostics refer to exact source regions and provider versions. The report separates structural validity, consistency, inferred intent and unsupported metadata. No "all healthy" conclusion follows solely from CRC validity.

## Interruption, cancellation and recovery

Interrupted verification returns partial coverage. Preserve useful diagnostics but never promote incomplete coverage into a valid-map certificate.

## Required adversarial cases

EBR cycle, array multiplication overflow, GPT valid-but-disagreeing copies, truncated image, invalid UTF-16 name, overlapping entries and hot-removal.

## DE-W024 private captured-map observation slice

The first integration function consumes an immutable byte prefix and explicit
decimal-u64 block count plus logical block size (512 or 4096). It performs no I/O,
allocation outside its bounded workload, provider loading or repair. Its private
JSON observation is a review representation, not a frozen public storage API.
An input prefix is at most 16 MiB and cannot exceed the declared byte capacity;
capacity multiplication must fit u64. Zero captured bytes and zero declared
blocks are legitimate incomplete/empty observations. Invalid geometry and an
exhausted input budget are typed refusal conditions, not corrupt-map findings.
Zero declared blocks have no LBA zero: retain reader bounds status without
inventing an empty parsed table. Missing bytes within a declared block are instead
reported as truncated/unavailable according to the reader contract.

Report exact declared/captured byte counts, geometry, full-prefix SHA-256 and
whether all declared bytes were supplied. These bind the bytes interpreted;
they do not establish a stable source identity, acquisition epoch or atomic
point-in-time capture. Source consistency remains `unknown` until a later
capture adapter supplies separately qualified evidence. The function retains no
borrowed input or parser-workspace pointers after returning.

Observe the MBR at LBA zero, walk every structurally eligible extended root,
and independently observe GPT at LBA one and the declared final LBA. Do not choose
one format based on a signature or suppress a backup because a primary failed.
Missing bytes remain missing; no zero substitution is permitted. EBR visits are
bounded to 128 per root; GPT limits are 1024 entries, 4096 bytes per entry and
1 MiB per array. Preserve reader status, issue masks, exact requested regions,
coverage/completeness and both candidate results. Issue-bit meanings remain owned
by the private C90 reader contracts; an API refusal and a media finding are distinct.

The report includes all four MBR entries, up to eight EBR nodes per root and up
to eight active GPT entries per candidate. It reports observed/active counts and
explicit omitted counts; omitted detail is not omitted validation. Walk and array
summaries aggregate findings over the entire bounded traversal/array. Original
16-byte MBR/EBR records and 72-byte GPT name fields are hex; valid UTF-16 names
also have derived UTF-8 text, without normalization. Invalid names retain bytes
and a decoding status. Coordinates/attributes are decimal strings; inclusive GPT
last blocks remain distinct from derived exclusive ends. No selected copy, repair
intent, healthy-volume certificate or source-consistency assertion is emitted.

The owned report must fit 48 KiB with finite JSON depth/node/string budgets,
leaving room for a later 64 KiB command envelope. Resource refusal publishes no
partial success. Native tests compare this integration against independently
declared corpus findings, verify retained bytes/geometry and exercise prefix
truncation, unsupported units, capacity overflow, input/report bounds, EBR cycles,
GPT disagreement and lossless name handling. This slice does not yet admit
`image.inspect` or `table.verify`; file capture and real frontend parity remain
DE-W024 work, with physical devices, mounting and elevation outside the grant.

## DE-W024 ordinary-file capture slice

The initial private Windows capture adapter accepts an explicitly named ordinary
local raw file, with a selected 512- or 4096-byte logical block unit. It reads
metadata regions through the same map integration rather than loading an entire
image. File length is retained exactly; the derived block count rounds a partial
final block upwards and records that fact. This is interpretation geometry, not
an assertion about physical sector geometry. A large file is not refused merely
because its total length exceeds the earlier 16 MiB prefix-test budget.

For this prototype profile, resolve an ordinary relative or drive-absolute path
once, then require a fixed local drive and a canonical path of at most 240 UTF-16
code units. Reject UNC/device namespaces, drive-relative paths, alternate streams,
reserved DOS device components, trailing spaces/dots, wildcards and control
characters before opening the selected source. Pin and inspect each ancestor and
the final file without following reparse points; all handles are non-inheritable
and deny write/delete sharing. Refuse directory, reparse and multiple-hardlink
sources. Bind each opened handle's normalized path to the resolved selection;
short-name/drive aliases that do not preserve that binding are refused in this
profile. Refuse offline/recall attributes before reading. These are explicit
prototype restrictions, not permanent filesystem-name or provider-support claims.
No volume/physical-device open, mounting, elevation,
network discovery, source write or destination creation is part of capture.
Ordinary reads can still cause host filesystem/cache activity.

Bind the opened source using its volume and 128-bit file identity, exact byte
length and before/after metadata observations. Record a capture epoch, wall-clock
start/end FILETIME observations and separate elapsed monotonic milliseconds. The
private epoch binds this attempt; it is not a grant or durable operation identity.
Retain owned immutable buffers
through parsing and comparison; callbacks may supply only actual available bytes
from the checked requested extent. At most 517 metadata requests and 5 MiB of
requested bytes are permitted in one map observation. An exact duplicate region
can reuse its captured buffer; an overlapping distinct region must be compared
against the earlier capture. Missing bytes are never filled with zeros. A finite
second pass rereads every unique captured region and compares identity/length/
write-change metadata. I/O errors, short reads and observed changes remain
separate from partition-format findings and invalidate a coherent-source claim.

The private receipt retains all region coordinates, actual byte counts, per-region
digests and errors in an owned manifest. Its digest, total/unique request counts,
byte coverage and a bounded detail projection accompany the map report. Unique
requested bytes and requested bytes including exact-region reuse are distinct.
There is
no whole-file hash or whole-file verification claim. Source consistency is
`live-uncoordinated`: sequential reads and equal rereads are not an atomic snapshot,
and local sharing restrictions are not general storage fencing. Observed stability
and metadata coverage are separate fields. Empty files are legitimate empty
captures; a partial final block or incomplete required metadata remains explicit.

Native tests use repository-generated ordinary disposable files and independent
reader findings. They exercise large sparse files, partial final blocks, bounded
coverage, read errors/changes, path and sharing refusal, hardlinks/reparse ancestors,
retained source bytes and result ownership. Fault controls exist only in separately
compiled test probes. This slice remains private until shared command and actual
CLI/TUI/GUI parity tests admit it; product image commands remain unavailable.

Windows API references for this slice are the official [CreateFileW contract](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
and [GetFileInformationByHandleEx contract](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex).

## Normative requirements

### DE-REQ-102-01

`table.verify` MUST enforce the preconditions, evidence and recovery limits in this operation contract before admission.

**Verification:** EBR cycle, array multiplication overflow, GPT valid-but-disagreeing copies, truncated image, invalid UTF-16 name, overlapping entries and hot-removal.

## Related specifications

- [DE-030](../storage/identity-and-graph.md)
- [DE-042](../safety/planning.md)
- [DE-043](../safety/journal-and-recovery.md)
- [DE-044](../safety/verification-and-performance.md)
