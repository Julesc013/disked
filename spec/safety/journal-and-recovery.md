---
type: DiskEd Specification
title: Journal, recovery and durability
description: Explicit recovery classes without false transactional or rollback claims.
resource: disked://spec/de-043
tags:
- disked
- safety
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-043
  profile: disked-spec/1
  version: 0.1.6-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-042
  - DE-041
  requirements:
  - DE-REQ-043-01
  - DE-REQ-043-02
  - DE-REQ-043-03
updated:
  by: codex
  at: '2026-10-08T23:01:37.720126+00:00'
  scope: DE-W040 bounded semantic binary journal declaration reader; no live durability, authority or replay admission
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
- id: review-08a8246-2026-10-04
  resource: ../references/sources.json#review-08a8246-2026-10-04
---

# Journal, recovery and durability

## Recovery semantics

Classify each operation as atomic-metadata (only when proven), replayable, resumable, rollback-capable, forward-recovery-only, irreversible-after-step, backup-required or forensic-best-effort. These can combine with precise scope. A small journal does not retain the original contents of a multi-terabyte overlapping move. Once overwritten bytes are absent from all backups, metadata cannot reconstruct them.

## Required journal properties

The eventual on-disk journal needs magic, exact encoding version, target and plan identities, provider closure, sequence, record kind, bounded payload length, checksums and explicit commit/seal behavior. Its parser rejects truncated, reordered, mismatched or unsupported critical records. A durable authorization/intention record precedes a bounded external effect; a verified completion record follows required target flush and recapture. A crash between effect and completion produces uncertain state requiring observation, not blind replay.

This baseline intentionally does NOT freeze a new binary journal encoding before the storage/durability spike. `DE-DEC-004` blocks production writer implementation until exact byte layout, torn-write handling, checksum, sector assumptions, flush guarantees, recovery algorithm and fault model are reviewed. `catalog/journal-model.json` defines state transitions for design tests; it is not a runtime journal or evidence that a power-loss test passed.

## Placement and retention

Store the journal/recovery capsule on a different physical resource or an explicitly owned area proven outside affected extents and failure domains. Alignment gaps are not free space. Record storage independence limitations: another partition on the same failing disk is not an independent backup. Keep the exact recovery-compatible provider closure reachable without network dependence. Redact secrets while preserving references needed by the operator.

## Recovery capsule

Include reviewed plan, original map/boot metadata, target identity, expected states, journal bootstrap, tool hashes, verifier contract, required backup references and human procedure. Verify the capsule before admitting a high-risk step. Recovery reidentifies the disk after reboot and refuses ambiguous matches. Signed or hashed capsules do not make their operation correct; they bind what was reviewed.

## Cancellation and flush

There is no universal cancellation point or atomic GPT switch. Mark safe checkpoints by operation, and distinguish user cancellation request from confirmed quiescence. Flush is a provider capability whose guarantees depend on stack and hardware. Successful API return may not prove power-loss persistence; qualification must describe cache/controller assumptions and physical tests where claimed.

## Lifetime and generation retention

Timeout, client loss or cancellation request does not seal an unobserved effect. Preserve the affected target's quarantine and exact journal/provider/executor identities until quiescence and postconditions are established. A replacement worker cannot blindly replay. Software maintenance must retain required generations, including when the operation is unreachable, until reconciliation permits retirement.

The recovery closure includes independent code access, state, reconstruction data, credential references and physical dependencies. Configuration caches and another partition on a failing disk do not meet an independent-backup requirement. DE-DEC-004 remains unresolved: state-model checks do not prove durable runtime encoding or power-loss safety.

## Independent recovery properties and operation dimensions

The prototype plan's scalar recovery summary is insufficient for executable writers. Before DE-W040/041, define per-step resumability, backup dependence, cancellation checkpoints and irreversible boundaries, and derive a conservative plan summary. These properties can coexist; do not enumerate every combination into another scalar status.

Separate logical operation state, execution attempt, worker liveness, effect certainty, cancellation request/acknowledgement and recovery state. The current `catalog/journal-model.json` is an unguarded design graph only; reachability does not prove legal transitions. DE-W017 adds guarded fake scenarios with operation/attempt IDs, capture and worker epochs, sequence domains and explicit ownership transfer. Cover old worker late completion, client disconnect/reconnect, cancellation followed by normal effect completion and failed verification. Starting another observer cannot retire a possibly active writer or release its dependencies.

## DE-W040 private binary codec proposal

