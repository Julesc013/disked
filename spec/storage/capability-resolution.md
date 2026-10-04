---
type: DiskEd Specification
title: Explainable capability resolution
description: Keep implementation, qualification, permissions, freshness and resource eligibility independent.
resource: disked://spec/de-035
tags:
- disked
- storage
generated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
status: draft
disked:
  id: DE-035
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-030
  - DE-033
  requirements:
  - DE-REQ-035-01
  - DE-REQ-035-02
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Explainable capability resolution

## Independent dimensions

Represent, discover, identify, inspect, validate, plan, simulate, execute, verify and recover are separate capabilities, not a monotonic score. Qualification is evidence for a defined claim, never a runtime stage called certification. Track implementation presence, provider identity, host/media compatibility, feature predicates, permissions, policy, freshness, target state, recovery availability and resource sufficiency independently.

`schemas/capability-assessment.schema.json` defines a conservative assessment: operation, target, snapshot, exact provider reference, checks, blockers, alternatives and execution eligibility. Unknown is not eligible. This is an explanation snapshot, not an authorization token; fresh admission checks still precede effects. Model presence without recognition or mutation support explicitly.

## Selection

Filter hard constraints first; among eligible providers compare evidence, preservation, recovery and resources before performance or preference. Built-in, OS-native, exact existing tools, adjacent/user/machine packages and offline/remote executors are candidates only where qualified. No PATH-first privileged selection, silent provider substitution, automatic driver installation or weakened recovery fallback.

Present available inspection and planning while execution is unavailable. A denied device remains visible with permitted metadata; do not label the inventory empty. Alternatives explain which condition would need to change and never assert that a missing permission or offline environment has already been obtained.

## Normative requirements

### DE-REQ-035-01

Execution eligibility MUST require every mandatory capability dimension to be satisfied; unknown, denied or unqualified state MUST remain explicit.

**Verification:** Reject an executable assessment with one unknown/failed check; preserve denied and stale fake targets alongside successful observations.

### DE-REQ-035-02

Provider selection and alternatives MUST be visible, operation-specific and fixed in the reviewed plan; changing a provider requires renewed admission.

**Verification:** Compare CLI/TUI/GUI capability explanations and reject a provider replacement after review.
