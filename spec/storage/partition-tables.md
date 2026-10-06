---
type: DiskEd Specification
title: Partition-map parsing and validation
description: Independent bounded readers for MBR, EBR and GPT before any writer.
resource: disked://spec/de-032
tags:
- disked
- storage
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-032
  profile: disked-spec/1
  version: 0.1.19
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-030
  - DE-031
  requirements:
  - DE-REQ-032-01
  - DE-REQ-032-02
  - DE-REQ-032-03
sources:
- id: uefi-210-mbr
  resource: references/sources.json#uefi-210-mbr
- id: linux-612-ebr
  resource: references/sources.json#linux-612-ebr
---

# Partition-map parsing and validation

## MBR and EBR

Read the minimum required blocks without assuming a byte-packed host struct matches the disk format. Decode little-endian integers explicitly. Validate signature, entry extents, integer bounds, overlaps, protective entries and CHS/LBA inconsistencies. Treat bootstrap code and unused bytes as opaque preserved material. Recognize that a nonstandard layout may be diagnostically meaningful without being safe to rewrite.

Walk EBR chains with a visited-LBA set and a profile limit. Differentiate addresses relative to the current EBR from links relative to the extended container base. Detect cycles, repeated nodes, out-of-container ranges, truncated media and overlapping logical partitions. Do not automatically normalize historical alignments. Tiny-memory profiles may use bounded cycle detection but must retain reliable limits and diagnostics.

## DE-W021 initial reader contract

The first reader is an internal C90 library, not an admitted storage provider or
a stable SDK. Its caller supplies immutable bytes and a named DE-031 block space;
the library performs no I/O, allocation, mounting, writes or callbacks. The
selected logical block size is 512 through 1048576 bytes. A complete table block
must have exactly that size; a shorter supplied block is a retained truncation
observation. Oversized views and invalid caller parameters are API errors and
leave the output/state unchanged. Borrowed bytes and space must remain alive and
immutable for the entire observation lifetime. The caller's writable EBR workspace
is exclusively reserved for the parser during a walk and retained for subsequent
inspection; the caller must not move or overwrite it while observations use it.
Output objects and workspace must not overlap input byte storage or the immutable
space/geometry descriptors. These are private C caller preconditions, not validation
of hostile pointers supplied by an external process.

Byte layout follows UEFI 2.10 sections 5.2.1 and 5.2.3 (four 16-byte entries at 446
with little-endian start/count fields, signature at 510). Preserve the entire
supplied block, including bootstrap, unused entries and bytes after 512, as a
borrowed opaque view. Do not execute or normalize it. Linux v6.12's original
partition reader documents the two EBR address bases and historical variations;
it is a comparison reference, not incorporated code or a claim that all those
variations are supported. Exact references are in `references/sources.json`.

Decode all four primary records. Type and count both nonzero select an active
entry. Preserve and flag nonzero inactive records, unusual boot flags, invalid
extents and primary overlaps. Types 05, 0F and 85 identify extended containers;
EE identifies a protective observation, never proof of valid GPT. Check protective
start/count, boot flag, starting CHS, other records and specified reserved bytes;
flag hybrid/multiple protective layouts. Their content remains inspectable.
No signature means no interpreted entries, even when bytes resemble a table.

CHS never determines a read address. Optional caller-supplied heads (1..256) and
sectors/track (1..63) allow comparison of representable CHS against absolute LBA
start and inclusive end. Both geometry fields zero mean unknown. All-zero or
saturated FE-FF-FF / FF-FF-FF CHS is preserved as unverified. Missing geometry is
also unverified; no geometry is guessed and no CHS discrepancy is repaired.

An EBR walk explicitly selects one valid primary extended container. The first
request is its start. The common two-entry profile interprets slot zero's data
offset relative to the current EBR and slot one's extended link relative to the
original container. Empty data with a next link is permitted. Additional active
slots, misplaced data/link types, or nonzero inactive data/link records terminate
with an unsupported-layout observation, preserving all bytes. Historical DR-DOS,
OS/2, boot-manager and alternate-base layouts require separate profiles/evidence.

Every requested EBR and resolved data/link extent must fit the device and the
selected container. Link count is retained and checked as a descriptor extent;
it does not replace the original container bound. Data extents are compared with
earlier logical extents and every visited EBR block, including metadata discovered
later. Adjacent data extents do not overlap. Containment of a logical partition
inside its extended container is expected, not a primary-overlap defect.

The caller chooses an EBR budget from 1 through 128 and supplies at least that
many node slots. A retained visited-LBA set rejects a repeated next address before
another request; a nonempty continuation at the limit reports budget exhaustion.
No recursion, implicit retries or resettable per-link budget is permitted. Feeding
an unexpected LBA is a caller error and leaves state unchanged. Short blocks, bad
signatures, unsupported layouts, invalid links and reported source unavailability
terminate with partial coverage. Valid terminal links establish traversal
completion only; diagnostics, unverified CHS and unchecked filesystem/GPT content
remain separate. There is no disk-wide validity certificate or writer admission.

The acceptance corpus must independently specify device-end and u32 endpoint
widening, both EBR bases, cycles/repeated nodes, limits, malformed/short blocks,
logical/metadata/primary overlaps, non-512 units, protective/hybrid records, CHS
comparison and exact opaque-byte retention. Generated valid layouts and bounded
malformed mutations supplement those cases. Native memory protection and C/C++
linkage checks exercise the actual C reader. Product `table.verify` remains
unavailable until its source-consistency and provider contracts are implemented.

## GPT

Validate primary and backup independently: signature, supported revision, header size, reserved fields, header CRC, current/alternate LBA, usable bounds, entry count/size, entry-array size and CRC, array location and partition extents. Guard every multiplication before allocation/read. GPT uses CRC-32 as specified by its format; do not substitute the journal's checksum without an explicit format definition. Decode GUID byte order and UTF-16 names correctly, preserving unrecognized attributes.

A valid CRC is not proof that content is correct or intended. When two structurally valid copies disagree, retain both candidates and refuse automatic repair until an explicit selection is supported. Do not always prefer primary or backup by location. Repair is a reviewed operation with original metadata capture and an independent verifier.

## Writer boundary

Table-only writers initially operate against disposable images. A partition boundary change does not resize a filesystem. Preserve untouched table fields, boot code, GUIDs and opaque sectors unless an intent explicitly authorizes them. No global atomicity is promised across redundant GPT structures; journal ordering and interrupted-state recovery require provider-specific design. Historical APM, BSD labels, VTOC, RDB and vendor maps are future providers with the same observation law.

Implementation MUST cite an exact primary format specification revision in its provider record before real writes. This document is a safety/behavior contract, not a substitute for byte-level upstream format references.

## Normative requirements

### DE-REQ-032-01

MBR/EBR/GPT readers MUST enforce range, multiplication, cycle and resource bounds before reads or allocation.

**Verification:** Malformed corpus plus fuzzing and differential parsers.

### DE-REQ-032-02

Disagreeing valid GPT copies MUST produce competing observations and require explicit repair authority.

**Verification:** Create valid but conflicting primary/backup fixtures.

### DE-REQ-032-03

Table updates MUST preserve unrelated opaque bytes and MUST NOT imply filesystem resizing.

**Verification:** Byte-diff a fixture around modified entries and compare unchanged regions.

## Related specifications

- [DE-030](identity-and-graph.md)
- [DE-031](address-spaces.md)
