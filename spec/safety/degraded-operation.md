---
type: DiskEd Specification
title: Bounded responsiveness and failure containment
description: Bound waiting and resources without treating timeout as proof that effects stopped.
resource: disked://spec/de-045
tags:
- disked
- safety
generated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
status: draft
disked:
  id: DE-045
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-015
  - DE-043
  requirements:
  - DE-REQ-045-01
  - DE-REQ-045-02
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Bounded responsiveness and failure containment

## Failure-state contract

| Condition | Required outcome |
|---|---|
| Access denied | Retain permitted observations and the exact denial. |
| Optional provider absent/crashed | Mark its contribution unavailable; preserve unrelated results. |
| Probe timeout | Bound frontend waiting; show stale/unknown data and outstanding I/O state. |
| Writer timeout/disconnect | Retain operation and recovery closure; quarantine conflicting effects until reconciled. |
| Low memory/full destination/event backlog | Enforce budgets, stop admitting new work, retain recoverable state where possible. |
| Corrupt personalization | Offer built-in diagnostics; preserve enforced policy. |

Cancellation requested, completion observed, target quiescent and safely reversible are different facts. [CancelIoEx](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-cancelioex) requests cancellation without waiting for completion, and I/O may complete normally. Its documented client floor is Vista; an XP adapter needs its own qualified mechanism. A watchdog cannot guarantee recovery from a hung kernel/controller.

## Budgets and measurements

`schemas/resource-budget.schema.json` records target/workload-specific proposed limits for startup, input latency, probe waiting, worker count, replacement attempts, memory, frame/event queues, outstanding I/O and scratch. Example numbers are synthetic schema fixtures, not measured promises. Each implementation selects measurable budgets before the fault campaign and retains actual environment, samples, workload, distributions and failures.

Bound work per controller/device failure domain where the host can enforce it. Do not spawn unlimited replacement workers. Retire observation workers only when their remaining authority and outstanding effects are understood. Never restart a writer, release its resources, unload dependencies or service its image solely because it stopped responding. Backpressure may coalesce replaceable progress with an explicit sequence gap/resnapshot path; it cannot discard durable operation truth.

## Normative requirements

### DE-REQ-045-01

Timeout or cancellation request MUST NOT imply quiescence, no effect or permission to retry; uncertain effects MUST prevent conflicting execution until reconciliation.

**Verification:** Simulate late completion and a worker that never confirms cancellation; verify no replacement writer or false cancelled/success result.

### DE-REQ-045-02

Every admitted workload MUST have finite target-specific resource limits and a bounded frontend waiting policy, with actual measurements before responsiveness claims.

**Verification:** Inject stalled/crashed providers, huge input, full destination and slow event consumers; measure limits and verify successful unrelated observations remain usable.
