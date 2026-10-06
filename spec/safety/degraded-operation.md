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
  version: 0.1.16-proposed.1
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
  at: '2026-10-06T17:56:37.391761+00:00'
  scope: DE-W012/017 bounded fake event watch and frontend parity; owner acceptance pending
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

CLI and stdio file callbacks have the separate 4,000 ms bounded wait in DE-022.
The single occupied slot survives timeout; built-in/cached NDJSON requests remain
available while another file request is refused. A late completion does not create
a second response. The 3,000 ms standard-output wait in DE-028 applies backpressure
before the next request; output failure cannot cancel or restart admitted work.
Actual pipe backpressure and an injected file-boundary delay require their own
retained evidence, independent of interactive responsiveness.

State-store write/flush failures follow the DE-015 failure contract. The
separate test build injects disk-full, partial and flush errors at the claim,
cancellation and five worker-record transitions. Keep the original error and
uncertain admission/cancellation receipt, preserve residual bytes, and stop
transitions without retry. Cached healthy and denied observations remain usable.
Readable terminal state is not proof that its final flush succeeded.

These store/transport checks are separate from frontend memory admission below,
the later public event-stream and combined provider contracts in DE-022 and the
sections below; the initial containment slice alone does not qualify them.
Injected store boundaries do not qualify a real full filesystem or persistence
after power loss. No timeout proves retirement of an arbitrary stuck kernel call.

## DE-W017 Windows frontend memory admission

The Windows fake composition selects a 256 MiB per-process committed-memory
ceiling before any valid invocation enters a command handler or frontend. Fixed
argv/descriptor parsing and host/channel observation precede this admission so a
failure can use the selected diagnostic channel; these bounded startup steps and
the Windows loader are not covered by a post-start assignment claim. Invalid
syntax remains its original refusal without attempting budget admission.

All frontend instances for the current user/Windows session join one common
Windows job. A protected current-user DACL and `Local` namespace bind applicability;
the name includes the Windows SID. This is a cooperating-composition resource
limit, not a security boundary against the same user. Only the per-process
memory flag is configured there. No active-process, total-memory, kill-on-close,
breakaway, priority or UI policy is added. The existing worker jobs still enforce
four workers, 128 MiB per worker and 512 MiB aggregate. Closing a frontend cannot
terminate an admitted worker or free its still-live quota slot.

A matching named initialization mutex serializes creation/verification and
assignment, with a 250 ms wait. An existing job is inspected, never reset. A
missing/denied API is `memory_budget_unavailable`; mutex timeout is
`memory_budget_busy`; mismatched existing limits are `memory_budget_mismatch`;
incompatible inherited job membership is `memory_budget_incompatible`. These are
unavailable refusals (exit 3), preserving the original platform code and selected
process limit. No handler, provider, window or interactive session is initialized
after failed admission. No fallback removes or weakens inherited host policy.

Essential commands still require no provider, device probe, elevation, network,
Setup or installed service. The Windows core now dynamically uses the system
`advapi32.dll` for bounded token-SID/DACL operations, in addition to kernel APIs.
That dependency must appear in the actual loader contract and tests. A stricter
inherited host budget remains effective; success never promises 256 MiB is
available. Committed memory, working set, file cache and total host memory are
different measurements. This is not a global frontend-count or host-memory quota.

The campaign must query real job membership/limits and process memory, execute
maximum bounded NDJSON sessions and repeated GUI/TUI/shell interactions, exercise
actual commitment denial, and check concurrent frontends plus worker independence.
Inherited stricter jobs, incompatible host restrictions, existing-limit mismatch
and initialization contention need explicit fixtures. Fault controls and their
isolated object namespace exist only in a separate test executable. They cannot
alter production limits through arguments or environment variables.

