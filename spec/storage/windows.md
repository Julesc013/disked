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
  version: 0.1.21-proposed.1
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
- id: windows-reference-storage-management
  resource: ../references/sources.json#windows-reference-storage-management
- id: windows-reference-services
  resource: ../references/sources.json#windows-reference-services
- id: windows-reference-service-status
  resource: ../references/sources.json#windows-reference-service-status
- id: windows-reference-service-transitions
  resource: ../references/sources.json#windows-reference-service-transitions
- id: windows-reference-service-recovery
  resource: ../references/sources.json#windows-reference-service-recovery
- id: windows-reference-cancel-io
  resource: ../references/sources.json#windows-reference-cancel-io
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
  at: '2026-10-18T10:43:10+00:00'
  scope: Required-service applicability and lifecycle experiments; proposed, no provider admission
---

# Windows NT provider strategy

## Discovery first

Use documented Win32 handles, storage-property queries, volume APIs and disk-layout IOCTLs, with runtime capabilities determined per exact OS/API/provider. Modern Storage Management can enrich topology but must not become an XP-wide assumption. VDS is a separate optional legacy provider. Record native and independently decoded metadata without flattening partitions, volumes, disks, VHDs, pools and encryption into one object.

## Reference behavior and integration boundaries

Use public API/service contracts first and bounded guest experiments for an
identified ambiguity. Distinguish OS-reported topology, independently decoded
bytes and UI display; none substitutes for the others. Record exact Windows
build, component/provider identity, token/policy, geometry, raw errors and media
effects. Modern Storage Management, legacy VDS and direct documented queries
remain capability-selected providers; do not infer Disk Management's backend
from its appearance. The [testing policy](../development/testing-and-ci.md) and
differential contract (`tests/differential/CONTRACT.md` in the implementation repository) govern observations.

The retained DE-W107 partition pilot on Windows 10 build 19045.7548 illustrates
this distinction: a primary-matching API projection did not resolve conflicting
valid GPT copies; accessible `1 MB` and `Healthy` UI labels did not establish
exact extents, filesystem integrity or recovery eligibility. Preserve those
independent observations in DE-W030. This is a bounded reference result, not a
claim about Windows' general copy-selection algorithm or DiskEd provider admission.
The implementation repository retains its reviewed cases under
`.aide/evidence/2026-10-21-windows-reference/ui/COMBINED-REVIEW.md`.

MMC consoles/snap-ins, Computer Management and Explorer are presentation and
integration surfaces under [DE-025](../interaction/native-integration.md), not
alternate engines. Study service lifecycle only where a concrete DiskEd
operation needs it; no general replacement of Windows services is added.

## Contained native namespace candidate

The [separate private native profile](../catalog/nt-native-namespace-prototype.json)
selects a compiled native role explicitly. It preserves the injected reader's
native/mixed-table refusal, uses distinct schema/attempt bindings and requires
empty native provider input. The existing owned process lifecycle and immutable
inventory publication are shared; native and fixture graph contexts remain typed
and mutually checked. This candidate does not add a public provider or startup
query. Its x64/Win32 native cases, unchanged injected regressions and current
product qualification must pass before the selected implementation is reviewed.

## Required services and lifecycle observations

For a named provider profile, record any required service or activation-capable
API, exact version/access conditions and declared activation effects. Observation
can cause service activation; do not label it effect-free without evidence.
Essential help/build/command discovery retains the nonactivating DE-015 contract.

Keep SCM-reported status, endpoint availability, provider availability, selected
target/operation capability and individual operation outcome separate.
`QueryServiceStatusEx` reports the latest status supplied to SCM; `SERVICE_RUNNING`
is not proof that every provider, target or storage operation is usable. Qualify
absent, disabled, denied, pending, running-but-unavailable and dependency-loss
states without projecting an unavailable provider as successful empty inventory.
Bound startup waits by observed progress and the selected deadline; a timeout
does not establish process exit or stopped effects.

Use the existing work owners. DE-W030 owns relevant read-only provider lifecycle
fixtures; DE-W050 owns the local privileged broker boundary. Installing an
optional service, selecting its account/startup behavior and removing its owned
registrations belong to DE-W060 and [DE-063](../delivery/deployment-profiles.md),
through [DE-061](../delivery/universal-setup.md). No persistent service is required
merely to present an MMC or Explorer interface. Use owned test services or
injected failures; do not disturb unrelated services for reference experiments.

Service stop/control, client disconnect, cancellation request and actual operation
completion are distinct events. `CancelIoEx` requests cancellation without waiting
for completion; a raced operation may complete normally, be aborted or fail for
another reason. Observe its actual completion before retiring its asynchronous
state. Service recovery/restart does not prove transaction recovery or authorize
automatic replay. Reconnect and reconcile the original operation/attempt through
[DE-015](../architecture/execution-topology.md), [DE-022](../interaction/protocol.md),
[DE-043](../safety/journal-and-recovery.md) and [DE-045](../safety/degraded-operation.md).
An unresolved result remains unresolved until supported by actual evidence.
These named APIs illustrate profiles where they are available; each target
retains its separately qualified imports and cancellation mechanism.

