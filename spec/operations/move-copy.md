---
type: DiskEd Specification
title: Copy or move an extent-backed volume
description: Independent operation contract for partition.move.plan.
resource: disked://spec/de-108
tags:
- disked
- operations
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-108
  profile: disked-spec/1
  version: 0.1.0
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-030
  - DE-042
  - DE-043
  - DE-044
  requirements:
  - DE-REQ-108-01
---

# Copy or move an extent-backed volume

## Identity and availability

Semantic ID: `partition.move.plan`. Operation specification: `DE-OP-008`. Earliest phase: **M7**. Initial target scope: image/clone-first then separately qualified nonoverlap and overlap cases. Status: specified, not implemented or qualified. No availability is implied by the presence of this document.

## Required inputs and preconditions

Offline/quiescent known stack, exact geometry, boot/encryption dependencies, overlap-aware algorithm, independent recovery store and verified backup requirements. Source and destination aliases must be detected. A filesystem-specific move may have different metadata needs from opaque byte copying.

## Planned procedure

Choose direction and bounded chunk strategy with a proven overlap invariant; preserve any data needed for the declared recovery class; checkpoint durably before destructive overwrite; verify destination; commit map and dependent metadata only at defined checkpoints. Unknown start-dependent metadata prevents an opaque move from being called bootable.

## Postconditions and evidence

Destination content/metadata verified, source cleanup only if explicitly authorized, map and boot dependencies consistent. User-facing success does not occur before required post-boot validation when applicable.

## Interruption, cancellation and recovery

Overlapping copies can destroy original source bytes; a small checkpoint log usually provides resume, not rollback. Stop only at safe points. Recovery after uncertain chunk writes rechecks bounded content before proceeding.

## Required adversarial cases

Overlap both directions, power loss at every chunk, media error, changed device, corrupt checkpoint, boot reference mismatch, insufficient independent recovery storage and canceled irreversible stage.

## Normative requirements

### DE-REQ-108-01

`partition.move.plan` MUST enforce the preconditions, evidence and recovery limits in this operation contract before admission.

**Verification:** Overlap both directions, power loss at every chunk, media error, changed device, corrupt checkpoint, boot reference mismatch, insufficient independent recovery storage and canceled irreversible stage.

## Related specifications

- [DE-030](../storage/identity-and-graph.md)
- [DE-042](../safety/planning.md)
- [DE-043](../safety/journal-and-recovery.md)
- [DE-044](../safety/verification-and-performance.md)
