---
type: DiskEd Specification
title: Health assessment and forensic workflow
description: Independent operation contract for health.assess.
resource: disked://spec/de-111
tags:
- disked
- operations
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-111
  profile: disked-spec/1
  version: 0.1.17-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-030
  - DE-042
  - DE-043
  - DE-044
  requirements:
  - DE-REQ-111-01
updated:
  by: codex
  at: '2026-10-09T13:59:19.684583+00:00'
  scope: DE-W034 bounded historical observation collections and explicitly granted private retention; product worker and platform gates remain open
---

# Health assessment and forensic workflow

## Identity and availability

Semantic ID: `health.assess`. Operation specification: `DE-OP-011`. Earliest phase: **M3/M4**. Initial target scope: read-only observations with explicit acquisition policy. Status: a provisional fake-only command is under local development; real observers and physical qualification remain planned. No availability is implied by the presence of this document.

## Required inputs and preconditions

Known target identity and observer capability; do not assume SMART passthrough works through all bridges. Cases identify allowed scope, custody and redaction. Deep self-tests and potentially damaging reads require explicit selection.

## Planned procedure

Collect bounded observations, retain unavailable fields, distinguish vendor interpretation from raw values. If media errors exist, route toward image-first acquisition rather than destructive repair. Forensic acquisition keeps immutable custody events and qualified write-blocking observations.

## Postconditions and evidence

Health report is evidence, not a guarantee of future reliability. Forensic report states exact acquisition scope, unreadable ranges, software and operator records. No repaired original media is silently called an untouched forensic source.

## Interruption, cancellation and recovery

An interrupted health query returns partial information. A degraded device can deteriorate even under reads; stop/retry strategy belongs to the case. Recovery operates on a copy unless independently authorized.

## Required adversarial cases

No SMART over bridge, forged serial, media deterioration, accidental self-test, secret leakage, repaired original mislabeled forensic and incomplete acquisition hashes.

## Private native observation contract

DE-W032 first implements the [proposed observation profile](../catalog/health-observation-prototype.json)
against fake/owned values. Its immutable request binds target generation/composite
identity and observer/provider declarations. Every returned field belongs to the
requested set; missing or unavailable data stays explicit. Raw bytes and vendor
interpretation with its rule identity are separate. Neither a serial string nor a
complete response establishes physical identity or safe media.

Capture/worker epochs reject stale results. Request completion, timeout,
cancellation and worker retirement remain distinct; outstanding workers prevent
a replacement capture. Cancellation stops further dispatch without discarding
valid partial evidence or inventing exit proof. Count, byte and epoch limits fail
without silently truncating accepted observations.

The default support projection omits identifiers, raw values and interpretation
text. Its explicit policy can select additional classes; secret field content is
never exported. Classification belongs to the selected request and cannot be
downgraded by a returned field. Exact internal bytes and redacted support output
remain separate. Public admission still requires reviewed adapter classification,
actual containment, provider identity and target validation; declarations alone
are not qualification.

This private reducer does not issue queries or self-tests, access files/devices,
or itself implement the command service. DE-W030 native inventory remains a prerequisite
for actual observer admission. Forensic custody, acquisition coverage, write-blocking
and physical/platform qualification remain separate DE-W033/034 and later gates.

## Provisional fake command execution contract

The [fake command profile](../catalog/fake-health-command.json) and
[parameters](../schemas/command-health-parameters.schema.json) define the initial
`health assess <target_id>` observable contract before evaluation. Only exact
fake graph IDs are accepted. Request `expected_revision` and frontend review
must bind the graph revision before collection. Denied/stale targets refuse;
unknown observations return partial data, and table/volume fixtures explicitly
lack an observer. Selected composite identities and provider declarations are
bound independently of cloned serials. New/unrecognized fixture identities
remain unavailable. Lookup is synchronous and has no OS/device/file port.

The result identifies compiled fixture provenance and has no sampling timestamp.
Its `support_report` defaults to ordinal labels, states and availability only.
Optional `include_identifiers`, `include_raw`, `include_interpretations` and
`include_customer_data` booleans (corresponding CLI flags) select disclosure.
Identifier/customer content also needs its category flag; secret content is
never disclosed. The outer target/revision envelope is routing metadata, not a
redacted support payload. No support file is created. Exact fixture label bytes
are preserved within separate raw/interpreted limits; oversized values become
explicit error/null. Human presentation escapes arbitrary control/Unicode text
without altering machine values. Completed/partial reports cannot authorize
mutation or establish physical identity, media reliability or observer admission.

