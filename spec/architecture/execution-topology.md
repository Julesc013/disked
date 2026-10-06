---
type: DiskEd Specification
title: Essential startup and execution roles
description: Keep built-in diagnostics available before probes and bind roles to explicit hosts and resources.
resource: disked://spec/de-015
tags:
- disked
- architecture
generated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
status: draft
disked:
  id: DE-015
  profile: disked-spec/1
  version: 0.1.16-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-010
  - DE-022
  requirements:
  - DE-REQ-015-01
  - DE-REQ-015-02
updated:
  by: codex
  at: '2026-10-06T17:56:37.398435+00:00'
  scope: DE-W012/017 bounded fake event watch and frontend parity; owner acceptance pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Essential startup and execution roles

## Essential, inspection and execution tiers

Essential startup exposes build/help/command information, policy explanations and explicit local saved-report inspection before any device probe. It requires no elevation, network, optional provider or Setup extraction. Corrupt personalization may be bypassed with a diagnostic; enforced policy must remain effective, or effects requiring that policy are unavailable.

Inspection publishes incremental identity-bound observations, with denied, stale, incomplete and failed contributions retained. Expensive scans, tape movement, snapshots and device self-tests are explicit tasks. Execution adds reviewed plans, authority, recovery resources and verification; it is not implied by opening a view.

The Windows fake composition now admits valid frontend invocations to the
256 MiB per-process committed-memory job described in DE-045. Bounded token/SID
and protected-DACL setup dynamically requires the system `advapi32.dll`; it does
not initialize a provider or GUI. Fixed parsing/host observation and the loader
precede assignment. A host-policy incompatibility refuses execution without
breakaway or changing host limits. All cooperating frontends share one memory
ancestor so independently lasting workers can still join the existing stricter
worker jobs. There is no kill-on-close policy or aggregate frontend quota.

## Roles and boundaries

Coordinator, observer, planner, executor, verifier and recovery executor are logical roles. Their record binds host identity, target profile, provider closure and resources. A local fake session may use one process. On a qualified host, another instance of the same executable may isolate a probe or execute an admitted job. A process boundary is not automatically a security boundary; retain actual enforcement limits.

The frontend can disconnect while the job remains identified. Role recovery does not mean restarting an uncertain writer. A cross-boot or remote executor independently validates the same target, plan version and bounded supported operations. The first broker is local-only. Neither an SDK nor installation enables a remote listener.

An independent storage recovery path must work without the normal GUI, optional discovery pipeline or network. Software repair uses the servicing owner's independent payload and journal, separate from storage recovery. Targets lacking process protection publish a constrained profile rather than inheriting NT containment claims.

## DE-W016 fake worker execution contract

The native Windows development composition admits `plan simulate <fixture_id>
--state-dir <directory>` for the compiled fixtures `fake:complete`,
`fake:verification-failure`, `fake:cancel-checkpoint` and `fake:unknown` only.
This is an asynchronous synthetic workload, not the general planner, an image
writer or provider admission. The fixture's sole effect is an in-memory counter;
its evidence store uses ordinary disposable files in the explicitly supplied
directory. No storage plan, approval, privilege or hardware guarantee is inferred.
`operation inspect <operation_id> --state-dir <directory>` reconnects to its
retained state; `operation cancel <operation_id> --state-dir <directory>` records
a cancellation request. DE-022 now defines the bounded fake-only `operation watch`
extension and its explicitly negotiated NDJSON event frames. It observes the same
retained chain without creating, cancelling or replaying an operation.

The directory must already exist, be an ordinary empty local drive directory on
first admission, and pass the prototype's absolute-path, length and reparse checks.
UNC/device namespaces, additional named streams and reparse components are refused.
The prototype caps the directory path at 240 UTF-16 units. One directory identifies
one operation. Exclusive creation of an immutable request record serializes start:
repeating the same fixture/build/provider request inspects the existing operation;
different content is `idempotency_conflict`. An incomplete admission or dead worker
never triggers automatic re-execution. The operation ID is a fresh random identity,
not a transient process ID or path. Inspect/cancel must match that identity and the
local host binding. No automatic history deletion or state migration occurs.

