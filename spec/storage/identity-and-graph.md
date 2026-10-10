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
  at: '2026-10-10T00:55:32.207261+00:00'
status: draft
disked:
  id: DE-030
  profile: disked-spec/1
  version: 0.1.2-proposed.2
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
  - DE-REQ-030-04
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: DE-W030 private namespace observation graph; live/product/provider/platform and owner qualification remain open
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
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

## Aliases, footprints and shared ownership

Preserve alias sets, media generations and address-translation provenance across physical paths, mounts, image files/backing chains, hypervisor attachments and shared LUNs. An effect footprint names all affected ranges/metadata/resources. Detect source/destination self-alias, an image stored on its own destination, overlapping jobs and destroyed recovery dependencies before admission.

Before shared or remote mutation, establish host/controller identity, delegated role and applicable reservation/fencing/quiescence through a qualified provider. Persisted leases and local mutexes are not fencing. Expired or superseded ownership prevents new effects; uncertain in-flight work follows its recovery contract. Reconnection binds the same host/job/target, never substitutes a reachable local disk. Shared mutation remains later separately granted work.

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


### DE-REQ-030-04

Plans MUST account for storage aliases, dependent resources and conflicting actors; unresolved ownership or aliasing MUST block the affected mutation.

**Verification:** Use multipath, attached-image, same-device recovery and shared-LUN fixtures; a second path or partition must not be mistaken for independent ownership or backup.

## Related specifications

- [DE-010](../architecture/system.md)
- [DE-005](../foundation/glossary.md)

## Native fake graph slice

DE-W013 exercises immutable captures, identity/generation-bound selection,
cloned aliases, shared resources, cycles and partial observations under the
private [DE-023 execution contract](../interaction/presentation.md). Revision
digests bind capture identity and exact observations. This is an in-memory
fake provider, not physical identity validation, leases, fencing or media
qualification. Real providers must earn their own identity/freshness claims.

## Private namespace observation profile

DE-W030 uses the same immutable graph and capture coordinator with an explicitly
selected private `Observations` profile. A namespace volume record and each mount
path are separate observation nodes; only observed volume-to-mount edges are
produced. Equal GUIDs, paths or case-folded lookup keys never merge nodes or imply
physical backing, capacity, exclusive ownership or complete topology.

Each observation ID is the SHA-256 of the exact canonical private JSON containing
its source, numeric capture/worker epochs, owned worker-context digest, complete
frame digest, node kind, escaped label and payload. The payload retains exact
UTF-16LE code-unit bytes and separate ASCII display escapes, record ordinals,
provider observation ID, conflict/status fields and owned worker context. That
context binds attempt/observer/native worker identities, request and executable
digests, process ID and creation identity. These IDs name evidence, not media.
Staleness is a view property and does not rename the original observation.

Observation properties have null media identity/generation/capacity, empty media
aliases, unknown physical identity, and false physical admission and mutation
authority. Current observations have `state: unknown` and
`freshness: current_observation`; cached observations have `state: stale` and
`freshness: cached`. Display freshness does not establish a physical identity.
The coordinator requires current nodes to belong to the exact source/capture/
worker key. Earlier epochs are allowed only as explicitly stale cached content
from an earlier worker. Observation IDs do not consume lifetime media-identity
tombstones. Existing fake media identity checks remain in force.

This private aggregate is limited to 320 nodes, 512 edges, 64 omissions,
786,432 serialized bytes and 32,768 JSON values; its capture coordinator reserves
8,192 bytes for source notices, allowing at most 778,240 graph bytes and 48
source-supplied omissions. Per-observation hash input is limited to 16,384 bytes,
1,024 values and depth 16. At most eight sources and eight retained notices remain
unchanged. The fake profile retains its existing smaller limits and exact output.
These are selected fixture limits, not a universal target profile or public ABI.

The native adapter retains at most the last complete namespace frame. A partial
or cancelled frame publishes its observed rows plus that complete frame marked
stale; repeated partial frames do not recursively grow the cache. Denial,
unavailability or invalid input retains prior visible content as stale. A complete
empty frame removes only this source's observations. Publication never retires
the worker: the owned reader's exact observed exit is required. Superseded frames
cannot publish into a later capture. Validation and allocating work precede
atomic publication; failed preparation cannot change an existing view.

The private producer and native fixture executable are separate from the product
composition. Existing `FrontendSession` rejects this profile pending explicit
observation selection, responsiveness and resource qualification. Native physical
identity/topology, live dispatch, frontend/product/provider admission and other
host/platform qualification remain required work; pure projection validates data
but does not authenticate a producer or prove process exit.