This bounded prototype may proceed under the recorded local continuation grant.
DE-W032 remains partial; DE-W030 inventory and actual observers, classification,
containment, forensic custody and platform qualification retain their own gates.

## Private case evidence contract

DE-W034's [proposed case profile](../catalog/case-evidence-prototype.json)
records immutable before/observation/after snapshots from the validated native
collector. Each record binds exact case/code/fixture/target/provider declarations,
its phase, a distinct case sequence and the prior record digest. The builder
records a snapshot; it does not issue a fresh query, retire workers, authenticate
an operator or establish physical preservation. An absent after snapshot and
unavailable fields remain explicit. Native acquisition/custody/file persistence
and observer admission require their own ports and actual evidence.

Public-field comparison is a labeled inference. Changed target/provider/requested
field bindings, missing values and unavailable raw/interpretation remain
incomparable; identifiers, customer labels and secrets do not decide the result.
Support projection only discloses that comparison with both raw and interpreted
content selected. It never certifies reliability or storage postconditions.

The support payload never contains the original private case/context/fixture or
custody digests: these can disclose omitted content. An opt-in identifier policy
may bind the disclosed projection with a separate chain, explicitly distinguished
from original custody. Default output uses ordinal labels, states and availability;
the existing category/content gates and unconditional secret omission apply.
Record/count/aggregate budgets reject without editing old evidence or truncating
it. These are proposed serialized contracts, not a frozen public storage ABI.

The [proposed export profile](../catalog/report-export-prototype.json) binds a
typed support projection to exact UTF-8/LF bytes, destination/ancestor generations
and producer metadata/content. Preparation creates no file. Execution requires a
matching immutable definition and separate report-write/host-effect flags. The
native ordinary-file adapter holds parents/producer, uses creation without
overwriting, rejects nonordinary paths, flushes and verifies exact readback.
Submitted, acknowledged-written, read and verified counts remain distinct; lost
acknowledgement and incomplete effects remain uncertain. Failure/cancellation
retains any created output; there is no automatic deletion, retry or overwrite.

Export completion concerns that output artifact. Per-file flush API confirmation
does not establish power-loss persistence, media health, forensic custody,
original-source preservation, worker exit or authenticated approval. Surrounding
paths/producer/routing receipts are not redacted support content. The synchronous
adapter was private before dev.31. The current native recorded-acquisition source,
contract, bounded service and frontend qualifications are described below.
Broader case sources, custody and physical/platform qualification retain their
separate gates.

## Recorded acquisition cases

The [proposed acquisition-case profile](../catalog/acquisition-case-prototype.json)
adds a typed, immutable view of an explicitly selected ordinary-file worker's
request and history. Its native reader holds the two fixed metadata files and
strong ancestors, checks actual paths/generations/content and binds the recorded
operation, host declaration, store and history file identity. It never follows
source, destination or map paths inside the records. The pure model validates the
request/plan/grant declarations and bounded canonical history before retaining
before/after snapshots and an exact content revision. Open/torn history and
missing configuration evidence remain explicit; a record hash authenticates no
actor and establishes no current image bytes, worker exit or preservation claim.

Default support discloses structural state and recorded outcome only. Raw values,
code/random identifiers and labeled inference have separate gates. Literal
declared paths require identifiers, customer-data and raw-value selection
together. Original case/definition/history/record hashes, resource/capture hashes,
grants, diagnostics, receipt extensions and torn contents stay omitted under
every policy. The typed support artifact can use the private bounded exporter;
completion qualifies that artifact alone. Exact case/source-resource admission,
bounded service waits/cancellation/late results and all frontend journeys remain
required before public `evidence.export` availability. Authenticated custody,
current image verification and physical/platform qualification retain their gates.

## Joint case and export admission

The [joint prototype profile](../catalog/acquisition-case-export-prototype.json)
binds the exact case revision, current metadata source and typed output effects
under one immutable definition and grant. Read-only preparation creates no file.
Execution requires separate case-read, report-write and host-effect declarations,
then reconstructs and compares all reviewed inputs. No case-contained image path
is followed and a matching digest authenticates no actor.

Revalidate the held source before each native effect/resource step and after the
effect finishes. Source applicability and output facts remain separate: a late
source change can invalidate joint completion without erasing a verified created
file or its receipt. An unavailable effect result remains uncertain. Preserve
partial outputs; no automatic retry or deletion. These observations are not an
atomic multi-resource transaction or privileged-writer fence.