The private store consists of `request.json` (immutable admission identity),
`operation.records` (append-only evidence) and `cancel.request` (one-byte request
flag). Directory identity includes volume/file identity; the host binding hashes
the current Windows SID and computer name. This is a local applicability check,
not a cryptographic machine identity. A changed build can read an existing record,
but cannot reuse its admission as a matching new start.

The parent resolves its running executable and self-spawns without a shell or
elevation. It uses `DETACHED_PROCESS`: no inherited or newly allocated console.
The worker's current directory is its explicitly selected state store,
so it does not keep the client's unrelated launch directory open after disconnect.
A restricted handle list carries only a bounded bootstrap channel,
the already-open append-only record file, a cancellation flag and an admission
event. No parent standard streams or arbitrary other handles are inherited.
The worker receives no caller-selected executable, script, provider DLL, target
path or raw-device handle. It checks the inherited capability roles and compiled
source/input/image identity before running the fixture. Explicit file permissions
restrict newly created records to the current user. Process creation and file
permissions are measured boundaries, not a sandbox or protection from a compromised
same-user process. Exact-image elevation remains DE-DEC-005/008 work.

Admission returns `accepted_running` (exit 5) only after the worker has flushed its
initial record and signaled the admission event. The response includes operation,
attempt and worker epoch identities. A timeout or broken admission returns an
honest unknown outcome with the operation ID; it does not kill/restart an uncertain
worker or pretend no work began. Client exit does not own worker lifetime. The
worker has one process slot, finite memory, record and workload budgets. The job
has no kill-on-parent-close policy. Zero replacement attempts are admitted.

If the first read already observes a terminal record, return a completed request
with that terminal operation state instead of claiming it is still running.

This prototype uses a 3,000 ms admission wait, 128 MiB per-process job memory limit,
one active process per private job, a 2 KiB bootstrap message, 16 KiB maximum record, at most 64
records and 1 MiB maximum history. The worker checks its actual job limits before
admission. Pre-effect waits are 250 ms (2,000 ms for the cancellation fixture),
followed by 500 ms in-flight and 250 ms before verification; cancellation is polled
at 20 ms intervals. These bound synthetic workload and admission, not the duration
of a blocked Windows file API. DE-W017 adds frontend callback waiting (DE-022),
interactive request containment (DE-045) and output waiting (DE-028); none proves
that a stuck kernel request retired.

DE-W017 adds an outer named job for the cooperating fake composition, scoped to
the current Windows user and Windows session. It admits at most four processes,
128 MiB committed memory per process and 512 MiB aggregate job memory. These are
job-accounting limits, not frontend memory limits or a machine-wide quota. The
current-user DACL and name derived from the local host binding do not protect
against a hostile same-user process. An existing job must have the exact expected
limits; a mismatch or incompatible inherited job hierarchy refuses admission
without resetting limits or breaking away from the host's policy.

Both jobs are supplied using Windows 10's
[`PROC_THREAD_ATTRIBUTE_JOB_LIST`](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute)
at process creation. There is no suspended child awaiting a later parent-owned
assignment/resume step. Neither job kills a worker when a client closes, and no
timeout frees its live slot or authorizes replacement. A failed creation after
the immutable claim remains unknown and inspectable; a later free slot does not
retry that claim. These Windows mechanisms do not qualify older adapters.

The retained private operation projection separates logical phase, attempt phase,
effect certainty, cancellation, recovery and outcome. Sequence is decimal u64 in
one operation/attempt/worker epoch domain. External or late observations with a
different identity/epoch cannot advance it. A synthetic effect moves through
not-started, in-flight and observed states; verification success and failure are
distinct. Cancellation before effect dispatch can be acknowledged as cancelled.
After dispatch, a request cannot erase the effect; verification may finish normally
with cancellation still merely requested. No requested cancellation implies quiescence.

