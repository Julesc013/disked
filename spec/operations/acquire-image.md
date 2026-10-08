---
type: DiskEd Specification
title: Read-only image acquisition
description: Independent operation contract for image.acquire.
resource: disked://spec/de-103
tags:
- disked
- operations
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-103
  profile: disked-spec/1
  version: 0.1.2-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-030
  - DE-042
  - DE-043
  - DE-044
  requirements:
  - DE-REQ-103-01
updated:
  by: codex
  at: '2026-10-08T13:02:26.765242+00:00'
  scope: DE-W033 private native acquisition pipeline; ordinary-file/provider admission and owner acceptance remain pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Read-only image acquisition

## Identity and availability

Semantic ID: `image.acquire`. Operation specification: `DE-OP-003`. Earliest phase: **M4**. Initial target scope: explicit source and separately owned destination. Status: specified, not implemented or qualified. No availability is implied by the presence of this document.

## Required inputs and preconditions

Confirm source identity, destination capacity, destination is not a source extent/alias, overwrite policy, sparse policy and evidence root. For failing media choose a read-mostly strategy and request operator approval before aggressive rereads. Destination paths may be symlinks/reparse aliases and need safe resolution.

## Planned procedure

Create destination with no-clobber semantics; record geometry/identity; stream bounded regions with a persistent acquisition map. Distinguish successful reads, unreadable ranges, retries and substituted bytes. Checkpoint source/destination identities and verified region hashes. A filesystem-aware acquisition is a different provider with documented metadata coverage.

## Postconditions and evidence

Image, acquisition map and evidence agree on source size, unreadable ranges and verified bytes. A full-image digest is labeled according to what was actually read. Verify destination independently where policy permits; no restore readiness claim without the required validation.

## Interruption, cancellation and recovery

Resume only with matching identities/map/destination state. An interrupted map record is uncertain and causes bounded re-observation. Do not overwrite original source. Stop/pause may be safe between recorded chunks but failing-media policy takes precedence over ordinary throughput.

## Required adversarial cases

Destination equals source through alias, full destination, thin-provisioning exhaustion, disconnected device, corrupt map, resumed different disk, read substitution and destination file preexistence.

## Consistency and observational effects

[DE-036](../storage/acquisition-consistency.md) governs source consistency and capture epoch. Bind participating volumes/writers, snapshot scope/lifetime, source-read and destination-write permissions, host side effects and resume limits. Report live-uncoordinated/unknown rather than coherent when evidence is absent. Hash coverage, filesystem validity, restore readiness and bootability are independent results.

## Normative requirements

### DE-REQ-103-01

`image.acquire` MUST enforce the preconditions, evidence and recovery limits in this operation contract before admission.

**Verification:** Destination equals source through alias, full destination, thin-provisioning exhaustion, disconnected device, corrupt map, resumed different disk, read substitution and destination file preexistence.

## Related specifications

- [DE-030](../storage/identity-and-graph.md)
- [DE-042](../safety/planning.md)
- [DE-043](../safety/journal-and-recovery.md)
- [DE-044](../safety/verification-and-performance.md)

## Private native acquisition pipeline profile

DE-W033 first implements a private provider-independent C++14 pipeline under
`source/runtime/acquisition/`. Its fixture port is not the Windows file provider;
`image.acquire` remains unavailable until separately implemented and tested
ordinary-file admission and shared frontend execution are reviewed. This step
does not reduce the programme's full acquisition/platform scope.

The private [plan review schema](../schemas/acquisition-plan-prototype.schema.json)
binds source, destination, acquisition map, host, executable and provider
individually: composite provider identity, expected generation/epoch, access,
effect footprint, complete relevant alias set, failure domain and verification.
The source/destination byte footprint is exactly `[0, bytes)`; nonrange host/code
observations have zero range, and `create-append` identifies effects on the owned
map rather than claiming a zero-byte map. Map capacity/parent ownership is a
provider precondition, not established by these abstract fields. All output alias
sets must be disjoint from each other and from inputs/execution dependencies.
Shared failure domains are disclosed; they do not imply independent backup.

