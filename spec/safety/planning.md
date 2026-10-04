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
  version: 0.1.1-proposed.2
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
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
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
