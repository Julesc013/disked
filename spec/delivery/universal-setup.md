---
type: DiskEd Specification
title: Universal Setup boundary and installation modes
description: Setup owns software lifecycle; DiskEd owns storage operations.
resource: disked://spec/de-061
tags:
- disked
- delivery
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-061
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-060
  requirements:
  - DE-REQ-061-01
  - DE-REQ-061-02
sources:
- id: usk-policy
  resource: ../references/sources.json#usk-policy
- id: ulk-readme
  resource: ../references/sources.json#ulk-readme
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
---

# Universal Setup boundary and installation modes

## Separation

Universal Setup installs, verifies, repairs, moves and removes DiskEd's software payload. DiskEd interprets and transforms storage. Universal Launcher can discover and launch DiskEd but is not required to run it. Do not embed the full Setup engine into the DiskEd broker or maintain product-specific installer file lists that diverge from portable staging.

The preferred optional `setup` bundle contains the exact DiskEd portable payload plus its package contract. It can extract, manage a portable root, install per user or install system-wide where implemented. These are desired integration commands, not claims that the current upstream implements every mode. The observed Setup source contains restricted acceptance gates; DiskEd must honor the actual upstream contract rather than bypass them.

## Deployment scope

Unmanaged run-in-place writes no install record. Managed-portable uses an explicitly chosen root and owned state. Per-user installs only in authorized user scope. System-wide adds shared integration after elevation. The detailed strict/registered/native-package distinctions are owned by DE-063. Every mode keeps payload, configuration, evidence and recovery ownership distinct. Copying a portable binary does not authorize registry integration, PATH edits, services, file associations or network acquisition.

## Integration inputs

Supply product identity, target profile, signed payload tree, component/license closure, state-root policy, optional shortcuts and associations, upgrade/migration compatibility and uninstall retention. Setup returns its own plan, verification and lifecycle evidence. Storage journal/evidence remains DiskEd-owned. An update package must not import a new storage-provider authority without that provider's admission.

## Exact upstream work

A dedicated work unit pins Universal Setup and Launcher revisions, reads exported headers/schemas and maps the product package. It must test extraction equality, user/system scope, occupied-root refusal, rollback boundaries and preserved customer data. No blind dependency on sibling worktrees or hardcoded absolute paths is allowed. Host toolchain support is verified for each setup asset; an XP disked binary does not automatically imply modern Setup runs on XP.

## Embedded host and consumer boundary

Inactive H inside D is permitted by [DE-060](composition.md), without granting the storage broker software-lifecycle authority. Explicit setup inspection/maintenance follows the shared lifecycle interface and a separately authorized owner. The actual upstream consumer kit must be pinned and read before use; the supplied reports of SDK targets and later dev behavior are inherited leads, not current consumer qualification.

DiskEd owns product selection, storage semantics and active-operation dependency reports. Universal Setup owns generic software lifecycle as qualified; MSI/MSIX owners retain their resources. [Deployment profiles](deployment-profiles.md), [acquisition policy](component-acquisition.md) and [channels](channels-and-servicing.md) define DiskEd's requirements without forking upstream schemas. No other repository is changed by this task.

Maintenance distinguishes pause requested, checkpoint reached, resources released, recovery still dependent and unknown/unreachable. It cannot treat unreachable as quiescent. Retain exact generations or defer. Generic upstream gaps become consumer test requirements for DE-W060/062, not a private fallback installer.

## Normative requirements

### DE-REQ-061-01

Setup MUST consume the authoritative portable payload and MUST NOT own or execute DiskEd storage transformations.

**Verification:** Integration boundary test and byte-equality verification.

### DE-REQ-061-02

Each lifecycle mode MUST be qualified against the pinned upstream implementation; planned modes MUST be reported as unavailable.

**Verification:** Exercise occupied-root, scope and unsupported-runtime refusals.

## Related specifications

- [DE-060](composition.md)
