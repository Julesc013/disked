---
type: DiskEd Specification
title: Provider packages and acquisition policy
description: Separate implementation choice, version selection, source location, ownership and storage admission.
resource: disked://spec/de-064
tags:
- disked
- delivery
generated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
status: draft
disked:
  id: DE-064
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-033
  - DE-061
  - DE-062
  requirements:
  - DE-REQ-064-01
  - DE-REQ-064-02
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Provider packages and acquisition policy

## Resolution before storage review

Provider forms include built-in modules, OS facilities, exact existing installations, adjacent portable packs, user or machine packages, and separately qualified offline/remote executors. Detected, installed, trusted, qualified, admitted and authorized are different states. An existing tool remains externally owned unless an explicit transfer is accepted.

Version selection is bundled-exact, explicit lock or latest-admitted-compatible under an approved policy. Source location is a separate choice: embedded payload, adjacent package, verified cache, local installation, offline mirror or approved repository. Resolve the complete set and display dependencies, conflicts, provenance, licenses, runtime floors, resource needs, extraction and effects before software changes.

Generic acquisition and lifecycle belong to a pinned qualified Universal Setup consumer contract, not a new DiskEd downloader/installer. Offline policy must return an explicit missing-source result; it cannot silently use the network or weaken verification for old hosts. Prepare offline layouts on a qualified coordinator where needed. Upstream requested features remain consumer requirements until independently demonstrated.

## Admission and retirement

Package installation does not qualify a writer. Storage planning binds exact provider code and evidence after package resolution. No automatic acquisition, PATH discovery or provider substitution occurs in the privileged storage path. A withdrawn provider is denied for new work while exact recovery-required generations are retained under a separately reviewed recovery policy; deletion is not a safe response to unresolved effects.

## Normative requirements

### DE-REQ-064-01

Provider acquisition MUST occur through separately authorized software lifecycle before storage-plan admission, with exact version/source/owner identities.

**Verification:** Exercise missing offline source, pre-existing external tool and changed provider lock; no implicit network access, ownership takeover or storage execution.

### DE-REQ-064-02

Provider withdrawal MUST block new admission without silently deleting the exact closure required by active or uncertain operations.

**Verification:** Revoke a fake provider during unresolved work and verify new-use refusal plus retained recovery material.
