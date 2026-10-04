---
type: DiskEd Specification
title: Acquisition consistency and observation effects
description: Distinguish byte capture from point-in-time consistency and separately authorize destination effects.
resource: disked://spec/de-036
tags:
- disked
- storage
generated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
status: draft
disked:
  id: DE-036
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-031
  - DE-044
  requirements:
  - DE-REQ-036-01
  - DE-REQ-036-02
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Acquisition consistency and observation effects

## Consistency classes

Each acquisition reports `live-uncoordinated`, `offline-stable`, `snapshot-crash-consistent`, `application-consistent` or `unknown`. Record source identity/generation, capture interval, participating volumes, snapshot identity/lifetime, writer participation and outcomes, unreadable/substituted ranges, hash coverage and resume conditions. A hash over a changing source does not establish a point-in-time backup.

VSS coordinates requesters and application writers through the [documented Windows framework](https://learn.microsoft.com/en-us/windows/win32/vss/volume-shadow-copy-service-overview). A DiskEd VSS adapter remains unimplemented. A volume snapshot does not automatically include disk boot metadata or every volume used by an application. Failed/missing writers lower the stated consistency class; they are not ignored to report application-consistent success.

## Effects and resumption

Source-read authority, destination-write authority and any snapshot/quiescence side effects are distinct. Read-only intent is not physical write-blocker assurance: probing may spin media, move tape or invoke host services. No expensive or disruptive probe runs on bare launch.

Resume requires matching source epoch, snapshot lifetime where applicable, destination identity and acquisition map. If the original epoch is unavailable, start a separate capture or explicitly report a mixed/inconsistent result; do not combine later reads into a purported coherent original image. Unreadable data is not zero data. Record filesystem validation, restoration and boot tests separately, only when performed.

## Normative requirements

### DE-REQ-036-01

An acquisition MUST declare and substantiate its consistency class, participating volume/writer scope and resume epoch; byte hashes MUST NOT imply coherence or restore readiness.

**Verification:** Exercise changing-source, expired snapshot, missing writer and multi-volume mismatch fixtures and verify downgraded or refused claims.

### DE-REQ-036-02

Observation and acquisition MUST separately disclose source, destination and host side effects and their authority.

**Verification:** Trace bare launch and acquisition planning; no snapshot, self-test or destination overwrite occurs without the selected task and scope.
