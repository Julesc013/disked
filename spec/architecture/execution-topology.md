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
  version: 0.1.1-proposed.2
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
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Essential startup and execution roles

## Essential, inspection and execution tiers

Essential startup exposes build/help/command information, policy explanations and explicit local saved-report inspection before any device probe. It requires no elevation, network, optional provider or Setup extraction. Corrupt personalization may be bypassed with a diagnostic; enforced policy must remain effective, or effects requiring that policy are unavailable.

Inspection publishes incremental identity-bound observations, with denied, stale, incomplete and failed contributions retained. Expensive scans, tape movement, snapshots and device self-tests are explicit tasks. Execution adds reviewed plans, authority, recovery resources and verification; it is not implied by opening a view.

## Roles and boundaries

Coordinator, observer, planner, executor, verifier and recovery executor are logical roles. Their record binds host identity, target profile, provider closure and resources. A local fake session may use one process. On a qualified host, another instance of the same executable may isolate a probe or execute an admitted job. A process boundary is not automatically a security boundary; retain actual enforcement limits.

The frontend can disconnect while the job remains identified. Role recovery does not mean restarting an uncertain writer. A cross-boot or remote executor independently validates the same target, plan version and bounded supported operations. The first broker is local-only. Neither an SDK nor installation enables a remote listener.

An independent storage recovery path must work without the normal GUI, optional discovery pipeline or network. Software repair uses the servicing owner's independent payload and journal, separate from storage recovery. Targets lacking process protection publish a constrained profile rather than inheriting NT containment claims.

## Normative requirements

### DE-REQ-015-01

Essential startup MUST run without opening devices, fetching dependencies, extracting Setup or requesting elevation.

**Verification:** Trace fake startup with absent providers, corrupt optional settings and offline networking; help/build/command discovery must remain available.

### DE-REQ-015-02

Every executor/verifier/recovery role MUST bind its execution host and supported plan subset; loss of a remote target MUST NOT redirect to local storage.

**Verification:** Reconnect and cross-boot fake transcripts with host mismatch, unknown required features and missing remote target; require explicit refusal.
