---
type: DiskEd Specification
title: Filesystem features and media capabilities
description: Qualify each operation against exact format features, consumers and address-space semantics.
resource: disked://spec/de-037
tags:
- disked
- storage
generated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
status: draft
disked:
  id: DE-037
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-031
  - DE-035
  requirements:
  - DE-REQ-037-01
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Filesystem features and media capabilities

## Capability predicates

Support is a tuple of operation, format/version/features, medium, access path, provider, host, consumer compatibility, current state and evidence. Recognition, inspection, extraction, creation, check, repair, grow, shrink, move, mount and boot are distinct. A formatter does not install a filesystem driver or make the host able to mount its output.

Feature predicates record required/forbidden/unknown critical bits, sector and allocation-unit constraints, addressing ceiling, encryption/compression state and online/offline restrictions. Unknown critical features block mutation. Preserve arbitrary file contents opaquely unless a chosen operation requires content interpretation. Migration reports unrepresentable names, streams, ACLs, links and other metadata.

## Domain boundaries

Random-access byte sources, block devices, filesystem trees, sequential records, objects and device-control services expose different interfaces. Tape uses position/filemarks/records; optical media uses tracks/sessions/finalization; flux uses timings; zoned media uses zone/write-pointer constraints. None inherits ordinary partition writes by naming itself a drive.

Table conversion, filesystem conversion, image-container conversion, encryption transitions and pool reorganization require separate selected operation contracts. The future destructive-administration umbrella is routing only, not one unrestricted executor. Add concrete tape, optical, mounting and repair contracts with their implementation work and fault model, not as empty support badges.

## Normative requirements

### DE-REQ-037-01

Every filesystem/media capability MUST bind exact operation and feature predicates; recognition, creation, mounting and bootability MUST be reported independently.

**Verification:** Present known format with an unknown critical feature, a tape target and a consumer-incompatible format request; refuse the affected action without hiding inspection.
