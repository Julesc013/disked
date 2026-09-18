---
type: DiskEd Specification
title: Health assessment and forensic workflow
description: Independent operation contract for health.assess.
resource: disked://spec/de-111
tags:
- disked
- operations
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-111
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
  - DE-REQ-111-01
---

# Health assessment and forensic workflow

## Identity and availability

Semantic ID: `health.assess`. Operation specification: `DE-OP-011`. Earliest phase: **M3/M4**. Initial target scope: read-only observations with explicit acquisition policy. Status: specified, not implemented or qualified. No availability is implied by the presence of this document.

## Required inputs and preconditions

Known target identity and observer capability; do not assume SMART passthrough works through all bridges. Cases identify allowed scope, custody and redaction. Deep self-tests and potentially damaging reads require explicit selection.

## Planned procedure

Collect bounded observations, retain unavailable fields, distinguish vendor interpretation from raw values. If media errors exist, route toward image-first acquisition rather than destructive repair. Forensic acquisition keeps immutable custody events and qualified write-blocking observations.

## Postconditions and evidence

Health report is evidence, not a guarantee of future reliability. Forensic report states exact acquisition scope, unreadable ranges, software and operator records. No repaired original media is silently called an untouched forensic source.

## Interruption, cancellation and recovery

An interrupted health query returns partial information. A degraded device can deteriorate even under reads; stop/retry strategy belongs to the case. Recovery operates on a copy unless independently authorized.

## Required adversarial cases

No SMART over bridge, forged serial, media deterioration, accidental self-test, secret leakage, repaired original mislabeled forensic and incomplete acquisition hashes.

## Normative requirements

### DE-REQ-111-01

`health.assess` MUST enforce the preconditions, evidence and recovery limits in this operation contract before admission.

**Verification:** No SMART over bridge, forged serial, media deterioration, accidental self-test, secret leakage, repaired original mislabeled forensic and incomplete acquisition hashes.

## Related specifications

- [DE-030](../storage/identity-and-graph.md)
- [DE-042](../safety/planning.md)
- [DE-043](../safety/journal-and-recovery.md)
- [DE-044](../safety/verification-and-performance.md)
