---
type: DiskEd Specification
title: Deployment effects and state ownership
description: Portable, user, machine and native-package modes declare effects and preservation separately.
resource: disked://spec/de-063
tags:
- disked
- delivery
generated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
status: draft
disked:
  id: DE-063
  profile: disked-spec/1
  version: 0.1.2-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-013
  - DE-061
  requirements:
  - DE-REQ-063-01
  - DE-REQ-063-02
updated:
  by: codex
  at: '2026-10-09T22:23:24.522988+00:00'
  scope: DE-W062 private servicing dependency preview; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Deployment effects and state ownership

## Profiles

| Profile | Permitted deployment effects | Removal |
|---|---|---|
| Run in place | No enrollment; explicit state/output roots | Remove chosen software; preserve case data. |
| Strict folder-portable | Owned files under declared roots only | Remove owned files; no external integrations to undo. |
| Registered portable | Portable root plus selected recorded shortcuts/associations | Servicing owner removes its integrations. |
| Per-user | Authorized user payload and user integration | User-scope owner. |
| Machine | Approved shared payload/integration | Machine-scope owner with separate authority. |
| Native package | Effects allowed by the package system | Native owner lifecycle. |

No undeclared deployment effects is the promise; no operating-system traces is not. Shortcuts outside the portable root survive deletion of that root unless explicitly removed. Software uninstall never reverses storage operations.

Resolve target-native folders instead of hardcoding a drive. Separate immutable versioned payload, user preferences, cache/log quotas, organization policy, provider stores, secrets and independently selected case/journal/recovery roots. Legacy profiles may need flat or short-name layouts. Read-only payloads cannot imply volatile recovery is acceptable.

PATH, associations, services, drivers, scheduled tasks and background updates are independent opt-in selections. Preserve foreign files and subsequent unrelated PATH/registration edits. A service account must not guess the interactive user. Installation scope neither grants nor removes storage authorization.

Modify changes selections; repair restores the recorded accepted set; update resolves an explicitly new compatible set while preserving exclusions and policy; recover reconciles interrupted software maintenance. Resetting personalization does not reset enforced policy. Active jobs and recovery-required generations interlock with every owner before retirement; unreachable is not permission to delete.

## Private servicing preview

The [servicing profile](../catalog/servicing-preview-prototype.json) describes
a generated ownership/capture review model, not installed-state discovery or
execution authority. Resource roots are disjoint relative fixture footprints;
each binds one owner, exact generation and digest. This spelling rule does not
establish real filesystem ownership or physical alias independence.

Requests bind observed ownership/capture epochs and exact affected resources.
Incomplete capture, stale operation observations or unreachable workers defer
all requested retirement because complete current scope is unknown. Active,
unresolved, uncertain, held or recovery-required dependencies retain their
exact generations. A cancellation request/acknowledgement is not release;
worker exit alone does not prove certain effects or discharged recovery.

Repair preserves accepted selections/exclusions and policy without adding GUI,
drivers or new integrations. Configuration, case, evidence, recovery and external
tools never acquire payload ownership. A withdrawal preview can propose new-use
denial for exact provider generations while retaining their required bytes; it
does not apply storage admission policy. Every outcome keeps lifecycle/storage
authority false and requires a live atomic recheck. Captured views, owner
transfer, authenticity, live generation leases and an actual servicing adapter
need separate implementation/qualification before endpoint use.

## Normative requirements

### DE-REQ-063-01

Every deployment profile MUST enumerate owned effects, scope and retention; strict portable mode MUST exclude persistent host integration and shared dependency installation.

**Verification:** Trace portable/user/machine fixture plans, foreign files, external shortcuts and opt-in PATH changes; reject effects outside the selected scope.

### DE-REQ-063-02

Repair/update/removal MUST preserve component selections, enforced policy, externally owned tools and storage recovery dependencies.

**Verification:** Repair a console-only installation without adding GUI/drivers; refuse or defer removal of an unreachable generation required for recovery.
