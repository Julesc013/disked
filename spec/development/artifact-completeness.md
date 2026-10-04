---
type: DiskEd Specification
title: Artifact completeness and publication checks
description: Verify required content independently of archive integrity and distinguish historical audit claims.
resource: disked://spec/de-077
tags:
- disked
- development
generated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
status: draft
disked:
  id: DE-077
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-004
  - DE-060
  - DE-074
  requirements:
  - DE-REQ-077-01
  - DE-REQ-077-02
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Artifact completeness and publication checks

## Independent expected inventory

A matching checksum identifies bytes; a valid empty archive can still omit the entire product. The supplied audit reports such an earlier archive. That archive itself was not supplied to this task, so its size, contents and historical test counts remain attributed external claims, not newly reproduced results.

Before packaging, independently enumerate reviewed staging: required entrypoints, safe relative paths, regular-file types, byte sizes and content hashes. Refuse duplicate/case-colliding paths, traversal, absolute names and unapproved links. The final archive must match that nonempty expected inventory, not an inventory derived only from the archive being checked. Extract into disposable storage with containment checks and validate expected content before executing any explicitly approved entrypoint.

After an authorized publication, download and compare delivered bytes. Record staging identity, final archive and downloaded hashes, tool versions, actual commands and limitations. Keep completeness, integrity, authenticity, compatibility and runtime correctness separate. Local spec manifests enumerate source content; they are not signatures or proof that a separately packaged release contains it.

## Scope

Artifact-validator implementation and an empty-but-valid archive regression belong to the release-tooling work unit. The supplied claim of 15 archive-checker tests is not an executable checker in this repository. No such tests are reported as passed here. Product runtime and platform checks apply to the actual composed artifact once one exists.

## Normative requirements

### DE-REQ-077-01

Every distributed artifact MUST match an independently reviewed nonempty staging inventory with required entrypoints and safe unique paths.

**Verification:** Before release, test empty-but-valid, missing, extra, duplicate/case-colliding, traversal and changed-byte archives against the staging contract.

### DE-REQ-077-02

Publication evidence MUST distinguish local packaging checks, delivered-byte checks, authenticity and product qualification, and MUST report unexecuted checks as not run.

**Verification:** Review a release record with a missing download check or runtime evidence; no publication/runtime success may be inferred from checksum equality.
