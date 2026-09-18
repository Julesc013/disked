---
type: DiskEd Specification
title: Grow a partition and filesystem to the right
description: Independent operation contract for filesystem.grow-right.plan.
resource: disked://spec/de-106
tags:
- disked
- operations
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-106
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
  - DE-REQ-106-01
---

# Grow a partition and filesystem to the right

## Identity and availability

Semantic ID: `filesystem.grow-right.plan`. Operation specification: `DE-OP-006`. Earliest phase: **M5/M6**. Initial target scope: qualified filesystem in a supported simple stack. Status: specified, not implemented or qualified. No availability is implied by the presence of this document.

## Required inputs and preconditions

Exact unallocated adjacent capacity, supported filesystem grow provider, underlying container limits, consistent identity and mount/lock state. Encryption, thin volumes and arrays need their own providers. No neighboring extent may be consumed implicitly.

## Planned procedure

Expand the appropriate containing extent before filesystem growth according to the stack; verify the intermediate boundary; invoke the exact grow provider; flush and recapture. If the filesystem grow fails, report the larger container and old filesystem as an explicit partial state, not automatic failure rollback.

## Postconditions and evidence

Filesystem and container lengths match the intended result within provider rounding. Data/metadata checks and geometry verification pass. Evidence records all intermediate revisions and any unused trailing capacity.

## Interruption, cancellation and recovery

Stopping after container growth may leave a safe but incomplete state; prove that per provider. A generic shrink-back rollback is not assumed. Resume/recovery plans use the observed state.

## Required adversarial cases

Nonadjacent free space, capacity race, filesystem maximum, encryption layer, grow-provider success with unchanged filesystem and failure after boundary growth.

## Normative requirements

### DE-REQ-106-01

`filesystem.grow-right.plan` MUST enforce the preconditions, evidence and recovery limits in this operation contract before admission.

**Verification:** Nonadjacent free space, capacity race, filesystem maximum, encryption layer, grow-provider success with unchanged filesystem and failure after boundary growth.

## Related specifications

- [DE-030](../storage/identity-and-graph.md)
- [DE-042](../safety/planning.md)
- [DE-043](../safety/journal-and-recovery.md)
- [DE-044](../safety/verification-and-performance.md)
