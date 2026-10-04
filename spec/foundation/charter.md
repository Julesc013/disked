---
type: DiskEd Specification
title: Product charter and scope
description: Windows-first storage administration with one target-native entrypoint and evidence-qualified operations.
resource: disked://spec/de-001
tags:
- disked
- foundation
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-001
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R1
  depends_on: []
  requirements:
  - DE-REQ-001-01
  - DE-REQ-001-02
  - DE-REQ-001-03
  - DE-REQ-001-04
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Product charter and scope

## Mission

DiskEd is the native storage inspection, planning, imaging, administration, repair and recovery tool for Windows NT first, with DOS, JC-DOS, Project Carbon, Win9x, OS/2 and other underserved systems as deliberate architectural targets. GParted is a parity reference and optional recovery provider, not the Windows implementation foundation. The user should ordinarily invoke one `disked` tool rather than remember which external utility implements a task.

The product must be useful as a copy-and-run workshop utility before it can modify physical disks. Its first complete journey is: identify a device or image, explain topology and uncertainty, validate partition metadata, acquire an image, and export reproducible evidence. A read-only product is useful but must not be advertised as a completed Disk Management replacement.

## Product commitments

One semantic operation model serves CLI, JSON/NDJSON, TUI and a target-native OEM+ GUI. A build selects one GUI adapter; it does not load every toolkit. `disked` and `DiskEd` identify the same product, not case-distinguished files. One-file, zero-extraction native Windows composition is the reference delivery objective. A process count is not a file count: the same verified image can launch a separate broker process. Exceptions for dependencies, OS app bundles, licensing or secure provider isolation must be declared in the composition, not concealed.

Windows XP SP3 x86, Windows 7 SP1 x64, Windows 10 x64 and Windows 11 x64 are the initial qualification lanes. ARM64 follows the native NT core. Historical lanes share contracts and selected portable algorithms; they need not run the complete modern planner locally. No target is supported merely because it appears in the roadmap.

## Boundary of the promise

Universal means extensible representation and honest capability discovery. It does not mean all filesystems can be shrunk, damaged media can always be restored, locked operating systems can be bypassed, or unknown proprietary formats can be rewritten. An unavailable operation remains recognizable and explainable. No source of encryption keys, undocumented hardware behavior, or recovery information is assumed.

Microsoft, Sysinternals and OEM adoption are possible integration destinations, not endorsements, certifications or release dependencies. The project can offer a clean Windows-native core, community provider packs and a recovery composition without claiming Microsoft requires this particular architecture.

## Initial exclusions

No production physical writes, kernel driver, arbitrary privileged plugin loading, automatic boot modification, online system-volume movement, AI-generated execution authorization, or customer media in development. Tape, optical, flux, object and distributed storage remain explicit future domains rather than being erased from the model.

## Useful under partial failure

Where the host permits execution, retain useful inspection, image-file work, saved reports, simulation and explanations at the authority actually available. Denied, absent, unsupported, stale and uncertain are different outcomes. Neither an expert view nor installation scope bypasses host policy, encryption, ownership or missing recovery resources. The essential interface precedes discovery; see [execution roles](../architecture/execution-topology.md).

The product direction spans DOS 1.x/2.x onward, early Windows and OS/2, with explicit research profiles. Release scope is a selected, qualified subset. Compare GParted/Disk Management by named tasks, features, preservation, recovery and measured equivalent work; no present superiority or universal-success claim is made.

## Normative requirements

### DE-REQ-001-01

The executable basename MUST be `disked`; a native-capable release profile MUST include CLI, machine mode, TUI and its declared GUI in one product entrypoint.

**Verification:** Inspect composition manifest and execute all declared frontend smoke tests.

### DE-REQ-001-02

Every advertised operation MUST bind support to target, provider, object state and evidence; planned capability MUST NOT be presented as implemented.

**Verification:** Compare generated support page with evidence records; inject an unsupported target.

### DE-REQ-001-03

Initial development MUST use fake targets and disposable images; production physical-write admission is outside this baseline.

**Verification:** Inspect work grants and exercise a denied raw-device request.

### DE-REQ-001-04

DiskEd MUST preserve available permitted functions and explicit refusal/uncertainty reasons when optional capabilities fail; it MUST NOT represent denied or unknown observations as empty success.

**Verification:** Combine healthy, denied, absent and stalled fake targets and compare the retained observations and reasons across all frontends.
