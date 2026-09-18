---
type: DiskEd Specification
title: Filesystem-aware migration and representability
description: Independent operation contract for filesystem.migrate.plan.
resource: disked://spec/de-109
tags:
- disked
- operations
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-109
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
  - DE-REQ-109-01
---

# Filesystem-aware migration and representability

## Identity and availability

Semantic ID: `filesystem.migrate.plan`. Operation specification: `DE-OP-009`. Earliest phase: **M7+**. Initial target scope: source/destination filesystem profiles with exact metadata support. Status: specified, not implemented or qualified. No availability is implied by the presence of this document.

## Required inputs and preconditions

Capture filename/encoding rules, streams/forks, ACLs/xattrs, sparse/hardlink/reflink relationships, timestamps, special nodes and snapshot semantics. Destination capacity and collision rules must be known. Required credentials are references, not ordinary logs.

## Planned procedure

Generate a fidelity/loss report. Offer explicit normalization, metadata sidecar/containerization or refusal. Bind the chosen strategy and acknowledged losses into the plan. Copy through bounded providers; preserve object relationships and verify against selected fidelity goals.

## Postconditions and evidence

Content and all required representable metadata match. Lost/normalized/encapsulated classes are itemized with limitations. A successful byte copy alone does not establish semantic migration success.

## Interruption, cancellation and recovery

Resume needs stable source revision and object mapping. Source mutation during migration requires a snapshot or explicit consistency strategy. Rollback can mean abandoning the destination only while the source remains intact.

## Required adversarial cases

Case-fold name collisions, unsupported resource forks/ADS, lost hardlinks, changed source, ACL translation ambiguity, timestamp precision loss and encrypted per-file data.

## Normative requirements

### DE-REQ-109-01

`filesystem.migrate.plan` MUST enforce the preconditions, evidence and recovery limits in this operation contract before admission.

**Verification:** Case-fold name collisions, unsupported resource forks/ADS, lost hardlinks, changed source, ACL translation ambiguity, timestamp precision loss and encrypted per-file data.

## Related specifications

- [DE-030](../storage/identity-and-graph.md)
- [DE-042](../safety/planning.md)
- [DE-043](../safety/journal-and-recovery.md)
- [DE-044](../safety/verification-and-performance.md)
