---
type: DiskEd Specification
title: Governance, review and change safety
description: Lean ownership with risk-scaled review rather than ceremonial committees.
resource: disked://spec/de-075
tags:
- disked
- development
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-075
  profile: disked-spec/1
  version: 0.1.0
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-070
  - DE-074
  requirements:
  - DE-REQ-075-01
  - DE-REQ-075-02
---

# Governance, review and change safety

## Roles

The owner sets product direction and accepts the initial baseline. Named subsystem maintainers review their actual modules. Independent storage-safety review is required before high-risk effects; do not claim a committee exists without people accepting that role. A solo maintainer can build and test on images, but cannot manufacture independent review by running a second prompt and naming it a council.

Use risk labels for routing, not a single linear safety score. Read-only parsers can be security-critical. Distinguish host privilege, data effect, target criticality, reversibility, concurrency and evidence requirements. Root instructions summarize hard limits; enforcement resides in sandbox/tool policy and release settings.

## Proposal to acceptance

A change names problem, user value, affected requirements, alternatives, threat-model delta, compatibility, migration and test/recovery plan. A bounded work unit implements only after prerequisites. Review checks diff and actual evidence. Acceptance binds content hashes and scope. Superseding a decision retains its history; do not silently mutate earlier accepted rationale.

## Autonomous workflow limits

Agents may inspect, propose and execute authorized fixture-only tasks. They stop at needs-review when asked, preserve unresolved blockers, and do not rewrite failing tests just to achieve a green status. They may propose a requirement correction when reality contradicts the design, but cannot reinterpret risk to expand privileges. Issued work grants specify allowed paths and forbidden operations; multiple concurrent workers use separate worktrees.

## Refactoring and retirement

Refactors preserve stable IDs, command semantics, public ABI and durable formats, or carry an explicit migration. Module paths are changeable. Remove dead duplication only after confirming no canonical information is lost. Generated files are regenerated, not edited. Deprecation has a successor, compatibility fixture and removal condition; "legacy" is not a catch-all folder for unowned code.

## Release gates

Separate a spec release, developer image build, public read-only preview, physical-write beta and production operation admission. Each has different evidence. No broad support badge is generated from a successful compile. Signing, security reporting and licensing must be real before public product distribution.

## Normative requirements

### DE-REQ-075-01

Acceptance MUST be content-bound and attributable; agents MUST NOT manufacture independent review or certification.

**Verification:** Review acceptance examples and reject missing reviewer/source digest.

### DE-REQ-075-02

Every change MUST identify scope, affected requirements and actual evidence or explicit blockers.

**Verification:** Validate a handoff/PR checklist and a deliberately incomplete record.

## Related specifications

- [DE-070](aide-integration.md)
- [DE-074](testing-and-ci.md)
