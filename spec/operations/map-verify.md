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
  version: 0.1.22-proposed.1
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
  at: '2026-10-07T08:56:07.601435+00:00'
  scope: DE-W024 private captured-map integration contract; file/frontend admission
    still pending
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

## Normative requirements

### DE-REQ-102-01

`table.verify` MUST enforce the preconditions, evidence and recovery limits in this operation contract before admission.

**Verification:** EBR cycle, array multiplication overflow, GPT valid-but-disagreeing copies, truncated image, invalid UTF-16 name, overlapping entries and hot-removal.

## Related specifications

- [DE-030](../storage/identity-and-graph.md)
- [DE-042](../safety/planning.md)
- [DE-043](../safety/journal-and-recovery.md)
- [DE-044](../safety/verification-and-performance.md)