Windows job nesting enforces compatible subset hierarchies and stricter effective
limits; see [Nested Jobs](https://learn.microsoft.com/en-us/windows/win32/procthread/nested-jobs)
and [job limit flags](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information).
Other hosts and historical Windows adapters require their own evidence.

## DE-W017 private observation-capture contract

The fake composition introduces a serialized capture coordinator before the
combined native provider campaign. It is an observation boundary, with no
storage-effect, cancellation, approval or writer authority. The existing compiled
graph passes through it as one immediately completed source; the resulting graph
bytes and target identities remain unchanged. Concurrent adapters must serialize
their completions at this boundary and prove process termination separately.

Register at most eight distinct nonempty ASCII source IDs of at most 64 bytes.
Each attempt binds source ID, positive u64 capture epoch and positive u64 worker
epoch. At most one outstanding attempt exists per source, and at most one new
attempt per source per capture. Timeout changes observation availability only;
it does not retire a worker, free its slot, or permit a replacement. Beginning a
new capture can invalidate old observations while old workers remain outstanding.
A completion for that exact old attempt may retire its slot, but cannot publish
its data into the new capture. Duplicate or unrelated completions change nothing.
A valid late result for the still-current capture may publish after timeout.

Each source contributes a complete bounded graph fragment. Validate the fragment
and the proposed aggregate before publication. Duplicate IDs, foreign-source ID
reuse, changed identity/generation under an existing ID, dangling cross-fragment
edges, malformed quantities and exhausted bounds reject only that contribution.
This initial disjoint-fragment rule is not a general cross-provider identity
merger; aliases/sharing can still be represented inside a fragment, as today.
Retain at most 1024 exact ID/owner/identity bindings for the coordinator lifetime.
The published aggregate retains the existing 64-node/256-edge bounds, with at
most 48 source-supplied omissions and 56 KiB serialized graph content. Remaining
space is reserved for bounded coordinator failure/freshness markers.

When a source starts a new attempt, fails, times out or is superseded, retain its
last validated content as cached evidence, changing `current` nodes to `stale`.
Existing denied/unknown labels remain explicit. A source omission identifies
pending, not-started, denied, malformed, unavailable or timed-out state and the
bounded reason/platform code. A missing source is never a successful empty
inventory. Successful unrelated fragments remain usable. Only a fully validated
current completion makes that source fresh. An explicit valid empty result may
remove its own prior observations. Publication and identity tracking are atomic;
allocation failure leaves the prior capture unchanged. Invalid content publishes
only the source's malformed state, retaining its prior content as stale and its
previous identity bindings; rejected content never contributes new identities.

Keep at most eight small observation-change notices, ordered by an exact u64
sequence for the coordinator lifetime. Notices bind capture/source/attempt and
state; they contain no durable operation outcome. A slow consumer never blocks
publication. An evicted notice produces a detectable gap: a reader with an older
cursor or a different capture epoch must obtain the current complete snapshot
and its sequence before continuing. A future cursor is invalid. No counter may
wrap. Previously obtained immutable snapshots remain unchanged.

A capture-reset notice has no source/attempt; its sequence is the new capture's
minimum valid cursor. A caller cannot combine the current epoch with a cursor
from before that reset to obtain old-capture notices. Frontend publication epochs
and provider-attempt capture epochs are separate domains. The frontend polls an
immutable source snapshot once at action admission or explicit view refresh and
acknowledges it only after successful publication. Allocation failure must not
consume a source update. Refresh does not rebase a staged request or selected ID.

The separate `disked_capture_campaign` test composition starts four effect-free
native fixture producers alongside the immediately available compiled healthy
graph. They report synthetic access denial, emit malformed JSON, delay a valid
result for 1,800 ms, or raise a native exception (0xE000D17D). A 400 ms observation
deadline marks the delayed source unknown/outstanding without replacing it. Each
producer inherits a one-process/64 MiB job and the campaign's four-process/256 MiB
job, atomically at creation, below the frontend job. These extra observer budgets
are per campaign instance; they are not admission of production observers or a
host-wide observer quota. Background callbacks own the handles and budget, never
the frontend/session. A failed OS observation retains its callback slot until the
exact owned process is observed exited. There is no kill-on-close or retry.

The private producer wire is at most 4 KiB and contains only a fixed fixture state
marker, mapped to compiled fake observations; it is not a general provider API.
The test executable's mode explanation reports parent-observed process IDs,
creation identities, actual exits, job membership/limits and peak commitment.
Its internal role, report and fault composition are absent from the product.
Essential commands do not start producers. Real CLI/stdio, Win32, TUI and shell
campaigns must retain failures, inspect healthy data, reject stale staged actions,
preserve typed input, observe late success and measure the 250 ms cached-input
target. Provider-reported denial is synthetic; the malformed pipe and exception
are real native failures. Arbitrary kernel hangs and hostile-provider security
isolation remain unqualified.

These private notices do not themselves admit public `org.disked.event/1`
streaming. DE-022 separately defines the implemented fake-operation watch
payloads, explicit negotiation and reconnect semantics over its retained store. The combined campaign must exercise the same coordinator
with real native delayed/exited/malformed fixture producers and all frontends;
isolated reducer tests alone do not close that campaign or DE-W017.

## Normative requirements

### DE-REQ-045-01

Timeout or cancellation request MUST NOT imply quiescence, no effect or permission to retry; uncertain effects MUST prevent conflicting execution until reconciliation.

**Verification:** Simulate late completion and a worker that never confirms cancellation; verify no replacement writer or false cancelled/success result.

### DE-REQ-045-02

Every admitted workload MUST have finite target-specific resource limits and a bounded frontend waiting policy, with actual measurements before responsiveness claims.

**Verification:** Inject stalled/crashed providers, huge input, full destination and slow event consumers; measure limits and verify successful unrelated observations remain usable.