The first native spike is `source/runtime/journal/codec.*`, a private C++14
codec exercised by `journal_codec_probe`. It is **not linked to disked.exe** and
offers no file writer, effect dispatch, tail repair or production admission.
[The exact profile](../catalog/journal-prototype.json) owns the byte layout.
All multibyte integers are unsigned little endian; payloads are opaque bytes.
No native struct layout, JSON canonicalization or sector atomicity is assumed.

The 192-byte file header starts with ASCII `DEJPR001`, format major/minor 1/0,
header length 192, zero flags and payload limit 65536. It binds a nonzero 16-byte
journal identity and three nonzero 32-byte digests: immutable plan definition,
participating target identities/epochs and provider/executor closure. Bytes
136..159 are zero. SHA-256 of bytes 0..159 occupies bytes 160..191. Supplied
expected bindings must match exactly before any record is visited. They must
come from independently established plan/resource/code observations, not from
the untrusted header itself; this codec cannot establish their authority.

Each record has a 112-byte prefix, a payload of 0..65536 bytes, and a 32-byte
trailer. Prefix fields are ASCII `JREC`, kind/flags (u16 each), prefix/payload
lengths (u32 each), sequence (u64), journal publisher identity (16 bytes),
publisher epoch (u64), previous digest (32 bytes) and payload SHA-256 (32 bytes).
Sequence starts at one and increases by one in the journal's sequence domain;
publisher identity/epoch are separate observations, not effect-worker authority.
The first previous digest is the file-header digest. The trailer hashes the
file-header digest followed by the complete prefix and payload. Hashes detect
alteration and bind context; they do not authenticate receipts or storage.

Known critical record kinds 1..9 are PlanDefinition, ReviewReceipt, Grant,
AdmissionReceipt, Intention, VerifiedCompletion, CancellationRequest,
RecoveryObservation and Seal. Their flags must be exactly one. Observation
kind 32769 has zero flags. Strict producers emit only these kinds. Compatible
readers may preserve/ignore unknown zero-flag kinds in 32768..65535; unknown
critical kinds, unknown low kinds and all other flag bits are rejected.
Observational compatibility never permits unknown mutation semantics.

The scanner visits one verified record at a time, limits a source to 16 MiB and
4096 records, and requests no read larger than 65536 bytes. It does not retain
the whole source or all payloads. Ports must return exact requested lengths;
short/oversized reads or exceptions are observation failures. A complete invalid
record, chain/order mismatch, unsupported critical record or data after Seal
is invalid, not a repairable torn tail. A partial final prefix/body/trailer is
reported as a torn tail with the last verified prefix. A partial/invalid file
header establishes no verified journal identity. Neither a verified prefix nor
an observed Seal authorizes replay, truncation, release of dependencies or a
completed logical operation. An optional semantic visitor may reject a record;
such a record does not extend the accepted prefix.

