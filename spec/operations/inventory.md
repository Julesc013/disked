---
type: DiskEd Specification
title: Bounded native inventory
description: Independent operation contract for target.inventory.
resource: disked://spec/de-101
tags:
- disked
- operations
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-101
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
  - DE-REQ-101-01
---

# Bounded native inventory

## Identity and availability

Semantic ID: `target.inventory`. Operation specification: `DE-OP-001`. Earliest phase: **M1/M3**. Initial target scope: fake targets first; later native NT read-only enumeration. Status: specified, not implemented or qualified. No availability is implied by the presence of this document.

## Required inputs and preconditions

An explicit scope identifies local host or image set. No automatic deep scan, media spin-up or elevation is implied. Read-only handles are requested; access denial is an observation, not an empty success. Inventory budget and cancellation policy are explicit.

## Planned procedure

Enumerate presentation paths; query bounded identity/capacity/sector observations; discover basic relationships; merge only identities supported by evidence. Preserve inaccessible resources and conflicting reports. Return a paged immutable snapshot with capture time and omissions. Never auto-select the first disk for a subsequent operation.

## Postconditions and evidence

No storage writes occurred. The graph identifies source provider and capture revision. Results distinguish unknown, denied, absent and present. A later mutation must freshly identify the selected resource.

## Interruption, cancellation and recovery

Cancellation can stop between bounded queries. Partial inventory is labeled partial. No journal is required for storage effects because no storage mutation is authorized; application output writes have ordinary file ownership rules.

## Required adversarial cases

Duplicate USB serials, cloned GUIDs, inaccessible volume, removed device, stale ordinal, sleeping media, enormous provider response and cancellation mid-enumeration.

## Normative requirements

### DE-REQ-101-01

`target.inventory` MUST enforce the preconditions, evidence and recovery limits in this operation contract before admission.

**Verification:** Duplicate USB serials, cloned GUIDs, inaccessible volume, removed device, stale ordinal, sleeping media, enormous provider response and cancellation mid-enumeration.

## Related specifications

- [DE-030](../storage/identity-and-graph.md)
- [DE-042](../safety/planning.md)
- [DE-043](../safety/journal-and-recovery.md)
- [DE-044](../safety/verification-and-performance.md)
