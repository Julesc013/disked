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
  version: 0.1.2-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-031
  - DE-012
  requirements:
  - DE-REQ-051-01
  - DE-REQ-051-02
updated:
  by: codex
  at: '2026-10-04T07:27:09.204646+00:00'
  scope: CLI syntax refinement; proposed, no native parser or acceptance claim
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
- id: review-08a8246-2026-10-04
  resource: ../references/sources.json#review-08a8246-2026-10-04
- id: cli-refinement-2026-10-04
  resource: ../references/sources.json#cli-refinement-2026-10-04
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

## Early research without support claims

DOS 1.x and 2.x, Windows 1.x and 2.x, OS/2 1.x text and PM-capable variants, and OS/2 2.x text/PM are explicit unqualified research profiles. DOS real mode and an extender are separate candidates; the inherited broad `dos.386.lba` and `os2.x86.pm` rows remain research leads rather than exact artifact contracts. An extender identity and its executable wrapper remain unresolved until pinned; neither a slash nor the word selected is an ABI qualification.

DE-W018 brings harmless loader, checked-arithmetic, encoding and text probes into M1. The later DE-W071 image-reader work remains separate. Record exact release, memory/CPU floor, APIs, file/directory assumptions, terminal behavior and toolchain limits. Do not change DOS 3+ to DOS 1+ by editing a label. Missing tools/emulators yield a documented blocker, never a support claim or a mandatory delay to the modern slice.

## Command and terminal consistency

Share command meanings and available typed outcomes across profiles; do not infer identical storage authority or UI richness. Qualify local DOS text display/keyboard/mouse independently from serial/VT channels. Primitive profiles need deliberate linear or cell-based interfaces and exact encoding/memory bounds, not a universal executable trick. DE-W018 records harmless terminal/loader probes; DE-026 owns capability detection and fallback.

## Portable command interpretation

Qualified parsers share DE-021 command identities, option/value placement, literal boundaries and alias meanings independently of terminal features. A constrained build can explain an unavailable operation or refuse an over-budget input; it cannot silently remap its alias. Raw DOS command-tail tokenization and code-page limits are distinct from the common token-vector grammar. DE-W018/071 must retain actual target evidence before claiming identical interpretation across DOS, OS/2 and Windows. No modern runtime or completion engine becomes a DOS prerequisite merely because the specification fixtures are validated with Python.

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