The strict provisional definition/outcome schemas describe this private contract.
Public worker/store identity, reconnect, bounded service/cancellation/late results,
descriptor syntax and all frontend journeys remain required before availability.
Authenticated custody, current image verification and physical/platform gates
remain separate. Schema/model passes do not admit the public command.

## Private report execution state

The [report worker profile](../catalog/report-worker-prototype.json) adds a
separate immutable execution definition around the joint case/export definition.
Bind exact producer/worker code, host and owned state-directory generations before
dispatch. Explicit store-write authority covers request, claim, bounded history
and cancellation metadata. Preparation creates no file; generated acquisition
image paths remain declarations and are never followed by this report role.

Persist operation/attempt/worker identities and actual process identity. Prepared,
executing, effect certainty, worker-observed cancellation and finished receipts
remain separate. The versioned worker `cancellation_observation` says
`not_observed` or `observed`; it never asserts that no request exists. Close
provider handles before recording effect quiescence; this does not establish
process exit. A delayed admission retains an unknown operation
and must not cause restart. Repeating the same admission only observes its store.
A failed terminal write retains the last valid state and actual created output,
without inventing a completion receipt. Torn histories remain unknown.

The ordinary same-file worker uses finite admission, process, memory and record
budgets. Test-only delays and metadata-write failures qualify actual process/API
behaviour, not power loss or physical storage. Public export descriptors,
parameter/result contracts, bounded common service/watch and all frontend journeys
remain admission gates. Retention grants no new writer permission.

## Current acquired-file verification

The [private verification profile](../catalog/acquired-image-verification-prototype.json)
defines a separate current-byte observation before evaluating its implementation.
Explicitly select image/map paths and an exact recorded plan. Do not follow paths
contained in case/map metadata. Bind current read resources and original output
generations, require both read grants, and use read ports only. No resume, replay,
map repair or automatic creation/write path is part of verification.

Independently validate canonical map ordering/hash chain, chunk geometry,
pending/checkpoint pairs, substitutions and full seal coverage. Read checkpointed
image ranges and distinguish bytes returned from bytes matched. Preserve matching
prefixes while later mismatch, unavailable reads, torn maps, cancellation or
resource changes keep the complete result unqualified. Bind separate before/after
resource observations; a transient observed generation change cannot be forgotten
merely because a later observation matches again.

`matched` concerns current held ordinary-file bytes matching the recorded map.
Substituted zeros remain substituted data. A consistent map authenticates no actor
and establishes no untouched source, point-in-time acquisition, worker exit,
healthy media, physical fencing or power-loss persistence. Existing acquisition
case/support claims remain `current_image_verification: not_performed` unless a
separate applicable verification observation is explicitly bound to them.
The native case source's revision and before/after bindings remain a separate
applicability check. A later unavailable case binding must retain the independently
observed image result; it cannot authorize a current-case completion claim.

The initial Windows adapter/probe is private and synchronous, with bounded
allocations, records and ranges. OS-call latency and asynchronous containment are
not thereby bounded. Native generated-file qualification, typed case/custody
integration, bounded product worker/watch and frontend journeys remain separate
steps; this component does not add an available product command or stable ABI.

## Immutable verification observations and disclosure

The [private observation profile](../catalog/image-verification-observation-prototype.json)
binds exact acquisition case/request/history semantics, raw request resource bytes,
verification definition/outcome, actual verifier code/clocks and separate case and
image before/after bindings. Validate relationships between counters, seals,
resource revalidation and outcomes before recording. Contradictory declarations
cannot construct a successful observation. No stored path is followed here.

Keep the original acquisition case and its earlier `not_performed` claim immutable.
This separate record preserves image-byte matching when a later case/image binding
makes attachment changed or unavailable. Historical applicability and matching do
not qualify the latest files or grant execution. Retain exact bounded full-view
identity without treating its digest as observer or custody authentication.

All sixteen four-boolean disclosure policies have explicit projections. Default
support contains recorded status and applicability markers; raw values select
bounded counters/clocks; identifiers select only random case/operation/attempt/
worker identities and verifier code; interpretations remain labeled inferences.
Do not disclose original customer/resource/private-record hashes, routing paths,
arbitrary diagnostics or substitute pseudonyms under any policy. The selected
artifact's own digest covers only its support bytes.

