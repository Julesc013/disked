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
  version: 0.1.0
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
---

# Partition-map parsing and validation

## MBR and EBR

Read the minimum required blocks without assuming a byte-packed host struct matches the disk format. Decode little-endian integers explicitly. Validate signature, entry extents, integer bounds, overlaps, protective entries and CHS/LBA inconsistencies. Treat bootstrap code and unused bytes as opaque preserved material. Recognize that a nonstandard layout may be diagnostically meaningful without being safe to rewrite.

Walk EBR chains with a visited-LBA set and a profile limit. Differentiate addresses relative to the current EBR from links relative to the extended container base. Detect cycles, repeated nodes, out-of-container ranges, truncated media and overlapping logical partitions. Do not automatically normalize historical alignments. Tiny-memory profiles may use bounded cycle detection but must retain reliable limits and diagnostics.

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
