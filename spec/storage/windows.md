---
type: DiskEd Specification
title: Windows NT provider strategy
description: Windows-native depth without treating storage restrictions as bypass
  targets.
resource: disked://spec/de-034
tags:
- disked
- storage
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-034
  profile: disked-spec/1
  version: 0.1.7-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-033
  - DE-032
  requirements:
  - DE-REQ-034-01
  - DE-REQ-034-02
sources:
- id: windows-ns-winioctl-storage_device_descriptor
  resource: ../references/sources.json#windows-ns-winioctl-storage_device_descriptor
- id: windows-ni-winioctl-ioctl_storage_get_device_number
  resource: ../references/sources.json#windows-ni-winioctl-ioctl_storage_get_device_number
- id: windows-ns-winioctl-volume_disk_extents
  resource: ../references/sources.json#windows-ns-winioctl-volume_disk_extents
- id: windows-shrink
  resource: ../references/sources.json#windows-shrink
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
- id: windows-identity-device-identifiers
  resource: ../references/sources.json#windows-identity-device-identifiers
- id: windows-identity-storage-identifier
  resource: ../references/sources.json#windows-identity-storage-identifier
- id: windows-identity-access-alignment
  resource: ../references/sources.json#windows-identity-access-alignment
- id: windows-identity-drive-layout
  resource: ../references/sources.json#windows-identity-drive-layout
- id: windows-identity-partition-info
  resource: ../references/sources.json#windows-identity-partition-info
- id: windows-identity-layout-query
  resource: ../references/sources.json#windows-identity-layout-query
updated:
  by: codex
  at: '2026-10-10T04:12:34.693618+00:00'
  scope: DE-W030 private device-ID/alignment/OS-layout query contract; integration/live/identity/owner
    admission remains open
---

# Windows NT provider strategy

## Discovery first

Use documented Win32 handles, storage-property queries, volume APIs and disk-layout IOCTLs, with runtime capabilities determined per exact OS/API/provider. Modern Storage Management can enrich topology but must not become an XP-wide assumption. VDS is a separate optional legacy provider. Record native and independently decoded metadata without flattening partitions, volumes, disks, VHDs, pools and encryption into one object.

## Operation selection

Prefer a qualified native online operation. Otherwise offer a qualified Windows-hosted external provider, a native offline recovery operation, a foreign recovery provider, or image-first workflow. An unsafe active-volume move remains offline; it is not solved by administrator elevation or a new driver. Non-system drive letters do not prove quiescence: page files, open handles, filter drivers and remote users still matter.

Partition layout IOCTLs update metadata, not filesystem contents. Microsoft documents `FSCTL_SHRINK_VOLUME` from Vista with NTFS/RAW support and a multi-step allocation-handling workflow. The XP profile therefore cannot simply reuse that call.[^windows-shrink] The implementation must independently establish availability, filesystem state, lock semantics and postconditions for each API.

## Windows-specific layers

Prioritize NTFS/FAT/exFAT, mount-manager identity, VHD/VHDX, boot/BCD/ESP/MSR/WinRE and BitLocker-aware inspection. Later plans include Storage Spaces, LDM, ReFS and VSS coordination. Unlocking encryption, suspending protectors and moving encrypted content are distinct operations. Do not log keys or assume a volume copy repairs boot measurements. VSS snapshots are not general partition-table rollback.

## Legacy and hardened environments

An XP x86 profile uses period-compatible imports and tested native CRT behavior; a Windows 7 x64 build is a separate profile. Modern x64/ARM64 adds qualified security mechanisms. Missing OS security guarantees must be declared, not emulated with a process argument called `authenticated`. Windows RT ARM32 is an OEM/research lane pending its deployment/security review, not modern ARM64 Windows under another name.

Use no custom kernel driver in the initial plan. Driver need, lifecycle, signing, vulnerability response and qualification require a separate decision, justified by an essential capability that documented user-mode and offline paths cannot supply.

[^windows-shrink]: Microsoft FSCTL_SHRINK_VOLUME documentation, recorded in the source registry.

## Permission and consistency boundaries

Report native API availability separately from raw-access permission and fresh target eligibility. Standard-user image and saved-report work stays available when physical-device access is denied. VSS acquisition must follow [DE-036](acquisition-consistency.md), with participating writers/volumes and snapshot lifetime, rather than equating live raw reads with a coherent backup.

Server/Core/recovery, hypervisor attachments, event-log/ETW reporting, PowerShell and enterprise policy are separate qualified adapters. None is an initial loader dependency. Computer Management and shell entrypoints follow [native integration](../interaction/native-integration.md); they do not change the storage driver's capabilities.

## Normative requirements

### DE-REQ-034-01

Windows capabilities MUST be checked per API, filesystem and OS profile; XP MUST NOT inherit Vista-only shrink support.

**Verification:** API-availability fake fixtures and real XP import/launch qualification.

### DE-REQ-034-02

System/boot/encrypted or layered storage MUST be routed through dedicated providers and preconditions, not raw bypasses.

**Verification:** Reject unsupported BitLocker/Storage Spaces/system-volume scenarios.

## Related specifications

- [DE-033](providers.md)
- [DE-032](partition-tables.md)

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

## Private borrowed-handle metadata queries

