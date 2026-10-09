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
  version: 0.1.7-proposed.2
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
  at: '2026-10-09T06:29:23.462435+00:00'
  scope: DE-W034 private report worker and retained execution state; public service pending
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
paths/producer/routing receipts are not redacted support content. This private
synchronous adapter remains unlinked from the product; public evidence.export
parameters, admitted case sources, bounded service behavior and frontend parity
remain required before admission. Acquisition/custody and physical/platform
qualification retain their separate gates.

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

## Normative requirements

### DE-REQ-111-01

`health.assess` MUST enforce the preconditions, evidence and recovery limits in this operation contract before admission.

**Verification:** No SMART over bridge, forged serial, media deterioration, accidental self-test, secret leakage, repaired original mislabeled forensic and incomplete acquisition hashes.

## Related specifications

- [DE-030](../storage/identity-and-graph.md)
- [DE-042](../safety/planning.md)
- [DE-043](../safety/journal-and-recovery.md)
- [DE-044](../safety/verification-and-performance.md)
