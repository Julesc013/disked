---
type: DiskEd Specification
title: Sanitize, firmware and advanced administration
description: Independent operation contract for media.destructive.plan.
resource: disked://spec/de-112
tags:
- disked
- operations
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-112
  profile: disked-spec/1
  version: 0.1.0
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-030
  - DE-042
  - DE-043
  - DE-044
  requirements:
  - DE-REQ-112-01
---

# Sanitize, firmware and advanced administration

## Identity and availability

Semantic ID: `media.destructive.plan`. Operation specification: `DE-OP-012`. Earliest phase: **M8 separate admission**. Initial target scope: future narrowly qualified device/vendor profiles only. Status: specified, not implemented or qualified. No availability is implied by the presence of this document.

## Required inputs and preconditions

Distinct operation identity for sanitize, secure erase, overwrite, crypto-erasure and firmware changes. Exact device/vendor support, authorization, power and recovery assumptions, retention policy and collateral impact must be known. No implementation exists in the initial program.

## Planned procedure

Use documented native/vendor facilities through explicitly admitted providers. Display irreversibility and affected resources, including namespaces/pools. Record the command/firmware identity and status. Sanitization claims require a chosen standard, method and verified evidence; deletion/format is not sanitization.

## Postconditions and evidence

Postconditions are method-specific and independently measured where possible. Firmware version/device availability and sanitize status are retained. Inability to verify becomes an explicit limit, not a claim of complete erasure.

## Interruption, cancellation and recovery

Many operations are irreversible and may render hardware unusable on interruption. A journal cannot recover erased keys or broken firmware; refusing unsupported recovery is preferable to inventing a guarantee.

## Required adversarial cases

Wrong namespace, vendor mismatch, power loss, fake sanitize success, blocked secure state, shared-array collateral effects and ordinary format mislabeled secure erase.

## Normative requirements

### DE-REQ-112-01

`media.destructive.plan` MUST enforce the preconditions, evidence and recovery limits in this operation contract before admission.

**Verification:** Wrong namespace, vendor mismatch, power loss, fake sanitize success, blocked secure state, shared-array collateral effects and ordinary format mislabeled secure erase.

## Related specifications

- [DE-030](../storage/identity-and-graph.md)
- [DE-042](../safety/planning.md)
- [DE-043](../safety/journal-and-recovery.md)
- [DE-044](../safety/verification-and-performance.md)