DE-W030's [selected storage observation profile](../catalog/nt-storage-observation-prototype.json)
uses documented descriptor, device-number, geometry, length and volume-extent
queries through an exact injected `DeviceIoControl`/`GetLastError` seam. Only
already-borrowed synchronous fixture handles are supplied; this layer opens or
closes none. The selected factory has no live dispatch admission. Validate every
subject, handle and policy before querying; preserve transport denial, unsupported
API/version, changed/truncated data, cancellation and unresolved activity.

Descriptor sizes, offsets, terminated strings and opaque byte spans are checked
against returned bytes. Header/body disagreement and repeated growth are not
stable metadata. Extent count growth is bounded once, and signed ranges use
checked ends. Raw query receipts retain exact known bytes and digests; original
descriptor strings and UTF-16 labels remain distinct from inert display text.
Reported physical sector size is unknown; translated geometry never substitutes
for independently queried length. Capacity disagreement, serial clones and
duplicate number hints remain visible rather than merged into a target.

Microsoft documents device-number lifetime only until removal/restart; such a
number is a lookup hint, never physical identity. A sequential volume-to-number
match yields only explicit candidate subject keys, including ambiguity, absence
and observed range disagreement. It creates no physical backing or authority
edge. These observations are captured through the existing private graph with
null media identity/generation/capacity and false mutation/admission flags.

An unexpected pending I/O or callback exception stops the port and later subjects;
it supplies no exit, retry, cleanup or writer authority. Byte and call limits do
not establish bounded kernel latency. Owned reader containment, reconciliation,
native source authentication, complete identity/topology, frontend/product/provider
admission and actual historical/other-host support remain subsequent gates.

The [private owned metadata reader](../catalog/nt-storage-worker-prototype.json)
reuses the namespace observation host rather than adding another process launcher.
Preparation creates no child; the adapter retains its session before registering
and launching the capture. Successful native process ownership is stored before
later identity lookup/allocation. Known no-launch failure is separate from an
unresolved launched reader, and only exact owned exit permits later replacement.
The parent reconstructs canonical metadata from bounded returned-byte receipts
and original subjects/policy without calling the original provider. This verifies
producer conformance, with provenance supplied separately by the owned code/
request/process binding. It does not qualify live dispatch or a public ABI.

## Private identity, alignment and layout queries

The [selected private profile](../catalog/nt-identity-layout-prototype.json)
extends the same borrowed query transport with device identifiers, reported
sector/cache alignment and Windows-reported MBR/GPT/RAW layouts. Separate
entrypoints and fixture admission retain finite buffers, raw receipts, cancellation
and unresolved activity. Native pointers remain unadmitted. No storage handle is
opened and no media byte read or write is performed by this fixture slice.

Identifier bytes, association, duplicate/cloned identifiers, original GPT name
code units and contradictory partition facts stay separate from physical media
identity. Signed ranges/counts/offsets are checked; uncertain or inconsistent
reports cannot grant mutation. OS layout is not independent raw metadata parsing.
The pinned SDK ABI determines field interpretation; newly documented fields not
in that selected declaration remain uninterpreted receipt bytes.

The original metadata frame/receipt reader, graph and product do not dispatch
these additions. The separately selected private owned profile below integrates
the new observations without changing the original /1 interpretation. Composite
identity, independent raw layout, actual live/provider/platform/public admission
and owner/full-unit qualification remain work. Native generated fixtures must
qualify the exact control calls, ABI, returned bytes and resource bounds.


## Private owned identity/layout frames

The [private owned identity/layout profile](../catalog/nt-identity-frame-prototype.json)
is an explicit compiled selection. Separate /2 input/reply/observation/frame
identities use the existing owned observation host and a distinct fixture role.
The default metadata /1 profile keeps its field interpretation and shapes.
Neither fixture data nor a received schema selects the parent's profile.

The frame collects disk identifiers, reported alignment and OS partition slots
alongside existing metadata/extents. A shared 128-detail budget covers identifier,
partition (including unused) and extent rows; remaining per-component limits
apply before decoding. Zero remaining detail skips dispatch. Cancellation and
unresolved callbacks stop the batch. Existing byte/value/graph/job and public
protocol limits stay fixed; budget refusal is explicit rather than truncation.

Parent reconstruction binds exact controls, typed property IDs, known returned
bytes, strict receipts and the original selected policy. It invokes no original
provider callback. Equality proves producer conformance; owned code/request/
process/epoch binding supplies separate provenance. It does not prove physical
identity, completeness of omitted queries, independent raw media or effects.

Separate identifier and partition observation nodes keep device summaries within
the existing node bounds. All parent/source/frame/context bindings stay exact.
Cloned reported IDs/layout identifiers and alignment/capacity/range/layout
disagreements are explicit candidates, without subject merge or backing inference.
Original identifier bytes, partition entries and GPT name units remain lossless
and distinct from inert presentation. Partial capture retains only the last
complete frame as stale data; actual owned exit remains the replacement gate.

Generated x64/x86 fixtures, pure replay mutations, maximum current/cached graphs,
owned reader failure/retirement and /1 regression evidence must qualify this
bounded profile before further admission. Live devices, public/product/provider,
composite identity, raw comparison, platforms and owner/full-unit gates remain.
