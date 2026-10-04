---
type: DiskEd Specification
title: Read-only image acquisition
description: Independent operation contract for image.acquire.
resource: disked://spec/de-103
tags:
- disked
- operations
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-103
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-030
  - DE-042
  - DE-043
  - DE-044
  requirements:
  - DE-REQ-103-01
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Read-only image acquisition

## Identity and availability

Semantic ID: `image.acquire`. Operation specification: `DE-OP-003`. Earliest phase: **M4**. Initial target scope: explicit source and separately owned destination. Status: specified, not implemented or qualified. No availability is implied by the presence of this document.

## Required inputs and preconditions

Confirm source identity, destination capacity, destination is not a source extent/alias, overwrite policy, sparse policy and evidence root. For failing media choose a read-mostly strategy and request operator approval before aggressive rereads. Destination paths may be symlinks/reparse aliases and need safe resolution.

## Planned procedure

Create destination with no-clobber semantics; record geometry/identity; stream bounded regions with a persistent acquisition map. Distinguish successful reads, unreadable ranges, retries and substituted bytes. Checkpoint source/destination identities and verified region hashes. A filesystem-aware acquisition is a different provider with documented metadata coverage.

## Postconditions and evidence

Image, acquisition map and evidence agree on source size, unreadable ranges and verified bytes. A full-image digest is labeled according to what was actually read. Verify destination independently where policy permits; no restore readiness claim without the required validation.

## Interruption, cancellation and recovery

Resume only with matching identities/map/destination state. An interrupted map record is uncertain and causes bounded re-observation. Do not overwrite original source. Stop/pause may be safe between recorded chunks but failing-media policy takes precedence over ordinary throughput.

## Required adversarial cases

Destination equals source through alias, full destination, thin-provisioning exhaustion, disconnected device, corrupt map, resumed different disk, read substitution and destination file preexistence.

## Consistency and observational effects

[DE-036](../storage/acquisition-consistency.md) governs source consistency and capture epoch. Bind participating volumes/writers, snapshot scope/lifetime, source-read and destination-write permissions, host side effects and resume limits. Report live-uncoordinated/unknown rather than coherent when evidence is absent. Hash coverage, filesystem validity, restore readiness and bootability are independent results.

## Normative requirements

### DE-REQ-103-01

`image.acquire` MUST enforce the preconditions, evidence and recovery limits in this operation contract before admission.

**Verification:** Destination equals source through alias, full destination, thin-provisioning exhaustion, disconnected device, corrupt map, resumed different disk, read substitution and destination file preexistence.

## Related specifications

- [DE-030](../storage/identity-and-graph.md)
- [DE-042](../safety/planning.md)
- [DE-043](../safety/journal-and-recovery.md)
- [DE-044](../safety/verification-and-performance.md)
