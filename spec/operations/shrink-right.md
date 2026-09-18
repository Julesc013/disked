---
type: DiskEd Specification
title: Shrink a filesystem and its container
description: Independent operation contract for filesystem.shrink-right.plan.
resource: disked://spec/de-107
tags:
- disked
- operations
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-107
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
  - DE-REQ-107-01
---

# Shrink a filesystem and its container

## Identity and availability

Semantic ID: `filesystem.shrink-right.plan`. Operation specification: `DE-OP-007`. Earliest phase: **M5/M6**. Initial target scope: provider-qualified NTFS or other supported filesystem, never generic XP support. Status: specified, not implemented or qualified. No availability is implied by the presence of this document.

## Required inputs and preconditions

Required target size is above the verified minimum; trailing allocations are handled by a qualified filesystem workflow; no unsupported mounted/system/encryption state. Availability is OS- and provider-specific. Raw partition boundaries alone cannot determine a safe filesystem minimum.

## Planned procedure

Prepare filesystem shrink; relocate allocations through the admitted provider; commit and independently verify the smaller filesystem; only then reduce the containing boundary. Record provider-rounded size and actual postconditions. Refuse if any mandatory allocation/consistency property is unknown.

## Postconditions and evidence

No filesystem allocation extends beyond its container, required checks pass and original unrelated extents are intact. Evidence distinguishes the requested size from actual safe aligned size.

## Interruption, cancellation and recovery

Failure before boundary reduction can leave a smaller filesystem in a larger partition. Recovery must use current filesystem state. Never shorten the partition after an uncertain shrink result.

## Required adversarial cases

Immovable metadata, unsupported filesystem, XP without qualifying provider, hibernation, failed relocation, stale minimum size and power loss before filesystem commit.

## Normative requirements

### DE-REQ-107-01

`filesystem.shrink-right.plan` MUST enforce the preconditions, evidence and recovery limits in this operation contract before admission.

**Verification:** Immovable metadata, unsupported filesystem, XP without qualifying provider, hibernation, failed relocation, stale minimum size and power loss before filesystem commit.

## Related specifications

- [DE-030](../storage/identity-and-graph.md)
- [DE-042](../safety/planning.md)
- [DE-043](../safety/journal-and-recovery.md)
- [DE-044](../safety/verification-and-performance.md)