Record a remote provider's schema/API separately from its transport and
authenticated host identity. A successful connection is not provider admission.
Unavailable authentication, transport or provider support remains explicit; the
integration plan supplies no listener, remote execution grant or local fallback.

## Operation selection and capability admission

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

## Private independent raw-layout comparison

The [generated-image comparison profile](../catalog/nt-raw-layout-prototype.json)
selects a bounded immutable raw value separately from the IdentityLayout /2
Windows observation. Runtime capture reuses portable MBR/EBR/GPT parsers over
supplied bytes; the Windows provider performs a pure comparison. The eight-row
image review report remains a display, not a complete comparison input.

Both GPT copies and an unambiguous protective MBR must be complete, consistent
and agreeing before a canonical GPT layout exists. MBR/EBR walks retain topology
and explicit faults. Selected limits cannot truncate into an agreement. Metadata
coverage, supplied-prefix completeness, unknown source consistency and unknown
CHS correspondence remain separate properties.

Compare available format, capacity, logical units, disk fields and uniquely
correlated active partition byte extents and common metadata. Retain missing,
extra, ambiguous and differing records. EBR links have separate structural roles;
transient numbers, ordering and host recognition/policy fields are not identity.
Missing capacity, logical-unit or layout evidence prevents overall agreement.

The receipt binds exact raw/frame content, the selected subject and caller's
fixture source/capture/worker tuple. Frame capture must match; the caller declares
the worker tuple, which does not authenticate an owned reader. Content agreement
within that scope proves neither common physical source nor live acquisition
consistency, media identity or storage authority. Original observations and their
claims remain immutable. Generated x64/x86 ordinary-image fixtures must qualify
this private selection; live, owned-reader, provider/product/public, historical
platform, owner acceptance and full-unit admission remain separate gates.

## Private owned image/layout provenance

The [owned-layout execution profile](../catalog/nt-owned-layout-prototype.json)
adds an ordinary generated-file reader to the finite Windows observation host.
It pins expected file/parent identity, reads a complete bounded first capture,
rereads chunks and retains metadata, length/error and digest observations.
Its compiled role receives one anonymous inherited byte channel capped at the
existing 16 MiB decoder limit. The parent copies and hashes bounded bytes,
independently reconstructs the layout and retains immutable values, rather than
keeping a borrowed view of writable shared memory. Old roles retain their
existing argument count, channels and limits.

Only actual owned sessions construct the private typed file/frame snapshots.
The pure join binds native PID/creation, code/request/profile/attempt/context,
capture, selected subject and content digests before comparing common fields.
An expired capture cannot provide a current frame. Historical snapshots retain
their exact evidence without claiming current resource freshness. Unstable
source observations or a partial final logical block make the overall join
incomparable; rounded capacity cannot establish missing source bytes.

These bindings authenticate the owned observation relationship, not a physical
association between the ordinary file and injected Windows subject. Equal reads
and metadata remain live-uncoordinated observations, not an atomic snapshot.
The original pure comparison retains its separate no-authentication scope.
Product composition, public protocol, provider admission, real storage, other
hosts, owner acceptance and full-unit completion require their existing gates.

The separate [composite evidence profile](../catalog/nt-composite-identity-prototype.json)
uses those actual owned /2 frames to preserve selected reported identity facts,
duplicate occurrence groups and successive-capture changes under DE-030.
The original /1, /2 frame and graph interpretations remain unchanged. A genuine
owned /1 frame is insufficient to construct this selected /2 observation.
Its fingerprints and complete-selected-report quality never establish physical
association, current freshness or a storage grant. No new host channel or
shipped composition is selected by this private producer.

The [coordinator-domain guard](../catalog/nt-capture-domain-prototype.json) also
applies to namespace/storage adapters. Prepare their actual domain before
launch so scalar startup reconciliation cannot lose ownership. Native graph
projection retains the typed token outside serialized observation payloads;
actual owned snapshots require the full current key. Composite evidence and
owned ordinary-image/layout joins preserve and compare that same storage-domain
token. JSON labels, another coordinator's numeric epochs and pure receipt
reconstruction cannot manufacture this native binding. No host role/channel,
wire schema, physical source association, provider or shipped composition is
added by this private guard. Historical receipts remain evidence at their exact
source revision, without admitting reconnect or fresh-media authority.

The [private compact projection](../catalog/nt-identity-projection-prototype.json)
derives evidence-only summary rows from actual owned /2 frames and immutable
identity objects. It preserves the existing frame detail nodes and adds bounded
links and complete content references. The retained native object resolves exact
current/previous frame, identity and comparison values; serialized hashes alone
do not reconstruct ownership or provide public retrieval. Cached CLI, shell,
TUI and GUI models consume these rows under their existing observation profile.
No Windows host role, storage query profile, shipped product composition or
public command is added. Full live/provider/platform/owner admission remains open.

