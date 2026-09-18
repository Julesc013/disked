---
type: DiskEd Specification
title: Read-only partition-map verification
description: Independent operation contract for table.verify.
resource: disked://spec/de-102
tags:
- disked
- operations
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-102
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
  - DE-REQ-102-01
---

# Read-only partition-map verification

## Identity and availability

Semantic ID: `table.verify`. Operation specification: `DE-OP-002`. Earliest phase: **M2**. Initial target scope: raw disposable images, later observed physical media. Status: specified, not implemented or qualified. No availability is implied by the presence of this document.

## Required inputs and preconditions

Explicit read-only source and device geometry. Resource limits bound all entry counts and walks. Source change during reading invalidates a coherent-state claim. A forensic source may require hardware write-blocker procedures.

## Planned procedure

Read independent candidate map copies; validate signature, checksums and extents; report competing interpretations. Run independent decoder or external oracle only if its read-only behavior is admitted. Produce proposed repair candidates as data, never automatic writes.

## Postconditions and evidence

Diagnostics refer to exact source regions and provider versions. The report separates structural validity, consistency, inferred intent and unsupported metadata. No "all healthy" conclusion follows solely from CRC validity.

## Interruption, cancellation and recovery

Interrupted verification returns partial coverage. Preserve useful diagnostics but never promote incomplete coverage into a valid-map certificate.

## Required adversarial cases

EBR cycle, array multiplication overflow, GPT valid-but-disagreeing copies, truncated image, invalid UTF-16 name, overlapping entries and hot-removal.

## Normative requirements

### DE-REQ-102-01

`table.verify` MUST enforce the preconditions, evidence and recovery limits in this operation contract before admission.

**Verification:** EBR cycle, array multiplication overflow, GPT valid-but-disagreeing copies, truncated image, invalid UTF-16 name, overlapping entries and hot-removal.

## Related specifications

- [DE-030](../storage/identity-and-graph.md)
- [DE-042](../safety/planning.md)
- [DE-043](../safety/journal-and-recovery.md)
- [DE-044](../safety/verification-and-performance.md)