Private ordinary-file exports separately review the complete observation/source/
effect wrapper and require its digest plus explicit output/host-effect grants.
Keep source applicability and actual output facts separate. A late source change
cannot rewrite the immutable historical observation or authorize an automatic
retry. This probe qualification does not admit a new product command or a stable
worker/store contract. Durable custody collections, bounded reader/watch and all
frontend/platform/physical qualification remain gates.

## Private historical verification collections

The [collection profile](../catalog/image-verification-collection-prototype.json)
defines bounded snapshots with the exact original raw request/history, typed
case and ordered verification observations. Each new snapshot retains old
records and binds a separate observer attempt/worker/capture/process identity.
Ordinal collection order does not establish fresh sampling or clock order.
Restore rebuilds the original case, typed observations and every chain binding;
it performs no OS calls and follows no path retained in a record.

Complete private retention and selected support are separate typed artifacts.
Private retention needs an additional private-metadata grant at the effect port;
its canonical bytes include original paths/metadata and are never support data.
Review binds the exact collection revision and complete create-new effect.
Flush/readback facts do not establish power-loss persistence or actor custody.

An ordinary-file reader takes only an explicit selected path and expected
artifact digest, retains strong file/parent bindings, applies finite byte/read
budgets and validates the entire retained snapshot. It must not reopen the
original case/image/map paths, and late selected-file applicability stays
separate from the immutable historical facts. Qualify actual generated-file
retention/reload, disclosure, malformed/contradictory records and held-source
changes. Bounded workers, watch/cancel and actual image.verify frontends remain
required before product availability. This private profile freezes no stable
persisted ABI and grants no physical, owner, release or authentication claim.

## Normative requirements

The private [verification worker profile](../catalog/verification-worker-prototype.json)
owns the next bounded Windows ordinary-file execution slice. Its immutable
definition binds the actual case metadata/raw request, selected image/map,
verifier generation, host and owned execution store. An exact wrapper grant
must include case/image/map reads and store, host and private-metadata effects
before any supplied path is followed. Never borrow another image's recorded
identity or open original source paths retained inside the case.

Keep operation/attempt/worker/capture identities distinct from collection
ordinals. Sample progress only after confirmed checkpoints. Persist cancellation
requests independently of worker observations; a late request cannot rewrite
the actual verdict. Admission timeout preserves the operation and its inputs,
without restart, removal or assumed exit. Close provider handles before recording
quiescence, and observe actual process identity/exit separately.

Retain a typed historical collection under the fixed owned filename. Keep the
verification outcome even when collection or terminal-record persistence fails.
Verified retention requires bounded readback and pure full restore; historical
inspection opens only the explicitly selected operation store. Private finite
history/cursor inspection does not qualify public negotiated events, frontends,
or the latency of every filesystem call. Product image.verify remains unavailable
until those gates have actual command and frontend evidence.

### DE-REQ-111-01

`health.assess` MUST enforce the preconditions, evidence and recovery limits in this operation contract before admission.

**Verification:** No SMART over bridge, forged serial, media deterioration, accidental self-test, secret leakage, repaired original mislabeled forensic and incomplete acquisition hashes.

## Related specifications

- [DE-030](../storage/identity-and-graph.md)
- [DE-042](../safety/planning.md)
- [DE-043](../safety/journal-and-recovery.md)
- [DE-044](../safety/verification-and-performance.md)


The provisional `evidence.export` prepare/execute contract and strict producer
schemas are owned by the [export command profile](../catalog/export-command-prototype.json).
The dev.31 ordinary-file composition selects it through the shared asynchronous
request channel. Exact metadata/resources/effects, explicit wrapper digest and
all four grants remain necessary. Source applicability cannot erase output facts.
The [report watch profile](../catalog/report-watch-prototype.json) owns retained
request/row validation, independent operation/attempt/worker/observer identities,
reconnect, cancellation observations and finite event/reply/rendering budgets.
Historical compatible observation grants no new writer authority.

Actual CLI/stdio/GUI/TUI/shell and bounded request tests qualify only the native
generated-case prototype at their exact source/host/artifact identities. Public
contracts remain proposed; full before/after/custody coverage, authenticated actors,
current acquired-image verification, other platforms, physical storage and owner
acceptance remain unqualified. Neither structure checks nor a UI review grants
storage authority or changes those gates.

