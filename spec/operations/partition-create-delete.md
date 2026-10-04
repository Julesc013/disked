---
type: DiskEd Specification
title: Create or delete a partition entry
description: Independent operation contract for partition.edit.plan.
resource: disked://spec/de-105
tags:
- disked
- operations
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-105
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
  - DE-REQ-105-01
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Create or delete a partition entry

## Identity and availability

Semantic ID: `partition.edit.plan`. Operation specification: `DE-OP-005`. Earliest phase: **M5 image / M6 admitted physical subset**. Initial target scope: basic table on explicitly selected healthy target. Status: specified, not implemented or qualified. No availability is implied by the presence of this document.

## Required inputs and preconditions

Explicit region/type or exact existing partition identity, known table, no unknown overlapping structure, no active consumers, admitted table writer and a reviewed deletion loss report. Deleting an entry is not erasing data or securely sanitizing a device.

## Planned procedure

Project current/desired graph; check alignment/capacity and reserved regions; generate a bounded table change and independent verification. A filesystem format is a separate dependency, not an incidental side effect. Preserve unrelated boot code and other entries.

## Postconditions and evidence

Expected table and object relations are present; unrelated bytes unchanged. Removal is reported as metadata deletion, not guaranteed confidentiality. The operator can inspect recovery candidates before further writes.

## Interruption, cancellation and recovery

Recovery class depends on metadata retention and subsequent writes. Recreating a deleted entry is not reliable rollback after content has been overwritten.

## Required adversarial cases

Active page-file volume, stale partition ID, hidden metadata in a gap, delete-vs-erase confusion, duplicate GUID, interrupted table write and follow-up format without approval.

## Formatting dependency

[DE-113](filesystem-format.md) owns filesystem creation and its data-loss, discard and verification rules. A table edit does not authorize a subsequent format, mount or sanitization. Any composite plan binds and admits each operation separately.

## Normative requirements

### DE-REQ-105-01

`partition.edit.plan` MUST enforce the preconditions, evidence and recovery limits in this operation contract before admission.

**Verification:** Active page-file volume, stale partition ID, hidden metadata in a gap, delete-vs-erase confusion, duplicate GUID, interrupted table write and follow-up format without approval.

## Related specifications

- [DE-030](../storage/identity-and-graph.md)
- [DE-042](../safety/planning.md)
- [DE-043](../safety/journal-and-recovery.md)
- [DE-044](../safety/verification-and-performance.md)
