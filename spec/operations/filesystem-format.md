---
type: DiskEd Specification
title: Create a filesystem through an explicit format plan
description: Formatting is a separately admitted destructive operation with consumer compatibility and verification.
resource: disked://spec/de-113
tags:
- disked
- operations
generated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
status: draft
disked:
  id: DE-113
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-037
  - DE-042
  - DE-043
  - DE-044
  requirements:
  - DE-REQ-113-01
  - DE-REQ-113-02
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Create a filesystem through an explicit format plan

## Identity and scope

Semantic ID `filesystem.format.plan`; operation `DE-OP-013`. Earliest phase M5 on disposable images, followed only by separately authorized and qualified M6 lab profiles. Status: specified, not implemented. This command creates a proposed plan; application requires the existing content-bound admission path.

## Inputs and preconditions

Bind the selected filesystem container and its backing resources to fresh composite identity and geometry. Specify filesystem/version, exact required features, intended consumer/boot compatibility, allocation unit, label encoding, initialization/checking policy, discard/TRIM behavior and overwrite consequences. Report unsupported combinations; never silently substitute another format or allocation size. Partition creation, mounting, boot configuration and sanitization are distinct dependent operations.

Establish ownership/quiescence, source/destination alias and shared-resource checks, exact formatter/verifier identities, sufficient independent recovery resources and a reviewed data-loss acknowledgement. Formatting may destroy existing metadata and make recovery impossible; a saved partition table alone cannot roll it back.

## Effects, verification and interruption

Plan the provider's exact metadata/data initialization footprint and disclosure of discard, scan or overwrite effects. Quick format, full initialization, bad-area checking and sanitization are separate intentions. Do not label a format secure erase. The broker revalidates the container after locks and before effects. Preserve unrelated regions or explicitly bind wider provider authority.

Independent verification checks format identifiers, geometry, required features, metadata invariants and declared preservation. Mountability and bootability need separate consumer tests. On interruption retain uncertain/partial state and recovery guidance; no automatic repeat format. Cancellation is available only at provider-defined safe checkpoints, with actual completion/quiescence established.

## Normative requirements

### DE-REQ-113-01

Formatting MUST bind exact container identity, filesystem feature/consumer choices, effects and loss acknowledgement; unsupported options MUST NOT be silently replaced.

**Verification:** Image fixtures cover stale container, active consumer, unsupported allocation/features, source/recovery alias, provider substitution and out-of-footprint changes.

### DE-REQ-113-02

Formatting MUST NOT imply sanitization, rollback, mountability or bootability without separate evidence, and MUST retain uncertain interruption outcomes.

**Verification:** Exercise quick/full/discard distinctions, false formatter success, interrupted initialization and absent consumer tests; verify truthful results.
