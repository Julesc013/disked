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
  version: 0.1.18-proposed.1
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
  at: '2026-10-06T18:59:16.591767+00:00'
  scope: DE-W020 internal C90 arithmetic, bounded views and named extents; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
- id: review-08a8246-2026-10-04
  resource: ../references/sources.json#review-08a8246-2026-10-04
---

# Address spaces, geometry and data fidelity

## Block arithmetic

Internally use half-open extents `[start_lba, end_lba)` or `{start_lba, length_lba}` with checked conversion. A zero-length extent is invalid for a partition. A containing device of N blocks permits end == N but no addressed block >= N. Translate inclusive on-disk endpoints explicitly. Calculate bytes as checked block_count × logical_block_bytes; never multiply before checking range. Use u64 semantic ranges with wider intermediates where available and bounded software arithmetic on constrained targets.

Logical sector size, physical sector size, alignment offset, minimum transfer and optimal transfer are independent observations. Unknown physical alignment is not a guessed 4096. Non-power-of-two units are representable unless a particular provider forbids them. Reject overflows, invalid block counts and device-size inconsistencies before any buffer allocation or I/O.

## DE-W020 portable execution contract

`source/portable/primitives/` owns the internal C90 checked-value, byte-view and
extent implementation used by subsequent format readers. The earlier DE-W018
probe exercises this same implementation; there is no parallel arithmetic copy.
These source-level C interfaces are private, not a frozen SDK or on-disk ABI.
They allocate nothing, include no OS headers, and perform no I/O. All fallible
calls leave caller outputs unchanged on refusal. Input objects must be valid for
their stated lifetime and byte length; null is allowed only for an empty byte view.

An exact u64 uses four 16-bit limbs and a checked 32-bit intermediate. Addition,
subtraction, multiplication and division/remainder refuse overflow, underflow or
zero divisors. Results may alias an arithmetic input; quotient and remainder
outputs must be distinct. Size conversion refuses values above the actual
target's `size_t` ceiling. Decimal representation remains canonical ASCII;
no pointer or struct layout is a wire representation.

A byte view borrows one caller-owned array. Slicing validates `offset <= size`
and `length <= size - offset` before pointer arithmetic, permits an empty slice
at the end, and can accept exact-u64 offsets/lengths only after checked native
size conversion. Unsigned endian reads/writes support exactly 1, 2, 4 or 8 bytes
in explicit little or big endian order, including unaligned offsets. Truncated
access or a value too wide for the requested field is refused before any write.
Mutable buffers and immutable views remain distinct C types.

A block-space object borrows a nonempty name of at most 128 bytes (no embedded
NUL), an exact block count and a logical unit of 1 through 1048576 bytes. Names,
geometry and the object itself stay immutable while its extents are used. Extent
operations require the same space object; equal display names alone do not merge
spaces or establish storage identity. A bytes-to-space constructor requires an
exact whole number of declared units. Geometry does not invent physical alignment.

Partition extents are nonempty, half-open, and bounded by the containing block
count; `end == device_blocks` is valid. Inclusive endpoints are converted with
checked `last + 1`; an unrepresentable end is refused. Overlap excludes adjacency.
Byte projection checks both endpoint products independently, so no rounded or
wrapped offset can escape to an I/O adapter. Pure block geometry may be retained
when the whole device's byte size is not representable; an overflowing byte
projection remains unavailable. None of these values grants provider authority.
The extent JSON review contract additionally requires successful byte projection;
a purely block-coordinate internal value cannot be emitted as that schema until
it passes the byte check.

Acceptance uses an independent integer oracle, zero/device-end/u64 boundary and
non-power-of-two-unit vectors, unchanged-output sentinels, unaligned/truncated
buffer tests and C/C++ linkage. Reuse the vectors across available compilers,
retaining actual widths and unrun historical targets separately. The initial
native fake executable gains no real-storage command from this internal module.

## Non-block semantics

Tape uses sequential records/filemarks, positioning and potentially partitioned media. Optical media has tracks, sessions, write-once and finalization state. Floppy flux represents timing transitions that may not have recognized sectors. Zoned devices restrict writes by zone and write pointer. Objects and distributed volumes have consistency/lease semantics. These domains share identity, capability, plans and evidence, not a universal arbitrary `write(offset)` promise.

## Preservation levels

Distinguish exact byte preservation, interpreted filesystem preservation, and semantic file migration. Unknown ranges may be imaged opaquely without claiming repair. A cross-filesystem copy must account for streams, resource forks, ACLs, ownership, xattrs, sparse extents, hard links, symlinks, snapshots, reflinks, timestamps and name normalization. An information-loss report identifies each nonrepresentable class and its count when discoverable. Containerization can preserve metadata but must be explicit.

Never "clean" unrecognized gaps, boot areas or trailing metadata just because a visible partition table does not allocate them. Acquisition hashes and bad-sector maps must distinguish unreadable content, substituted bytes and verified source bytes.

## Bounded layer traversal

Nested images, compressed containers, filesystems and backing chains require explicit depth, node/count, decompression, memory, output and I/O budgets, with cycle detection and checked translations. Preserve which layer and offset produced each observation. Unknown layers remain representable but cannot inherit a writable interface. [Feature-level capabilities](filesystem-capabilities.md) distinguish each operation and intended consumer.

## Lossless names before migration

Preserve original name/identifier bytes or code units and their encoding, separate lookup keys and escaped display text. Record normalization, case-folding, substitutions and representability loss explicitly. Display/search normalization cannot overwrite the recovery source. Cross-filesystem migration needs fixtures for distinct original names that collapse to one destination lookup key; this is an operation-specific admission gate, not a promise of universal name portability.

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
