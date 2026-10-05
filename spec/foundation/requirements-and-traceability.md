---
type: DiskEd Specification
title: Requirements and traceability
description: Stable requirement IDs connect decisions, implementation units, test procedures and evidence.
resource: disked://spec/de-004
tags:
- disked
- foundation
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-004
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-003
  requirements:
  - DE-REQ-004-01
  - DE-REQ-004-02
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Requirements and traceability

## Trace model

Each normative requirement has an ID, owning concept, statement, verification procedure, planned test IDs and an explicit boundary to implementation evidence. `catalog/requirements.json` and `catalog/tests.json` are generated projections from authored requirement sections. Their existence is traceability, not proof that the tests are implemented. Generated tests are `definition_only`; requirements say `evidence_owned_elsewhere`. Actual run, implementation and admission records live in the evidence plane and are joined by IDs. Regenerating the specification must never reset or manufacture an executed result. The baseline has a bounded DE-W010 native prototype; its separate evidence does not qualify the product or hardware.

Use MUST/MUST NOT for release-blocking constraints, SHOULD for defaults with documented exceptions, and MAY for allowed alternatives. Each requirement needs an observable outcome or a concrete inspection procedure. Replace adjectives such as perfect, military-grade, timeless and future-proof with measurable interfaces, failure handling, retained compatibility and migration behavior.

## Relationships

A requirement may be satisfied by multiple modules and tests. A test can verify multiple requirements only when its assertions actually cover them. An implementation work unit references source requirement IDs. A result binds the work unit, code revision, target profile, test command, environment, artifacts and limitations. Distinguish test design, executed test, passed result, independent review, admission and release qualification.

Acceptance requires evaluating applicable negative cases, not just demonstrating the happy path. Reused evidence must bind input hashes, toolchain, relevant implementation closure and policy; fresh hardware state and target identity are never satisfied from stale cache. Required tests cannot be marked skipped-as-pass.

## Change handling

Additive clarification retains the requirement ID with a revised owning document. A semantic replacement creates a new requirement and an explicit supersedes edge. Removing a feature records retirement and migration. The impact tool maps changed specification or code paths to affected concepts, work units and planned tests; it is conservative routing, not a substitute for reviewer judgment.

## Release statement

Publish three separate fields: designed, implemented, and qualified. A profile can compile but remain unqualified; an image-only provider can pass all image tests but lack physical-write admission. Required coverage percentages are not meaningful unless the denominator, target and evidence scope are specified.

## Independent evidence axes

Represent buildability, binary launch compatibility, semantic conformance, VM results, hardware/recovery qualification, channel eligibility and vendor support lifecycle separately. A successful reader does not qualify its writer; a compiled legacy build does not establish modern isolation. Public support is a join over the exact artifact, operation/provider, environment and evidence, not a hand-edited supported boolean.

The supplied acceptance designs are mapped into `catalog/amendments.json` and authored requirement procedures. They remain definitions with no product evidence. Historical audit results remain attributed claims; this amendment's own tool logs are retained separately.

## Normative requirements

### DE-REQ-004-01

Every normative requirement MUST map to at least one explicit verification procedure and planned test ID.

**Verification:** Validator rejects a requirement lacking a test reference.

### DE-REQ-004-02

Evidence reuse MUST bind relevant content hashes and scope; absent or skipped evidence MUST NOT count as a pass.

**Verification:** Invalidate a changed dependency fixture and verify qualification is withheld.

## Related specifications

- [DE-003](okf-profile.md)
