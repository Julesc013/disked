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
  version: 0.1.5-proposed.2
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
  at: '2026-10-10T02:33:32.351711+00:00'
  scope: DE-W030 shared owned observation host, storage receipt reader and startup
    reconciliation; live/product/provider/platform and owner admission remain open
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

## Contained private namespace observation

The [private observer profile](../catalog/nt-namespace-worker-prototype.json)
adds same-file process containment under injected API ports only. Reuse strong
code-parent pins, current-user object security, exact executable identity,
finite aggregate/local worker budgets and explicit inherited mapping/event
capabilities. Bind capture/observer/worker/attempt identities to immutable input
and one bounded publication. Refuse stale/malformed replies and unsupported
authority claims. Any native pointer in the supplied table, including a mixed table, is rejected
before dispatch here. Only the exact compiled fixture factory is qualified;
pointer checks do not qualify arbitrary wrapper behavior.

Finite waits retain the original attempt; they do not restart or imply exit.
Cancellation requests and collector checkpoint decisions are separate. A complete
snapshot can precede process exit. Explicit retirement or disconnect can stop
only this owned injected reader job, which has no storage effect port; without a
valid reply the capture remains unknown. This rule cannot authorize writer
termination, cleanup or replay. A temporary session does not claim durable
reconnect. Actual live namespace, physical identity/topology, graph/provider/
product admission and historical/other-platform qualification remain open.

## Private namespace graph projection

The [DE-030 observation profile](../storage/identity-and-graph.md#private-namespace-observation-profile)
projects conforming injected namespace frames into the existing graph with
source/epoch/context/frame-bound observation identities and explicit unknown
physical identity. The shared snapshot validator enforces exact selected policy,
lossless name/display agreement, count/status/claim relationships, and the
minimum MULTI_SZ units represented by observed paths. A pure projection is data
validation; only the owned adapter supplies verified worker binding and actual
exit evidence. Partial rows, cached complete rows, denial and complete-empty
inventory remain distinct. Generated native fixtures qualify that boundary;
product `target.inventory`, live namespace and physical topology admission remain
separate deliverables of DE-W030.

The selected [borrowed-handle metadata query profile](../catalog/nt-storage-observation-prototype.json)
additionally captures descriptor strings, transient device numbers, independent
geometry/length and volume extents under injected ports. It retains conflicting
components and candidate topology without physical-media admission. Its immutable
private frame has a bounded producer-conformance reader for the owned fixture
host; it is not a public protocol or proof of provenance. A complete
selected-query set does not establish complete inventory, atomic freshness or
worker exit. Actual owned-reader/public-service integration remains required.

Owned injected metadata publication must keep the capture outstanding until
actual owned reader exit. Prepare the session before capture registration/launch,
retain post-spawn failures and reconcile that exact process before replacement.
Never-launched failure is explicitly distinct from exit. Pure receipt decoding
must not repeat provider queries or reinterpret a completed metadata frame as
complete physical identity. Public/live/provider/platform admission is separate.
