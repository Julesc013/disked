---
type: DiskEd Specification
title: Address spaces, geometry and data fidelity
description: Checked half-open extents and multiple media semantics.
resource: disked://spec/de-031
tags:
- disked
- storage
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-031
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-030
  requirements:
  - DE-REQ-031-01
  - DE-REQ-031-02
  - DE-REQ-031-03
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Address spaces, geometry and data fidelity

## Block arithmetic

Internally use half-open extents `[start_lba, end_lba)` or `{start_lba, length_lba}` with checked conversion. A zero-length extent is invalid for a partition. A containing device of N blocks permits end == N but no addressed block >= N. Translate inclusive on-disk endpoints explicitly. Calculate bytes as checked block_count × logical_block_bytes; never multiply before checking range. Use u64 semantic ranges with wider intermediates where available and bounded software arithmetic on constrained targets.

Logical sector size, physical sector size, alignment offset, minimum transfer and optimal transfer are independent observations. Unknown physical alignment is not a guessed 4096. Non-power-of-two units are representable unless a particular provider forbids them. Reject overflows, invalid block counts and device-size inconsistencies before any buffer allocation or I/O.

## Non-block semantics

Tape uses sequential records/filemarks, positioning and potentially partitioned media. Optical media has tracks, sessions, write-once and finalization state. Floppy flux represents timing transitions that may not have recognized sectors. Zoned devices restrict writes by zone and write pointer. Objects and distributed volumes have consistency/lease semantics. These domains share identity, capability, plans and evidence, not a universal arbitrary `write(offset)` promise.

## Preservation levels

Distinguish exact byte preservation, interpreted filesystem preservation, and semantic file migration. Unknown ranges may be imaged opaquely without claiming repair. A cross-filesystem copy must account for streams, resource forks, ACLs, ownership, xattrs, sparse extents, hard links, symlinks, snapshots, reflinks, timestamps and name normalization. An information-loss report identifies each nonrepresentable class and its count when discoverable. Containerization can preserve metadata but must be explicit.

Never "clean" unrecognized gaps, boot areas or trailing metadata just because a visible partition table does not allocate them. Acquisition hashes and bad-sector maps must distinguish unreadable content, substituted bytes and verified source bytes.

## Bounded layer traversal

Nested images, compressed containers, filesystems and backing chains require explicit depth, node/count, decompression, memory, output and I/O budgets, with cycle detection and checked translations. Preserve which layer and offset produced each observation. Unknown layers remain representable but cannot inherit a writable interface. [Feature-level capabilities](filesystem-capabilities.md) distinguish each operation and intended consumer.

## Normative requirements

### DE-REQ-031-01

Extent arithmetic MUST be checked and explicitly translate inclusive disk formats to the half-open model.

**Verification:** Boundary tests at zero, device end and u64 overflow.

### DE-REQ-031-02

A provider MUST advertise its address-space semantics; non-block media MUST NOT inherit random-write operations by default.

**Verification:** Offer tape/flux/zoned fixtures to a block-only provider and verify refusal.

### DE-REQ-031-03

Migration MUST declare nonrepresentable metadata and unreadable content rather than silently report lossless success.

**Verification:** Cross-filesystem metadata-loss fixture with a digest-bound acknowledgement.

## Related specifications

- [DE-030](identity-and-graph.md)
