---
type: DiskEd Specification
title: Storage graph, identity and leases
description: Layer-aware observations and live target revalidation.
resource: disked://spec/de-030
tags:
- disked
- storage
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-030
  profile: disked-spec/1
  version: 0.1.0
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-010
  - DE-005
  requirements:
  - DE-REQ-030-01
  - DE-REQ-030-02
  - DE-REQ-030-03
---

# Storage graph, identity and leases

## Resource model

The graph contains hosts, controllers, ports, physical media, presented devices, namespaces/LUNs, image chains, maps, extents, volumes, pools, arrays, encryption, filesystems, mounts, snapshots, boot dependencies and observations. Typed edges include contains, backs, maps, transforms, mirrors, mounts, depends-on, observed-as and conflicts-with. A topology graph may have sharing; only the action dependency graph must be acyclic. Avoid assuming every resource is a local block device.

Identity is composite evidence: protocol identifier, device descriptor, controller/path, serial where credible, capacity, sector sizes, namespace/LUN, map identifiers, selected object identifiers and current layout fingerprint. Duplicate cloned disk GUIDs and missing/faked USB serials must be representable. A signature or GUID is not sufficient by itself. Ordinals and paths are display/lookup hints.

## Leases and concurrency

A capture session yields an immutable graph and a revision fingerprint. A mutation lease binds the selected resources, expected generation and access mode. The broker reopens and recaptures after acquiring exclusive control and immediately before each step whose preconditions depend on mutable state. OS locks are real synchronization; a persisted JSON lease is not. Local unmounted state does not prove a shared SAN LUN is unused by another host.

Distinguish storage identity from observation identity and content digest. A hash detects metadata change but does not identify the physical enclosure. Preserve disagreement among OS API, raw parser and external tool rather than merging arbitrary fields into a fictitious object. Unsupported layers stop mutation of descendants whose semantics are uncertain.

## Graph updates

External changes invalidate affected plans. A successful earlier step yields a new expected intermediate state for subsequent steps; do not compare the whole disk forever against its pre-operation hash. Each step names the relevant pre/postconditions and its allowed changes. Recapture records unexpected writes as deviations requiring stop/recovery, not as harmless noise.

## Normative requirements

### DE-REQ-030-01

A destructive target MUST use composite identity and fresh state, never only disk number, path, letter or cloned GUID.

**Verification:** Reenumeration, duplicate-GUID and absent-serial negative tests.

### DE-REQ-030-02

Before each dependent effect, the broker MUST check the relevant expected intermediate state under appropriate access control.

**Verification:** Inject a layout change between plan and apply and between two steps.

### DE-REQ-030-03

Unknown or conflicting layers MUST remain visible and MUST block unsafe dependent mutation.

**Verification:** Supply disagreeing map providers and assert a typed refusal.

## Related specifications

- [DE-010](../architecture/system.md)
- [DE-005](../foundation/glossary.md)
