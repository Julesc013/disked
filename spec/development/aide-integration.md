---
type: DiskEd Specification
title: AIDE integration without a second control plane
description: Bounded work, real evidence and projections over pinned upstream contracts.
resource: disked://spec/de-070
tags:
- disked
- development
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-070
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-002
  - DE-004
  requirements:
  - DE-REQ-070-01
  - DE-REQ-070-02
  - DE-REQ-070-03
sources:
- id: aide-readme
  resource: ../references/sources.json#aide-readme
- id: aide-workunit
  resource: ../references/sources.json#aide-workunit
- id: aide-okf
  resource: ../references/sources.json#aide-okf
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
---

# AIDE integration without a second control plane

## AIDE relationship

AIDE is a repository development control plane, not a library in DiskEd's runtime. At the current pinned dev revision, its README reports implemented local foundations while retaining separate runtime, isolation and stable-distribution gates; historical main-only descriptions must not be treated as current dev status. Use the actual WorkUnit shape inspected from that revision. Do not fabricate `aide run-all`, an autonomous scheduler, or a certification service.

This bundle keeps canonical planned work in `work/units.json`. `specctl aide-export` produces AIDE WorkUnit queue-shaped objects using the inspected fields, with `authorizes_implementation: false`, `status: planned`, `result: NOT_RUN` and real scope restrictions. The exporter is a mapping utility, not a claim of live AIDE admission or execution. Its schema projection and upstream revision are recorded. Full upstream CLI round-trip remains a qualification task.

## Development chain

A request becomes a bounded work definition. A grant binds the exact code/spec revision, allowed paths, actions, budgets and privileges. A worker attempts the task in an isolated worktree. Tests run independently and record actual commands/environment/results. A reviewer evaluates the patch, evidence and specification delta. Acceptance occurs only against exact content. A subsequent knowledge projection summarizes the result; it cannot accept its own source.

Suggested durable records are WorkUnit, WorkerRun, TestJob, EvidencePacket, EventRecord, ReferenceID and ContextPack. DiskEd-local extensions use their own schema namespace until an upstream contract accepts them. Do not populate `.aide/` with files falsely claiming an upstream schema that was not checked. The bootstrap integration file explicitly declares observed compatibility and unverified runtime behavior.

## Authority and automation

Read-only review may run automatically within a given workspace permission. Code edits require a grant; protected-path, release, hardware and signing operations remain separate. A task cannot approve its own evidence or rewrite the tests to make a failure disappear. Structured metadata is useful but not enforcement: OS sandboxing, tool ACLs, branch rules and review provide the boundary.

Model choice, reasoning level, provider generation, token budget and execution permissions are separate controls. AIDE may route subtasks economically only under authorized constraints and demonstrated quality. Do not assume a smaller subagent reduces cost after context duplication; record actual usage where available. No provider name or model tier is embedded in product semantics.

## Pinned dev refresh policy

The user requested AIDE dev at `5be37bd6510977e6cb2e960859c45b33b048dade`. It was fetched into ignored `.aide-local/upstream/aide` as a detached checkout; branch dev matched that identity when checked. `references/aide-lock.json` records upstream tree and inspected-file hashes. No upstream script, worker, scheduler, install/import lifecycle or external write is run by fetching source.

The current README reports repo-native and Windows lifecycle/runtime foundations in dev, while stable integrated/delivered-artifact, restricted-principal and model-enabled qualification remain gated. Its queue WorkUnit schema is unchanged from the prior pin. Source/schema inspection and passive local schema validation are narrower than live consumer installation or runtime interoperability; DE-W061 and DE-DEC-007 remain open for those claims.

Review upstream roughly every seven days until an explicitly stable, qualified release is selected. Next review target: 2026-10-11, Australia/Sydney; no unattended task is installed. Fetch/read a candidate into ignored storage, retain old and candidate identities, inspect release notes and changed contracts/security limits, validate exports against the exact schema, run authorized consumer checks, and update lock/source records in one reviewable change. Never float the accepted pin or execute a mutable dev checkout automatically. Stable promotion requires an exact release identity and applicable evidence, not a branch name.

## Normative requirements

### DE-REQ-070-01

AIDE exports MUST identify the pinned source shape and MUST NOT grant execution authority or fabricate passed work.

**Verification:** Inspect every exported record for planned/NOT_RUN/false authorization.

### DE-REQ-070-02

Agent execution privileges and model/budget choices MUST remain separate explicit controls.

**Verification:** Review grant schema and deny prohibited command/path/hardware operations.

### DE-REQ-070-03

Generated OKF knowledge MUST reference canonical specs/evidence and MUST NOT become a competing acceptance authority.

**Verification:** Change source spec and require knowledge freshness invalidation.

## Related specifications

- [DE-002](../foundation/authority.md)
- [DE-004](../foundation/requirements-and-traceability.md)
