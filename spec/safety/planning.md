---
type: DiskEd Specification
title: Planner, action graph and simulation
description: Compile intents into explicit dependencies, resources and recovery obligations.
resource: disked://spec/de-042
tags:
- disked
- safety
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-042
  profile: disked-spec/1
  version: 0.1.3-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-030
  - DE-033
  - DE-041
  requirements:
  - DE-REQ-042-01
  - DE-REQ-042-02
  - DE-REQ-042-03
  - DE-REQ-042-04
updated:
  by: codex
  at: '2026-10-08T21:31:19.658481+00:00'
  scope: DE-W040 private immutable fake-model definition and receipt proposal; no production authority
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
- id: review-08a8246-2026-10-04
  resource: ../references/sources.json#review-08a8246-2026-10-04
---

# Planner, action graph and simulation

## Intent compilation

Capture immutable current graph; normalize intent; resolve target identity; project desired graph; calculate graph difference; enumerate candidate providers; derive an action DAG; analyze preconditions, transient states, capacity, locks, data fidelity, boot dependencies and recovery. Provider selection is visible and fixed in the plan. No provider can mutate while proposing what should happen.

A plan contains target and basis fingerprints, semantic steps, dependencies, pre/postconditions, provider IDs/versions, required critical features, permitted cancellation points, recovery class, resource estimates, loss-report digest and required acknowledgements. Hash a specified canonical encoding excluding the digest field itself. JSON key ordering, integer representation, unknown fields and Unicode must be specified before using interoperable signatures. The baseline JSON representation is a review format; cross-implementation cryptographic canonicalization requires its dedicated work unit.

## Ordering examples

Shrink-right generally shrinks and verifies the filesystem before reducing its container boundary. Grow-right generally extends the container before growing the filesystem. A start move requires relocation and dependent metadata/boot handling, not just an offset edit. Both orderings remain provider-specific under encryption, volume management and controller layers. Operations with dependency cycles are rejected and return a witness.

## Simulation levels

Static graph projection detects geometry and dependency errors. Provider dry-run can inspect native constraints but must be proven nonmutating. Image reproduction and copy-on-write overlays exercise richer behavior. None predicts arbitrary hardware failure or guarantees boot success. Report simulation coverage, unknowns and versioned assumptions instead of a binary "safe" badge.

## Retry and recovery

Idempotency keys apply only to a defined semantic scope and current state. A step is replayable only if its implementation demonstrates it. A plan cannot be treated as one global transaction if constituent providers have separate commit points. After partial failure, produce observed state and an admissible recovery plan, not a rewind of the UI queue.

## Execution dependency closure

Include executable and provider generations, scratch, journal, capsule, backups and required credential references in the plan's storage dependency analysis. Model their backing devices/failure domains, not just directories. Refuse an action that would destroy its only execution/recovery path or that lacks durable independent capacity where required. Temporary/volatile state is insufficient for a persistence requirement.

Quiescence, shared ownership, media-specific irreversible boundaries and capacity are fresh preconditions. Tape positioning, optical finalization and discard are not generic reversible block writes. Optional assistance may propose an intent but cannot waive these checks. The v1 JSON plan remains a review model; concrete production encoding and typed operation parameters must be extended and tested before their writers are admitted.

## Required evolution before executable plans

The v1 JSON schema remains a prototype review model. Its mutable `status` and supplied acknowledgements are not the final immutable plan ABI. Before signing/admitting real effects, separate PlanDefinition (immutable effects/constraints/required acknowledgements) from ReviewReceipt, Approval/Grant, attempt-specific AdmissionReceipt and ExecutionRecord. Those receipts bind an exact plan digest rather than rewriting plan bytes. DE-W040 and DE-DEC-008 gate production encoding; the first fake interface may continue to use clearly labeled review fixtures.

Before acquisition or multi-resource execution, bind **each** source, destination, scratch, journal, backup and executable/provider dependency by identity, expected epoch, access mode, effect footprint, aliases/failure domain and required verification. A step's free-form target ID or root fingerprint is insufficient for another resource. Source-read, destination-write and host/quiescence effects have separate authority. DE-W033 must extend typed operation parameters/resource fixtures before claiming coherent acquisition; writer work must complete these contracts before admission.

## DE-W040 private immutable-definition proposal

The native `source/runtime/journal/definitions.*` spike uses
[a private profile](../catalog/plan-prototype.json), separate from the v1 review
schema and from `disked.exe`. It has no target, file, authorization or effect
port. Its definitions and receipts copy validated values, retain exact canonical
bytes and expose only const access. Caller-owned input changes cannot change a
prepared definition or receipt. Supplied acknowledgements, status and execution
progress do not belong in definition bytes; their addition is rejected.

This restricted encoding is compact ASCII JSON with object keys sorted by byte,
no insignificant whitespace or trailing newline, and decimal u64 strings in
shortest form. Numbers, nulls, unknown fields and non-ASCII identifiers are
rejected. Identifiers use the profile's alphabet and are at most 128 bytes.
Resource/step/set arrays must already be sorted and unique; validation never
silently normalizes them. A payload is at most 65536 bytes, a definition at most
32 resources and 32 steps, and a receipt inspection at most 128 records.
Resource alias sets are limited to 16, failure-domain sets to 8, required/supplied
acknowledgement sets to 16, and per-step dependency/effect/reconstruction sets and
grant permissions/admission observations to 32 each. Other validity rules can
impose a smaller realizable set; for example, a valid DAG cannot depend on itself.
Epochs
and execution sequences are positive u64s. This is a fake-model encoding, not
the production canonicalization or signing decision DE-DEC-008.

