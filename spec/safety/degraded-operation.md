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
  version: 0.1.11-proposed.1
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
  at: '2026-10-06T13:59:38.904750+00:00'
  scope: DE-W017 interactive request containment; combined campaign in development
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

## DE-W017 interactive request containment contract

The current Windows fake composition keeps UI event processing separate from
ordinary-file fake-operation admission/inspection/cancellation. Each interactive
frontend has one background request channel, at most one executing callback and
one bounded completion slot. A second fake-operation request is refused with
`request_resource_limit` while that slot is occupied; cached graph/help/build
requests remain available. A queued frontend request is private pending state,
not a protocol response or proof that an operation was admitted.

The callback owns immutable request data and cannot retain frontend, session or
view references. A stalled call keeps its slot; there is no replacement thread,
automatic retry, or inference that effects stopped. Closing the frontend does not
cancel an already admitted worker. Disconnection during incomplete admission can
leave an unresolved immutable claim and must not authorize re-execution. This
thread boundary is not process isolation, a security boundary or a guarantee that
Windows can complete a stuck file API.

Completion must satisfy the bounded response contract and exact request identity.
Malformed, oversized or throwing completion becomes an unknown outcome, never a
claim of no effect. Unknown/invalid receipts are allocated before the callback is
admitted so its allocation failure cannot require allocating another receipt on
the failing thread. One result occupies at most the existing 64 KiB serialized
frame budget. GUI/TUI view epochs prevent a late reply from replacing edited
forms, review, selection or a newer view. The most recent earlier reply is shown
separately. The shell appends the correlated outcome without executing or replacing
current input. Durable fake-operation truth remains in its explicit state store.

The selected local responsiveness target is a 250 ms UI message/key observation
budget during a five-second delayed fake-worker admission, with a 50 ms GUI poll
and at most 100 ms console input wait. These are pre-campaign test criteria,
not qualified promises for other hosts, keyboards or kernel/driver failures.
Retain raw synthetic samples and failures. The cooperating Windows fake workers
also use the four-process, 128 MiB per-process / 512 MiB aggregate job limits in
DE-015. The campaign must query actual membership and memory, exercise a fifth
admission and committed-memory denial, and verify that disconnect/unknown outcomes
neither free live slots nor permit re-execution. Test-only fault executables are
distinct from the product; no public flag enables their delays or allocations.

These checks do not close whole-frontend memory, event/backpressure,
scratch/full-destination or the combined malformed/crashed-provider campaign:
those remain DE-W017 work until implemented and measured. The synchronous CLI/file API path also requires its
own waiting evidence and containment; interactive success cannot qualify it.

## Normative requirements

### DE-REQ-045-01

Timeout or cancellation request MUST NOT imply quiescence, no effect or permission to retry; uncertain effects MUST prevent conflicting execution until reconciliation.

**Verification:** Simulate late completion and a worker that never confirms cancellation; verify no replacement writer or false cancelled/success result.

### DE-REQ-045-02

Every admitted workload MUST have finite target-specific resource limits and a bounded frontend waiting policy, with actual measurements before responsiveness claims.

**Verification:** Inject stalled/crashed providers, huge input, full destination and slow event consumers; measure limits and verify successful unrelated observations remain usable.