This codec qualifies byte framing and bounded reading only. The separate
`definitions.*` fake-model component now proposes exact immutable payloads,
receipt bindings and composable recovery properties under
[DE-042](planning.md#de-w040-private-immutable-definition-proposal). Definition,
resource and provider digests can supply the three header digest bindings;
review/grant/admission receipts and execution event kinds match framing kinds
1..8. The separate semantic declaration reader below now binds these payloads
to binary framing; no authenticated publisher or live durability proof exists.
The separate closed fake-memory model below exercises guarded effect/flush
transitions, freshness/ownership and reconciliation. Real provider durability
adapters and physical qualification remain subsequent work. Intention must be retained and qualified
durable before an effect; verification/required target flush precede completion.
An uncertain effect requires observation, never replay solely from codec output.
DE-DEC-004 remains proposed and blocks the production journal writer.

## DE-W040 guarded fake-memory execution contract

`guarded_model.*` is a closed native model under
[a private profile](../catalog/guarded-journal-prototype.json). It connects the
immutable definition and initial review/grant/admission data to simulated journal
and target state. It is separate from the unguarded design graph, the byte codec
and `disked.exe`. It authenticates nobody and exposes no host file/device/process
or production executor port. Fake observations and flush outcomes are explicit
test assumptions. Their agreement qualifies only this model.

The initial three receipts are review, grant and admission, validated against the
definition. Admission must include every predecessor of its selected steps. The
definition and receipts begin as four volatile fake log entries; a qualified fake
journal flush is required before worker dispatch. Positive budgets are selected
before the run: at most 512 entries, 1 MiB per journal generation, four attempts,
four journal generations and 1024 actions. Actions are at most 65536 bytes;
wrapped fake log events are at most 131072 bytes. Each action binds the current operation,
attempt, worker identity and positive worker epoch. Observation captures have a
separate positive, strictly increasing capture-epoch domain and observer identity.

Every fresh capture includes all resources, their identity/state digests, expected
epoch and availability. It must match the fake resource port and fixed identity/
epoch/code/reconstruction bindings. Captures are invalidated by resource changes
or a new worker. Before intention/dispatch, each effect's current state equals its
before digest, the capture remains current, code/journal/backup dependencies are
available, and predecessor steps have durable completions. Untouched participating resources retain their plan-basis state; completed effects
advance their expected digests. A change to a future target invalidates the current
plan too. Each target flush revalidates bound identities/availability and the
postconditions being flushed; missing or substituted journal storage cannot
acknowledge journal durability.
The model orders one
bounded step at a time. No target state changes during intention or planning.

Intention append and journal flush are separate transitions. Dispatch requires a
complete, acknowledged stable intention. An effect result may report after,
before or mixed state; submitted/result counts are not verified completion. A
qualified target flush and later fresh independent fake capture matching every
declared effect postcondition precede completion append. The step completes only
when that completion becomes an acknowledged stable journal entry. Final seal
requires every selected step complete or a valid cancellation checkpoint, known
effects and an exited worker. A stable seal cannot substitute for live identity/
state observation when assessing dependency retirement after a crash.

Cancellation request and checkpoint acknowledgement are distinct. A request
blocks another dispatch but lets an already dispatched effect reach verification.
Checkpoint acknowledgement requires its request durable and no uncertain effect;
after a step it also requires that step's declared cancellation checkpoint. Client
disconnect/reconnect changes presentation attachment only. Timeout marks worker
liveness stalled and the operation unresolved without releasing dependencies or
restarting effects. A late exact-generation result can change the fake observed
target, but cannot turn that timeout into accepted completion.
An unavailable or substituted target cannot receive a late result's simulated
write through its current alias; the old bounded effect remains uncertain.
Confirmed worker exit is an explicit fixture observation, never inferred from a wait.

Recovery requires worker exit and a capture newer than the exit observation, exact
resource/code/reconstruction identities and a qualified recovery flush followed
by another capture. Before/after reconciliation matches all active step effects;
terminal reconciliation checks the cumulative state of completed steps. A durable
recovery observation of after-state can close an interrupted step. A durable
before-state observation can propose retry only for a declared replayable step
when a stable intention may have authorized dispatch. If no stable intention
exists, the complete fake prefix plus confirmed quiescence establishes an
unstarted step under this model's acknowledged-flush/dispatch assumption; a new
admission may start it without claiming replayability. Missing/corrupt physical
journal data does not establish this absence proof.
Retry then needs a new, previously unused attempt identity, strictly newer worker
epoch, a separately durable model admission and another fresh capture. The fresh
attempt record binds the checkpoint separately from the original v1 admission's
basis observations; it does not reinterpret those observations as current state
or authenticate new operator authority. Late prior-generation messages refuse.

Append-before, torn append, failed flush and unqualified flush faults stop further
normal dispatch. Complete volatile entries and a partial tail are retained.
Crash injection may preserve an unacknowledged complete prefix and any dispatched
unflushed after-state; acknowledged stable prefixes/states cannot be lost under
the selected fake flush assumption. Reboot always requires observation and never
automatically replays. A partial tail blocks further append. Explicitly forking a
new fake journal generation requires quiescence and fresh observation, retains the
old prefix/tail digest and does not itself transfer worker/effect authority.
An incomplete bootstrap remains unbound and cannot authorize retry.

The fake log hashes canonical events and their previous digest as specified by
the profile; this is an inspectable simulated history, not a new physical ABI.
Snapshot dimensions and counters remain separate. Resources remain retained;
retirement eligibility requires a stable terminal outcome, exited worker, current
postcondition capture and no uncertainty. Illegal inputs/transitions leave state
unchanged; injected environment failures explicitly leave unresolved state.
The semantic declaration reader below is separate from this model. A native model
event producer/reader integration, authenticated authority, real flush adapters
and physical crash/power-loss qualification remain required later work.

## DE-W040 semantic binary journal declaration contract

`semantics.*` and `journal_semantic_probe` join bounded binary framing to the
private immutable-definition and receipt contracts under
[a private profile](../catalog/journal-semantics-prototype.json). This reader is
separate from `disked.exe` and from the closed guarded model. Inputs are declarations,
not authenticated facts, actual flushes or current target observations. The caller
supplies an independently established expected definition, header bindings and
nonzero binary publisher identity with positive epoch. Expected plan/resource/
provider digests must equal that definition before source reads. All records,
including compatible observations, match that publisher binding; worker identities
and epochs stay separate.

The first critical payload is the exact expected canonical definition. Kinds 2/3
carry v1 review/grant receipts, and the initial kind 4 carries a v1 admission.
References must precede admission, scope/permissions/acknowledgements match the
definition and selected steps include predecessors. Critical record IDs are unique
within this private journal profile. Additional reviews/grants do not change the
admitted operation/scope. This stricter journal profile does not change the v1
inspector's standalone idempotent-receipt behavior.

Kinds 5..9 carry exact `org.disked.journal-effect-prototype/1` payloads with plan,
admission digest, operation/attempt/worker identity and epoch, per-attempt sequence,
step, event and typed details. Binary journal sequence, worker epoch and capture
epoch are distinct domains. Event sequence starts at one for each admitted attempt
and is contiguous. All resource capture rows are complete, sorted and available,
matching fixed identity/epoch bindings and their expected state. Untouched resources
retain basis state; completed writes advance it. Capture epochs strictly increase
across critical capture claims.

Intention names an admitted uncompleted step with completed predecessors, matching
before-state and no overlapping intention, cancellation or declared worker exit.
Completion names the pending intention, declares a qualified fake target flush and
a newer matching after-state capture, and cannot follow declared worker exit.
These are internally checked claims, not evidence that intention or target bytes
were durable. Cancellation records a request and blocks another intention; it does
not close an uncertain effect.

Recovery declares exited worker, exit/capture/qualified fake flush order and an
exact before/after/terminal capture. After-state requires a pending intention and
may close its declared step. Before-state remains useful even for a nonreplayable
step, without admitting retry. Checkpoint kind 4 instead uses
`org.disked.journal-checkpoint-admission-prototype/1`: it binds the initial admission
digest, exact current-attempt binary recovery-record digest and a newer matching
capture; it requires a distinct attempt and strictly newer worker epoch. If an
intention may have authorized the old step, retry requires its declared
replayability. An unstarted step is distinguished under the private fake model's
assumptions only; journal absence never grants real authority. A checkpoint keeps
initial scope and cannot reinterpret v1 basis observations as fresh operator
authority.

Seal declares exited worker and a later matching capture. Completed outcome
requires every selected step declared complete and no unresolved intention.
Cancelled outcome requires a request, declared cancellation checkpoint and
before-state reconciliation of any pending intention. Seal remains historical
data; no record or accepted prefix establishes live quiescence or retirement.

Critical payloads are exact compact sorted-key ASCII JSON at most 65536 bytes,
without alternate escaping or whitespace. Unknown fields/versions are rejected.
This payload encoding is distinct from the guarded model's larger JSON event
wrapper. Unknown noncritical observation payloads stay opaque and cannot change
the semantic projection; framing still checks their identities, hashes and order.
The reader retains at most 128 review/grant/initial-admission receipts and 1 MiB
of canonical definition/receipt bytes, permits 1024 typed events and four attempts,
and retains the framing source/read/count limits. Serialized-byte limits are not
a measured bound on native allocator memory.

Acceptance commits semantic state only after the whole record passes. A rejected
record leaves the last accepted projection and byte/digest prefix unchanged; torn
tails and source failures retain that prefix without repair or truncation. A valid
prefix can still have an incomplete bootstrap. Projection fields are explicitly
declared history; authentication, effect/replay/retirement authority and durability
qualification remain false, and live reconciliation remains required. Integrating
the guarded model's event producer with this reader, real adapter evidence and
independent safety review remain work; DE-DEC-004/008 remain proposed.

## Normative requirements

### DE-REQ-043-01

Every admitted mutation MUST declare its recovery class and MUST NOT claim rollback without retained reconstruction data.

**Verification:** Review overlapping-move fixture and require backup/recovery classification.

### DE-REQ-043-02

Journal encoding and durability assumptions MUST be accepted before any production journal writer is admitted.

**Verification:** Decision gate DE-DEC-004 blocks physical-write work.

### DE-REQ-043-03

Recovery MUST reidentify the target and inspect uncertain effects instead of blindly replaying unsealed steps.

**Verification:** Crash-at-every-transition model and target-swap tests.

## Related specifications

- [DE-042](planning.md)
- [DE-041](broker-and-authorization.md)
