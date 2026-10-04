---
type: DiskEd Specification
title: Independent verification and efficient execution
description: Optimize verified work, never cache away fresh safety checks.
resource: disked://spec/de-044
tags:
- disked
- safety
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-044
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-043
  - DE-030
  requirements:
  - DE-REQ-044-01
  - DE-REQ-044-02
  - DE-REQ-044-03
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Independent verification and efficient execution

## Verification layers

An executor's success code is evidence of its reported result, not the postcondition. Recapture through independently maintained parsing where practical; validate maps, filesystem invariants, required boot state and expected graph changes. Shared library agreement is not independent verification if both paths share the same defective parser. Retain disagreements, unreadable areas and uncertainty.

Verified-byte progress differs from bytes read, submitted, cached, written or flushed. Report all meaningful counters distinctly. A hash only covers the bytes actually hashed; sparse holes, read substitution, compression and skipped damaged ranges need explicit semantics. A healthy SMART report does not establish safe media or backup adequacy.

## Data path efficiency

Bounded aligned buffers, async pipelines, back-pressure, sparse discovery, qualified clone/copy offload and independent-extent parallelism are eligible optimizations. Record queue depth, resource ceilings, temperature and health throttles. Keep separate conservative healthy-media and failing-media policies. Do not hammer a failing device with an ordinary verification scan merely because the tool can issue reads.

## Cache rules

Cache source specifications, immutable image descriptions bound to content digests, provider manifests and qualified test results with their complete input closure. Revalidate identity, current layout, mount state, free capacity, journal availability and relevant health before mutation. A code change in shared range arithmetic invalidates more evidence than a translation update; dependency-scoped test selection must reflect this. Clean release qualification must validate the final composed artifact.

## Residual risk

Independent verification can discover damage after irreversible effects. It is not prevention or rollback. Report verified, unverified and failed postconditions separately and prevent automatic success promotion when any mandatory postcondition is unknown. Preserve failure evidence before cleanup. Limit support-bundle contents so customer data is not leaked during troubleshooting.

## Measurements under failure

Measure cold startup, input response during stalls, memory, event backlog, verified throughput, resume overhead and interruption outcome for named target/workload profiles. Define proposed budgets before measurement using [DE-045](degraded-operation.md); report actual samples and limits rather than universal millisecond guarantees. Compare equivalent preservation, verification and recovery work, with cache and media-health conditions disclosed.

Acquisition consistency is independent of byte integrity; [DE-036](../storage/acquisition-consistency.md) owns live/snapshot/application claims. Future compatibility needs exact contract/reader windows and retained recovery closure, not a promise about unknown operating systems.

## Normative requirements

### DE-REQ-044-01

Execution success MUST be followed by explicit independent postcondition verification where available; mandatory unknowns MUST prevent success certification.

**Verification:** Fake provider reports success while resulting bytes are wrong.

### DE-REQ-044-02

Safety-critical live state MUST NOT be satisfied from stale cache, even when unchanged-code tests are reused.

**Verification:** Reconnect a changed target under a cached inventory entry.

### DE-REQ-044-03

Performance reporting MUST distinguish submitted, written and verified bytes and disclose unreadable/substituted regions.

**Verification:** Inject read errors and compare counters and acquisition map.

## Related specifications

- [DE-043](journal-and-recovery.md)
- [DE-030](../storage/identity-and-graph.md)
