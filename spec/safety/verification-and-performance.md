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
  version: 0.1.2-proposed.1
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

## Provisional shared verification commands and observation

The [verification command profile](../catalog/verification-command-prototype.json)
owns the proposed `image.verify` prepare/execute grammar, six independent grants,
status/exit outcomes and public byte budgets. Preparation reads only the explicitly
selected generated acquisition metadata/image/map and returns a review without
creating an operation, output or verification scan. Execution binds the exact
wrapper digest, resource/store/code definitions and all grants before dispatch.

The native observer reports a separate request binding from the retained header.
The shared service compares operation/attempt/worker/capture, definition and code
identities against the state; the native layer additionally validates full retained
history, actual PID/creation/path observations and collection bytes. Declared
relationships alone authenticate no actor or retained history. A completed
observation request is distinct from the logical verification verdict. Execution
succeeds only for a matched terminal verdict, verified validated retention and
applicable recorded attachment. Invalid, throwing or oversized replies after
dispatch retain unknown outcome, reviewed digest/store and any valid allocated ID.

Strict producer schemas close the definition, grant, outcome, state, record, event,
parameters and results. Automatic semantic validation checks cross-field counters,
digests, raw bytes, quiescence, retention and independent epoch domains. Compatible
event readers may preserve additive observational fields while strict producers
reject them; unknown required features remain a typed refusal. Private definitions
can exceed a public request: keep the 64 KiB input limit and reject an oversized
review before presentation/dispatch. Do not widen it to accommodate private storage.

The proposed `org.disked.verification-operation-events/1` feature applies only to
`operation.watch` with a verify-op selector. Bound records to the exact retained
request, keep request/observer identity separate, and commit cursor advancement
only after validation and budget checks. Finite follow is at most 2000 ms, with
64 events and 786432 aggregate event bytes. Later observer failure retains the
last validated state/cursor. Observer close/timeout grants no cancellation, restart
or dependency removal. Individual filesystem latency is not universally bounded.

The private native command probe evaluates shared CLI/form/request behaviour and
actual owned self-spawn/retention. Product composition/handler, bounded request
channel and actual GUI/TUI/shell journeys remain a required gate before advertising
availability. These contracts remain proposed; no stable ABI, full DE-W034, owner,
other-platform, physical/elevation/customer/install/signing/publication qualification
is implied by shared-service or schema validation.