The [private owned identity adapter](../catalog/nt-identity-adapter-prototype.json)
explicitly selects compact identity projection with the existing /2 frame
profile. Existing /1 and /2 frame projection defaults remain unchanged. Prepare
the exact owned frame, identity, graph and immutable evidence owners before
coordinator publication; replace owners only for an accepted graph of that
exact attempt. Duplicate, rejected and superseded publications cannot replace
matching retained evidence. Cached retrieval does not poll or dispatch APIs.

Optional comparisons require an exact retained prior digest and explicit named
disk subjects before launching the reader; the current digest comes from its
actual result. Complete captures replace current and last complete owners;
partial captures retain the last complete projection and stale original rows.
Allocation refusal preserves originals, while failure during reader retirement
can leave accepted content published and the actual attempt still outstanding.
No timed-out, cancelled or published result proves retirement. This remains a
private serialized adapter, without live/provider/public/product/owner admission.

The [private mixed inventory session](../catalog/nt-inventory-port-prototype.json)
owns the namespace/storage adapters and serialized capture coordinator. Explicit
reader advancement prepares immutable publications with the exact retained
current/last-complete frames and identity evidence. Every displayed node binds
its native domain, source, capture, worker, frame and context. Preparation failure
preserves the old publication and leaves the newer capture eligible for retry.

Its read-only port returns a prepared aliased generic graph without polling,
launching, waiting, retiring, native API dispatch or an allocating rebuild.
A retained port may outlive the session; it retains frozen data rather than
reader handles or fresh-media authority. Default /1 and /2 frame compositions
remain unchanged; compact identity projection remains an explicit private /2
selection. Complete frame and advertised-reference retrieval performs no I/O.
This is a serialized provider composition, without product/provider/public,
physical, other-host or owner admission.

The [private actual cached renderer composition](../catalog/nt-inventory-frontend-prototype.json)
prepares and retires injected namespace/storage readers before using the
existing Windows GUI, TUI or linear shell. Its source session is destroyed
before rendering, while readonly ports and generic snapshots retain frozen
native frame/reference owners through host teardown. Cached labels, evidence
focus, manual refresh and refusal of health/media-target authority use the
same semantic service. No native advancement occurs during presentation.
Generated JSON inputs and new receipts belong only to the separate bounded
test launcher; they add no public flags, live paths or shipped composition.
Owned desktop/console and import/launch evidence remains limited to its tested
host and selected x64/Win32 processes; provider, live/physical, historical-host,
public/product, accessibility, owner and full-unit admission remain separate.

The separate [private serialized native advancement composition](../catalog/nt-inventory-advance-prototype.json)
wires an application-owned pulse into existing Windows hosts. The injected
source session explicitly starts/releases/polls/cancels/times out readers and
prepares immutable publications; model getters and operation completion polls
do none of those things. Four bounded controller-owned event names request
private workloads, without adding a public endpoint or storage authority.
At most three authored captures and finite zero-wait pulses preserve existing
worker, graph, display and 256-MiB frontend budgets. A 5000-ms outer attempt
deadline does not extend the native 1000-ms startup-release barrier. Neither
a result, timeout, cancellation nor closing the host establishes actual exit;
retirement is separately observed before another source attempt is eligible.
On host closure, a cancellation result can arrive before explicit owned-job
retirement; otherwise the source is unavailable. Retain the actual outcome,
not a fabricated successful result. Initial/intermediate/final publications,
source outstanding state and held old native owners remain separate evidence.
This private injected profile admits no live/physical association, current
resource freshness, provider/public/product API, other-host, owner or release
claim.

The next private host qualification contract selects `screen` explicitly in
owned hidden consoles, preserving the exact old review and restoring the original
active buffer and console state. Its separately injected `pending` application
callback fault escapes the driver only after readers are outstanding. Internal
frontend error 4, unavailable final model sampling, cached owner retention and
actual reader retirement remain separate observations. These optional test-only
selectors default to the earlier linear/no-fault fixture behavior and add no
product flags, live provider or other-host admission. The owning private catalog
records the continuation base and expected outcomes before evaluation.

The next private integration contract withholds one already computed read-only
`target.inspect` result behind a separately owned completion event. The existing
internal `Submission::deferred()` state keeps its exact pending request identity;
it is not a protocol response or an admitted durable operation. Do not manufacture
an `accepted_running` envelope or operation ID. The original completed read-only
envelope and legitimately absent/null operation ID remain exact. Native source
pulses and `CompletionPoll` stay independent.
Actual GUI/TUI retain the old-view completion separately; the linear shell preserves
its original transcript and result basis. This simulates deferred interface delivery
and does not qualify a real asynchronous storage operation, durable record, reconnect,
freshness or mutation authority. Closing before completion records undelivered state
without inferring reader exit. The owning private catalog fixes expected outcomes
before implementation; all earlier host behavior and source budgets remain.
