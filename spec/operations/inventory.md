---
type: DiskEd Specification
title: Bounded native inventory
description: Independent operation contract for target.inventory.
resource: disked://spec/de-101
tags:
- disked
- operations
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-101
  profile: disked-spec/1
  version: 0.1.1-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-030
  - DE-042
  - DE-043
  - DE-044
  requirements:
  - DE-REQ-101-01
updated:
  by: codex
  at: '2026-10-09T22:55:35.310800+00:00'
  scope: DE-W030 private native volume namespace adapter; live/provider/physical/platform and owner qualification remain open
---

# Bounded native inventory

## Identity and availability

Semantic ID: `target.inventory`. Operation specification: `DE-OP-001`. Earliest phase: **M1/M3**. Initial target scope: fake targets first; later native NT read-only enumeration. Status: specified, not implemented or qualified. No availability is implied by the presence of this document.

## Required inputs and preconditions

An explicit scope identifies local host or image set. No automatic deep scan, media spin-up or elevation is implied. Read-only handles are requested; access denial is an observation, not an empty success. Inventory budget and cancellation policy are explicit.

## Planned procedure

Enumerate presentation paths; query bounded identity/capacity/sector observations; discover basic relationships; merge only identities supported by evidence. Preserve inaccessible resources and conflicting reports. Return a paged immutable snapshot with capture time and omissions. Never auto-select the first disk for a subsequent operation.

## Postconditions and evidence

No storage writes occurred. The graph identifies source provider and capture revision. Results distinguish unknown, denied, absent and present. A later mutation must freshly identify the selected resource.

## Interruption, cancellation and recovery

Cancellation can stop between bounded queries. Partial inventory is labeled partial. No journal is required for storage effects because no storage mutation is authorized; application output writes have ordinary file ownership rules.

## Required adversarial cases

Duplicate USB serials, cloned GUIDs, inaccessible volume, removed device, stale ordinal, sleeping media, enormous provider response and cancellation mid-enumeration.

## Normative requirements

### DE-REQ-101-01

`target.inventory` MUST enforce the preconditions, evidence and recovery limits in this operation contract before admission.

**Verification:** Duplicate USB serials, cloned GUIDs, inaccessible volume, removed device, stale ordinal, sleeping media, enormous provider response and cancellation mid-enumeration.

## Related specifications

- [DE-030](../storage/identity-and-graph.md)
- [DE-042](../safety/planning.md)
- [DE-043](../safety/journal-and-recovery.md)
- [DE-044](../safety/verification-and-performance.md)

## Private native volume namespace adapter

DE-W030 begins a bounded native Windows volume-namespace and selected mount-path
adapter under the [proposed private profile](../catalog/nt-volume-namespace-prototype.json).
Construction and product startup dispatch no query. Exact documented Win32 API
replies have fixed buffers, finite growth/count budgets, immediate error capture
and one search-handle close. Denied, removed, malformed, cancelled and uncertain
close results remain explicit alongside prior accepted observations. API counts
and byte limits do not establish a universal OS-call latency bound.

Names retain original UTF-16 code units separately from inert ASCII display.
Duplicate volume names and observed exact/ASCII-case mount conflicts are never
merged into physical media identity. Capacity, sectors, disks/layouts/backing
layers and complete alias proof remain unknown. This private component does not
admit target.inventory, alter the fake/ordinary-image product composition or
authorize device access. Actual live namespace, contained service, provider/graph
identity and XP/other-platform import/launch qualification remain open. Native
qualification injects Win32 replies and records that distinction.