Records are bounded, append-only JSON lines with a sequence and hash chain over
the specified native JSON encoding. A partial tail, invalid transition, mismatched
identity, over-limit file or corrupt hash is not successful completion. Inspect
does not repair or rewrite records. It reports a successful read separately from
the operation state; a missing/dead/reused worker with a nonterminal record yields
`unknown` (exit 6), retaining the last recorded state as evidence. A terminal
verified record can remain inspectable after worker exit. These fake records are
not the production crash-consistent storage journal, a signature or safety evidence
for real media. Same-user tampering and host-injected code remain explicit limits.

The strict provisional producer shapes are `fake-operation.schema.json` and
`fake-operation-record.schema.json`. The record digest is lower-case SHA-256 over
the native compact UTF-8 JSON object without `digest`; keys are sorted, controls
use `\u00xx`, and the line terminator is excluded. The first `previous` digest is
64 zeroes. Native history reading validates the entire chain and guarded transition
sequence; validating one record alone does not qualify the history. Completed
`operation inspect` returns exit 0 even for retained verification failure: its
request is a successful read, while the operation's outcome/recovery fields remain
failed/required. Cancellation returns a request receipt, never an inferred worker
acknowledgement. An observed terminal record returns `too_late` without changing
its flag; a request racing completion may remain unacknowledged.

### DE-W017 state-store failure contract

Before exclusive claim creation, an invalid request or unavailable store can be
refused without admitting a worker. Once the claim file has been created, a
failed write, partial write or failed flush returns `unknown` with the already
allocated operation ID and an unresolved admission. Preserve the original error
code and any bytes left in the store. Do not remove, overwrite or retry the claim;
a later matching start only reconciles it. If its identity cannot be read, that
reconciliation remains unknown rather than creating another operation.

A cancellation receipt distinguishes failure before attempting its flag write
from failure during write/flush. After the write is attempted, failure returns
`unknown` with the operation ID, `cancellation_request: unresolved`, the preceding
state observation and the error. A worker may already have seen the new flag;
neither refusal, acknowledgement nor quiescence may be inferred. Explicit later
inspection can observe the worker's actual checkpoint decision.

Any operation-record write/flush failure stops that worker's further transitions;
it cannot dispatch an effect after failure to record preparation/dispatch, or
retry an effect after failure to record its observation. A malformed/partial tail
remains unknown and unchanged. A readable nonterminal prefix with an exited
worker remains unknown. A complete terminal record establishes the recorded
synthetic outcome as observed now; record readability/hash validity alone does
not establish that the last flush succeeded or qualify persistence after power
loss. This distinction applies to all fake records, including healthy runs.

The local campaign injects disk-full, partial-write and flush errors at explicit
claim, cancellation and worker-transition boundaries in a separate test build.
Tests use ordinary disposable files and retain the actual residual bytes, original
error, process outcome, repeat-start behavior and unrelated cached observations.
The product does not accept the injection controls. No host volume is filled;
these boundary injections do not qualify a real full filesystem or storage driver.

Acceptance requires actual same-file launches, clean handle inheritance, exact
record identities, bounded admission waits, killed-client survival, reconnect from
another client, duplicate/mismatched starts, cancellation at both sides of the
checkpoint, worker death, partial/corrupt records and late-epoch refusal. Retain
commands, process identities, hashes, imports, resource observations and the
specific threat-model limitations. Spec-only or reducer-only checks are insufficient.

## Normative requirements

### DE-REQ-015-01

Essential startup MUST run without opening devices, fetching dependencies, extracting Setup or requesting elevation.

**Verification:** Trace fake startup with absent providers, corrupt optional settings and offline networking; help/build/command discovery must remain available.

### DE-REQ-015-02

Every executor/verifier/recovery role MUST bind its execution host and supported plan subset; loss of a remote target MUST NOT redirect to local storage.

**Verification:** Reconnect and cross-boot fake transcripts with host mismatch, unknown required features and missing remote target; require explicit refusal.