Pure `prepare` validates fixed role semantics and serializes an immutable private
definition. A separate execution grant binds its exact digest and source read,
destination write, map write and host effects. No provider runs during definition.
Before each new chunk effect, reserve map capacity for its intent, checkpoint and
seal; budget exhaustion must not begin an effect it cannot record.
Immediately before output creation, observed bindings must equal the plan.
The provider must establish safe path resolution, complete alias/capacity checks,
no-clobber output creation and owned resource control before effects. Creation
returns exact owned output identities/generations for the retained header. A
creation refusal may claim no effects only when the provider proves no output
was created; other creation errors retain a failed partial result. Every
dependent boundary rechecks source/host/code/provider and those owned resources;
output content progress is checked against the map, not mistaken for a new
resource generation. A provider must enforce these observations under its actual
locks; a JSON binding is not an OS lock or proof of physical ownership.

Buffers are one selected 4 KiB, 64 KiB or 1 MiB chunk with bounded source and
destination readback storage. Size is a canonical decimal string in signed-64
file range; before I/O the base two-record-per-chunk map must fit a one-million
record budget. Additional failure records consume that same finite budget.
Records are at most 16 KiB and stream one at a time. No entire image or map needs
to be buffered by the runtime. Oversized provider reads are errors.
Nonempty provider read errors must be valid UTF-8 identifiers of at most 256
bytes without ASCII control/delete characters. Reject malformed errors before
retry, map append or destination effects; never emit a receipt the reader rejects.

Ordinary policy permits an explicitly selected retry ceiling of zero through
three. `failing-read-mostly` admits zero automatic retries and no completed-source
verification reread on resume. More aggressive failing-media policies remain
unavailable pending their operator-approved contract. A failed/short read stops
with an explicit failure record, or `zero-fill` explicitly substitutes the entire
requested chunk, retaining the observed length/error/retry count. Returned bytes
from failed reads are never copied as established source data. Substitution
digests describe zero output, not recovered source bytes. No sparse optimization
is admitted by this first pipeline.

The private test acquisition map uses exact native sorted-key UTF-8 JSON bytes,
canonical decimal strings, a sequence and previous-record SHA-256. It contains
an immutable definition/owned-resource header, chunk intent (`pending`), verified
`checkpoint`, explicit `read_failure` and terminal `seal`. These hashes detect
alteration; they are not authentication. This encoding is private and provisional,
not the production journal gated by DE-DEC-004. Header and intent map flushes
precede data effects. Destination flush and independently obtained readback hash
must succeed before checkpoint append/flush; a successful write alone is not a
checkpoint. Flush capability/power-loss guarantees belong to the actual provider.

Resume parses bounded ordered records, rebinds the exact original definition and
source epoch plus owned destination/map generations and execution closure, and
verifies each checkpoint's destination bytes. Ordinary policy additionally checks
current successful-source prefix hashes; failing-read-mostly avoids that reread.
An incomplete final record can be removed only after the complete prefix is
validated; a corrupt complete record, reordered sequence, different identity,
unexplained prefix or unknown critical record is refused. A pending effect is
observed before replay: matching destination bytes can be checkpointed after
required verification/flush, otherwise reread source must match that exact intent
before overwriting only its owned destination range. Explicit zero substitution
must match the zero digest. Original sources are never overwritten. Corrupt maps
cannot be discarded to start over on an existing output.

Stop requests become `paused` only at a recorded chunk boundary, including an
inert precreation stop. They do not authorize abandoning an uncertain pending
effect or replacing a possibly active provider. A synchronous port's return must
establish call completion; process containment and asynchronous frontend lifecycle
remain separate integration work. A sealed resume verifies its applicability and
does not append/write when it already satisfies the definition.

The [outcome schema](../schemas/acquisition-outcome-prototype.schema.json) keeps
checkpoint, successful source, substitution, attempt returned-read, written and
readback-verified bytes separate. `completed_with_substitution` stays distinct
from `completed`; errors retain prefix coverage and effect uncertainty. The
consistency class remains `live-uncoordinated`. Per-chunk verification and a map
seal do not certify atomic capture, filesystem validity, restore readiness,
bootability, real-file resumption or physical/power-loss safety.

The native test probe models owned resources and pre/post API interruptions only
in memory. Its independent Python expectations check exact destination bytes,
SHA-256, ordered maps, grant/binding/alias refusal, bounded reads/retries,
substitution, stops and uncertain-effect recovery. Actual ordinary file handles,
capacity/sharing/no-clobber races, process interruptions, imports and frontend
evidence remain required before DE-W033 is complete.
