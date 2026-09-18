---
type: DiskEd Specification
title: DOS, JC-DOS, Carbon and OS/2 portability
description: Constrained native profiles without inventing device or BIOS guarantees.
resource: disked://spec/de-051
tags:
- disked
- platforms
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-051
  profile: disked-spec/1
  version: 0.1.0
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-031
  - DE-012
  requirements:
  - DE-REQ-051-01
  - DE-REQ-051-02
---

# DOS, JC-DOS, Carbon and OS/2 portability

## DOS and historical Windows

Separate DOS version, CPU ISA, executable format, memory model, BIOS services, CHS/LBA access and filesystem capabilities. DOS 3+ does not imply extensions for large LBA or a graphical desktop. Provide an MZ CLI/TUI with bounded buffers; Win16/Win9x have their own GUI and I/O adapters. Use shared explicit-width arithmetic and wire fixtures, not a universal MZ/NE/PE polyglot promise.

A 16-bit implementation may stream observations and consume a bounded plan subset. It need not host the full graph planner, AI tooling or provider catalog. A modern coordinator can prepare a portable plan on removable media or a serial link; the local executor must independently validate identity, supported features and limits. Remote coordination does not remove local safety constraints.

## JC-DOS and Project Carbon

Use the system's published BIOS/PAL/block-service contract. DiskEd must not implement parallel direct IDE/MMIO drivers for each Carbon board. Earlier discussion mentioned CPMX, JCOM and particular 32-bit/512-byte interfaces, but their current definitions have NOT been re-read in this archive session. These are integration leads, not frozen implementation facts. `DE-DEC-006` requires exact upstream commits, ABI headers, format specifications and test vectors before the Carbon provider is enabled.

A future wider storage-services ABI should report addressing width, logical/physical units, transfer limits, identity, media generation, flush and write-protection capabilities. Do not change the BIOS ABI merely because DiskEd prefers a feature; propose an upstream-compatible adapter/version change with its own tests. Existing v1 consumers keep their semantics.

## OS/2

Plan native CLI/TUI and Presentation Manager projection through an OS/2 target adapter. Pin compiler, executable ABI, filesystem interfaces and privilege/device access rules during a dedicated spike. No NT path syntax, Unicode expectation or service model should leak into the portable core. Read-only image support is a valid first port while physical operations remain unavailable.

## Qualification

Run identical format vectors on the host and constrained implementations. Simulator tests establish emulator behavior, not physical controller persistence. Retain source, toolchain provenance and hardware observations separately. Do not ship proprietary SDKs or ROM images without permission. Obsolete environments may require a modern build coordinator; installed product portability is distinct from build-tool portability.

## Normative requirements

### DE-REQ-051-01

DOS/Carbon/OS2 adapters MUST use exact host contracts and explicit memory/addressing limits.

**Verification:** Cross-run canonical binary vectors and boundary cases.

### DE-REQ-051-02

Unverified historical ABI claims MUST remain blocked integration leads until exact source and tests are captured.

**Verification:** Check DE-DEC-006 and provider admission manifest.

## Related specifications

- [DE-031](../storage/address-spaces.md)
- [DE-012](../architecture/languages-and-build.md)
