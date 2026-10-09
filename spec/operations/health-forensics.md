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
  version: 0.1.1-proposed.1
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
updated:
  by: codex
  at: '2026-10-09T00:44:34.134398+00:00'
  scope: DE-W032 private bounded observation and support redaction contract
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

## Private native observation contract

DE-W032 first implements the [proposed observation profile](../catalog/health-observation-prototype.json)
against fake/owned values. Its immutable request binds target generation/composite
identity and observer/provider declarations. Every returned field belongs to the
requested set; missing or unavailable data stays explicit. Raw bytes and vendor
interpretation with its rule identity are separate. Neither a serial string nor a
complete response establishes physical identity or safe media.

Capture/worker epochs reject stale results. Request completion, timeout,
cancellation and worker retirement remain distinct; outstanding workers prevent
a replacement capture. Cancellation stops further dispatch without discarding
valid partial evidence or inventing exit proof. Count, byte and epoch limits fail
without silently truncating accepted observations.

The default support projection omits identifiers, raw values and interpretation
text. Its explicit policy can select additional classes; secret field content is
never exported. Classification belongs to the selected request and cannot be
downgraded by a returned field. Exact internal bytes and redacted support output
remain separate. Public admission still requires reviewed adapter classification,
actual containment, provider identity and target validation; declarations alone
are not qualification.

This private reducer does not issue queries or self-tests, access files/devices,
or implement the public command. DE-W030 native inventory remains a prerequisite
for actual observer admission. Forensic custody, acquisition coverage, write-blocking
and physical/platform qualification remain separate DE-W033/034 and later gates.

## Normative requirements

### DE-REQ-111-01

`health.assess` MUST enforce the preconditions, evidence and recovery limits in this operation contract before admission.

**Verification:** No SMART over bridge, forged serial, media deterioration, accidental self-test, secret leakage, repaired original mislabeled forensic and incomplete acquisition hashes.

## Related specifications

- [DE-030](../storage/identity-and-graph.md)
- [DE-042](../safety/planning.md)
- [DE-043](../safety/journal-and-recovery.md)
- [DE-044](../safety/verification-and-performance.md)