Every resource declares an identity beginning `fake:`, identity/state digests,
expected epoch, purpose, access, half-open byte footprint, aliases, declared
failure domains, verification method and persistence requirement. Its identity
must occur in its sorted alias set. Alias sets are disjoint between resources;
the prototype refuses shared backing/aliases rather than claiming to resolve
them. Every declared resource must participate. Journal, provider and executable
resources are mandatory dependencies. The journal is persistent and writable;
code dependencies are persistent and read-only. These are fixture declarations,
not observations that prove storage independence or code admission.

Each `fake.range-transition` step names provider/executor resources, dependencies,
pre/postcondition digests and sorted resource effects. Effects may reference only
target/scratch resources; access and footprints must lie inside their resource
bindings. Observation effects have an empty footprint; reads/writes have nonempty
footprints. Read/observation before/after digests agree, and every step in this
mutation model has a write. Dependencies form a DAG or return a cycle witness.
Because state is represented by one digest per resource, conflicting effects on
the same resource must be ordered even when their extents do not overlap. Each
effect's before digest equals the latest ancestor write's after digest, or the
resource's initial state. Parallel extent reasoning is deferred.

Recovery declares independent replayability, resumability, rollback before/after
a boundary, external-backup dependence, checkpoint cancellation, irreversibility
after the step, forensic best effort and reconstruction resources. Irreversibility
after a step conflicts with rollback after that step. Declared rollback or backup
dependence requires retained reconstruction references: persistent, read-only
backup resources with stronger verification than identity/epoch alone. Written
resources must not share a declared failure domain with journal, code or any
reconstruction dependency. Conservative summaries use AND for replayability,
resumability and rollback, OR for backup/irreversibility/forensic properties, and
list cancellation checkpoints. No summary qualifies actual recovery.

Plan identity is SHA-256 of the complete canonical definition bytes. Resource
identity hashes the exact canonical resource array after the profile's
`DiskEd.plan.resources/1\n` prefix; provider closure similarly hashes the complete
executable/provider rows after `DiskEd.plan.providers/1\n`. A receipt's identity
hashes its complete canonical bytes. These domain prefixes contain an actual
line-feed byte. Changes to resource, code, policy, effects or required
acknowledgements change plan identity; receipts for another identity are refused.

Review, grant, admission and execution receipts remain separate immutable data.
Each binds the plan digest, issuer identifier and retained evidence digest.
Reviews select exact steps and a reviewed/rejected decision. Grants select steps,
the exact minimal resource permissions (including journal/code/backup reads or
writes), the complete required acknowledgement set and declared host effects.
Admissions bind reviewed/granted scope, policy and provider closure, exact initial
resource observations, operation/attempt/worker identities and a worker epoch.
Execution records bind that admission and worker generation, a selected step,
positive contiguous sequence in the attempt domain and a typed event. Intention
and verified-completion observation digests match the step's pre/postconditions;
cancellation/recovery observations carry separate nonzero digests.

Inspection requires referenced review/grant/admission receipts to precede their
users, rejects rejected review or missing host-effect authority declarations,
and prevents attempt identity reuse. Identical receipt identity/bytes is an
idempotent duplicate; reusing an identity for different bytes is rejected and
does not delete history. A new attempt has its own sequence starting at one.
Data matching does **not** authenticate an operator, establish an observation's
freshness, admit a writer, or prove intention durability/effect completion.
For example, matching a completion declaration does not establish a preceding
durable intention or a target flush. This inspector does not yet enforce those
event transitions.
The separate [closed guarded model](journal-and-recovery.md#de-w040-guarded-fake-memory-execution-contract)
now exercises state transitions under explicit fake flush/observation assumptions.
The separate [semantic binary reader](journal-and-recovery.md#de-w040-semantic-binary-journal-declaration-contract)
now binds these payloads to framing and checks event/recovery declarations. This
data inspector remains unauthenticated and gains no execution authority.
DE-DEC-004/008 and owner acceptance remain unresolved.

## Normative requirements

### DE-REQ-042-01

Planning MUST be side-effect free and produce an acyclic explicit action graph or a cycle witness.

**Verification:** Recording-provider test asserts no writes; cycle fixture verifies diagnostic.

### DE-REQ-042-02

Plans MUST bind exact inputs, providers, required critical features and intermediate pre/postconditions.

**Verification:** Alter each bound input and confirm apply refuses.

### DE-REQ-042-03

Simulation MUST describe its coverage and limitations; a graph-only simulation MUST NOT certify hardware safety.

**Verification:** Inspect reports for simulation type and absence of unsupported assurance claims.


### DE-REQ-042-04

Mutation admission MUST preserve a reachable execution/recovery dependency closure outside the affected scope and required failure domains.

**Verification:** Model formatting the executable volume, same-device backup, full journal space and volatile recovery state; refuse destructive dependency loss.

## Related specifications

- [DE-030](../storage/identity-and-graph.md)
- [DE-033](../storage/providers.md)
- [DE-041](broker-and-authorization.md)