The provisional [verification command profile](../catalog/verification-command-prototype.json)
now fixes shared prepare/execute, six grants, exact retained request/state bindings,
status/exit translation and negotiated finite observation. The private command
probe uses actual generated acquisitions and contained ordinary-file readers.
The [product verification profile](../catalog/product-verification-prototype.json)
selects the existing adapter in the ordinary-file native composition. Availability
requires bounded request-channel and actual CLI/stdio/GUI/TUI/shell evidence,
including independent process/history/collection reconstruction and uncertain
reply/retention outcomes. This historical verification is separate from an
authenticated custody claim or authority for the latest image generation.
Schema validity authenticates no actor, custody or current storage authority.


The [joined acquisition/verification report profile](../catalog/acquisition-verification-report-prototype.json)
owns a private typed snapshot of the original acquisition and a selected retained
verification collection. Construction requires exact original case/revision and
raw request/history equality and at least one recorded verification observation.
Original before/after facts and subsequent observations remain separate; custody,
current-image state and power-loss persistence remain unestablished. The complete
private snapshot/revision is distinct from all sixteen explicit disclosure
projections. Existing collection support is unchanged.

The private native export coordinator binds both selected ordinary metadata
sources and the complete typed output effect. It requires the exact joint review
digest and explicit case-read, collection-read, report-write and host-effects
flags. Each source has a separate last observation and ordered check sequence;
matched does not mean simultaneous or persistent freshness. Late source failures
retain actual output outcomes, counters and receipts. Preparation creates no
output; execution is create-new and single-use. Private synchronous qualification
is not a public latency promise. This slice adds no product command, stable ABI
or full DE-W034 acceptance.

The [joined report worker profile](../catalog/joined-report-worker-prototype.json)
extends the existing private report role through explicit definition version 2;
version 1 retains acquisition-only meaning. Strict producer schemas dispatch
bounded-integer and relationship checks automatically. Outer execution authority
requires the exact worker definition digest and separate case-read,
collection-read, report-write, store-write and host-effects flags. Preparation
must fit the complete retained header before returning review content.

The worker reconstructs both selected source generations and exact output
before admitting effects. Shared state/record version 2 preserves independent
source visits, output facts, receipts and exact process/attempt/worker identity.
Completed joined records require matched final adjacent case/collection checks
after at least four visits and completed verified output. Observation timeout,
caller departure or a lost terminal record cannot authorize a replacement or
invent completion. Applicable native reconstruction and exact artifact counters
remain necessary beyond standalone producer-schema checks. Common command,
bounded public-envelope/rendering and CLI/stdio/GUI/TUI/shell admission remain
the gate after private qualification. The product links the private adapter in
dev.35 without selecting a new public command variant.

## Provisional joined report public admission

The [public joined profile](../catalog/joined-report-public-prototype.json)
extends the existing provisional `evidence.export` command. Both
`collection_path` and its exact `collection_digest` MUST select the joined
prepare variant; either alone MUST refuse. Absent both retains acquisition-only
meaning. Execute MUST bind explicit worker definition version 2 and its exact
outer digest, with separate case-read, collection-read, report-write, store-write
and host-effects grants. Source/disclosure selection cannot be changed at execute.
Version 1 retains its four grants and forbids collection authority.

Joined preparation/result producer schemas use version 2. They MUST preserve
distinct acquisition and historical verification facts and declare authenticity,
custody authentication, current-image state and power-loss persistence
`not_established`. A known operation prefix without a validated definition MUST
NOT establish a source profile. An unresolved execution MUST retain separately
known review digest, state routing and allocated operation identity. An unresolved
observation without a known definition remains unclassified.

Preparation MUST fit a complete future execution envelope with a maximal escaped
request identity, including framing, before presenting executable review. Common
callbacks, output frames and all frontend review/current/earlier-result displays
MUST preserve valid bounded content. Private editor/composite display bounds are
separate from the unchanged 64-KiB input and one-MiB output frame. Oversized or
malformed replies do not establish absent effects or authorize retry.

Qualification requires actual native CLI, stdio, GUI, TUI and shell preparation,
execution, retained watch/reconnect, independent exact support bytes and actual
worker exit on generated acquisitions and retained verification collections.
The old source-image paths must be unavailable during joined report tests.
Synthetic port/budget tests supplement those journeys and MUST be labelled
separately. Full DE-W034, stable ABI, owner, physical/platform and release gates
remain separate from this bounded prototype admission.
