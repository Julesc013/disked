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
  version: 0.1.3-proposed.1
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
  at: '2026-10-08T14:09:59.155322+00:00'
  scope: DE-W033 private Windows ordinary-file adapter; public command admission and owner acceptance remain pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Read-only image acquisition

## Identity and availability

Semantic ID: `image.acquire`. Operation specification: `DE-OP-003`. Earliest phase: **M4**. Initial target scope: explicit source and separately owned destination. Public command status: specified and unavailable. Private native components are under local implementation/review; no public or physical-storage qualification is implied by this document.

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
Before tail repair or new effects, the provider must validate that destination
coverage is explained by the verified checkpoint prefix and at most its one
pending range. The growing-file profile requires checkpoint-end <= file length
<= pending-end (or checkpoint-end when no intent is pending). A test provider
may explicitly preallocate known-zero storage, but must reject unexplained
nonzero suffix bytes; that allowance is not the growing-file policy.
An incomplete final record can be removed only after the complete prefix and
destination coverage are validated; a corrupt complete record, reordered sequence, different identity,
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

## Private Windows ordinary-file acquisition profile

The next DE-W033 component uses `source/providers/image/file_acquisition.*`.
It remains private and is exercised by dedicated probes; its existence does not
admit `image.acquire` in the product command registry. The selected prototype is
Windows NT 10 x64 with the recorded v143/SDK build. Other OS/ABI profiles remain
unverified. It copies raw bytes only; no mounts, snapshots, physical devices,
elevation, sparse optimization, filesystem transformation or installation.

Preparation observes source, executable and path identities using non-inherited
handles without creating outputs. Execution needs a separate exact-plan grant
for source reads, destination writes, map writes and host effects. The shared
ordinary-file path guard rejects device/UNC/stream paths, reparse parents/files,
multiple hard links, recall/offline files and names outside the bounded local
fixed-drive profile. Original UTF-8 paths and file identifiers remain separate
from invariant uppercase leaf lookup keys used to conservatively detect proposed
output aliases. Logical file/parent identities do not establish all physical
backing aliases. Observed volume IDs disclose a shared file-volume domain; they
are not authenticated storage-topology or independent-backup evidence.

Source epochs include file ID, volume, size, creation/write/change times,
attributes and hard-link count. Parent and owned-output generations bind file ID,
volume and creation time; progress checks additionally bind expected map length
and verified destination coverage. Executable identity includes its metadata and
bounded whole-executable SHA-256, and provider generation binds that code hash.
Resume requires the same executable generation; changing from a fault probe to
a normal probe does not establish compatibility. The host binding records the
local computer name and profile, not global uniqueness, authenticated remote
host identity or a security boundary.

Pinned ancestors and source/code handles deny ordinary write/delete sharing;
effect handles for destination/map use exclusive normal-file sharing. These
checks are normal Windows file coordination, not privileged/physical fencing or
protection against an administrator, preexisting writable mapping, malicious
kernel component or external storage writer. Every dependent boundary rechecks
the retained identities. Source consistency remains `live-uncoordinated`.

Start uses `CREATE_NEW`, first for the map and then destination. Existing names
are never truncated or cleaned up. If the first creation fails before an output
exists, refusal can report no output effects. Failure after creation retains the
partial owned files and an accurate failed result; missing/torn headers do not
authorize automatic resumption or disposal. The receipt distinguishes creation
attempts from obtaining both output handles. Destination files grow as chunks
are written; no whole-image preallocation silently makes an unexplained suffix
legitimate. Resume observes existing files read-only, then reopens without
truncation, takes exclusive sharing and rechecks both identity and map length
before any repair, append or image write.

Receipts distinguish tracked expected map length from actual size observations
on held map/destination handles. Missing/unobservable handles yield null size
and retained observation errors where applicable, not an invented zero. Resource
receipts identify whether their bindings are the prepared plan or effect-owned
outputs. Attempt byte counters count successfully returned provider calls;
partial/failed writes can leave more actual file bytes than that counter reports
and must retain effect uncertainty until verified recovery.

Map framing is exact canonical UTF-8 JSON followed by one LF per complete record.
Each body is at most 16 KiB, traversed in bounded read windows; the final missing
LF marks an incomplete tail. Complete invalid JSON, CRLF, unknown critical
records, bad sequences/chains or trailing content after a seal are rejected.
Incomplete tails can be truncated only after the valid prefix and explained
destination extent pass validation. Maps remain private prototype evidence,
not an authenticated ledger or the production recovery-journal encoding.

Capacity checks use caller-available bytes from `GetDiskFreeSpaceExW`, including
quota limits, reserve source bytes plus bounded record overhead before creation,
and recheck local free space before map/data writes. Concurrent consumption,
thin-provisioned backing, remote controller capacity and later hardware errors
can invalidate that observation; actual short/error writes must retain partial
effects. Per-file `FlushFileBuffers` and readback are API-level evidence only;
successful API completion does not qualify power-loss survival, physical cache
behavior or restore readiness. These API contracts follow Microsoft's
[CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew),
[caller-available space](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getdiskfreespaceexw)
and [buffer flushing](https://learn.microsoft.com/en-us/windows/win32/fileio/flushing-system-buffered-i-o-data-to-disk)
documentation.

Test expectations must independently compare generated source/destination bytes,
map hashes and coverage, and preserve output bytes on refusal. Separately compiled
fault probes may simulate read/short/partial-write/space failures and pause at
named boundaries. A process-interruption test must observe the owned child alive,
terminate and wait for that child, and then re-open the generated files with the
same code generation. Such tests establish process behavior on the tested host,
not physical disconnection, thin-provisioning exhaustion or power-loss behavior.

## Native acquisition admission and worker integration

The next component must exercise real file acquisition in an isolated native
worker before the shared command/frontends are admitted. This remains a private
prototype under DE-W033, not a fake-counter substitute for data transfer.

Preparation returns an immutable operation definition binding the acquisition
plan, source/destination/map paths and options, exact code/host observations and
an explicitly selected existing operation-state directory with its generation
and fixed metadata-file effects. It creates no outputs or state files. A separate
grant binds that full definition digest and source-read, destination-write,
map-write and host/state effects. Preserve the reviewed capture epoch when
reobserving in another process, and refuse a changed definition before effects.
The command catalogue's requires_plan flag applies to acquisition execution;
metadata-only preparation is not execution or generic privileged plan.apply.

Admission persists immutable request/grant evidence with CREATE_NEW in the
owned empty state directory, then starts the same executable's private role
with only explicitly inherited input/append-record/cancel-read/event handles.
Source paths travel as bounded data, never as executable instructions. Validate
handle types, file paths/identities, host/code/directory generations, job membership
and budget before data effects. Metadata resources must not alias any planned
source/image/map or execution dependency. An existing admission is observed,
not relaunched; missing/partial evidence yields unresolved/refused state without
cleanup or a replacement writer.

This Windows prototype shares the existing owner/host aggregate limit of four
workers, 128 MiB per process and 512 MiB per job; each attempt additionally has a
one-process job. Closing a frontend/job handle must not kill a worker. The private
aggregate object retains its historical `DiskEd.Fake.Workers.v1` name; that name
neither restricts the new worker to fake data nor supplies storage authority.
Admission observation is bounded to three seconds. Exceeding it returns unknown
with the retained operation ID; it supplies no execution deadline or restart
permission. Operation history is bounded to 64 records, 16 KiB per record and
1 MiB total, using at most 32 coarse checkpoint observations plus startup/terminal
states. Preserve incomplete/corrupt records unchanged on reconnect.

The worker must survive frontend exit, retain an operation ID, random worker and
attempt epochs plus PID/creation-time observations, and record bounded ordered
states with exact definition bindings. Progress comes only from verified,
map-flushed checkpoints. Operation records use a finite coarse progress budget;
the acquisition map remains authoritative for individual ranges. Cancellation
is a request until observed at a checkpoint; it cannot declare a hung call
quiescent. The terminal record is written after the synchronous provider session
returns and releases its resource handles. Unknown, reused or exited-without-
terminal worker observations do not authorize restarting it.

The private acquisition record format advances to version 2 to retain original
capture provenance outside the immutable plan: capture epoch, first attempt ID,
clock kind and observed start. Unobserved fixture clocks remain null; Windows
FILETIME values are host wall-clock observations, not authenticated time. Each
file attempt separately reports start/end FILETIME, monotonic elapsed time and
wall-clock regression. Resume preserves the original header evidence and adds
the current attempt receipt. Version 1 maps retain their existing reader/code
generation; no automatic cross-generation admission is implied.

Checkpoint/stop callbacks are private owned-worker ports. A checkpoint callback
runs only after destination flush/readback and successful checkpoint map flush;
failure to retain its operation record must not invent a completed operation.
The first tests must demonstrate actual generated-file bytes, exact review/grant
refusal, disconnect/reconnect, active-worker exclusion, checkpoint cancellation,
late startup and incomplete worker evidence. Real power loss and other platforms
remain separate qualification. Public CLI/stdio/GUI/TUI/shell availability waits
for their own integration and evidence.

## Provisional shared acquisition request contract

The next native command adapter uses the canonical `image.acquire` descriptor
and shared parameter schema. `phase=prepare` binds source, destination, map,
state_directory and optional resume/chunk/read/retry/substitution policy. It reads
metadata and existing resume-header evidence only and returns the full immutable
operation definition and digest without creating outputs or state files. No grant
or execution-only field is accepted during preparation. Defaults remain 65536-byte
chunks, no retries, ordinary reads and stop-on-error; resume without explicit
policy derives the original map's effective options. Definition request options
are always resolved and marked explicit. Metadata preparation is not source-byte
acquisition, plan approval or effect authority.

`phase=execute` accepts only that definition, its exact definition_digest and
four separately supplied true booleans: allow_source_read, allow_destination_write,
allow_map_write and allow_host_effects. It cannot accept replacement paths/options
alongside the reviewed definition. Require resolved request options to agree with the inner plan. Validate the complete typed definition, inner
plan and full digest before invoking the platform effect port. Missing, mixed,
unknown or wrongly typed fields cannot initialize a provider or create state.

CLI forms are `image acquire prepare SOURCE DESTINATION --map MAP --state-dir DIR`
and `image acquire execute --definition-json JSON --definition-digest SHA256`
with all four corresponding `--allow-...` flags. The definition option is parsed
as bounded JSON data, never executed or expanded. Stdio supplies the same typed
object directly; frontend form decoding uses the same schema and strict parser.
Limit the definition to 16 KiB of canonical JSON, depth 20, 2048 values and
1024 bytes per string; the text decoder additionally bounds its original input.
Duplicate keys, invalid encoding, unknown fields and excess nesting are refused.
Use compact JSON in text editors; a visual review and actual effect grant remain
separate actions. Generic request plan_digest/idempotency fields remain reserved
for their owning broker contract and do not substitute for this grant.

A failing-read-mostly preparation permits only zero retries. Repeated execution
observes its original attempt, with no implicit replacement. A completed transfer
reply must retain the exact reviewed definition/binding and complete, certain
coverage counters.

The shared adapter returns the standard response envelope and existing exit
classes: preparation/completed execution 0, invalid parameters 2, pre-admission
refusal 3, terminal incomplete/failed execution 4, accepted_running 5 and unknown
admission 6. Accepted-running carries a valid operation ID and an active,
nonquiescent observation; a pre-admission refusal has no operation identity or
execution state. A paused
execution has not met the requested complete-image postcondition and returns
failed/incomplete with its independent paused/quiescent outcome retained; it is
not represented as completed copying. An inspection/cancellation request is a
completed observation independently of the saved operation outcome. Explicit
substitution completion retains its quality class and map; it does not certify
the original source or restore readiness.

Keep a returned identity and state-directory/digest recovery coordinates when
post-invocation reply validation fails. An exception after an execution port is
invoked produces unknown, never a fresh refusal/retry opportunity. Pin executable
parents separately through launch when state and code directories do not share
ancestors. The first adapter is tested through a private native probe before
linking it into the product; static syntax definition alone grants no availability,
stable API admission or complete frontend integration.


## Provisional acquisition operation observation contract

The common operation inspect/cancel/watch commands distinguish `fake-op:` and
`image-op:` identities explicitly. Never guess an operation kind from directory
contents or open another kind's metadata as a fallback. Inspection is a completed
read independently of an active/paused/failed operation; cancellation is a
persisted request until a verified checkpoint reports its outcome.

Acquisition watch uses the separately negotiated
`org.disked.acquisition-operation-events/1` feature. Its ordinary event envelope
carries acquisition.operation.record or acquisition.operation.snapshot and an
`org.disked.acquisition-operation-event/1` payload with request/observer identity
and the actual immutable acquisition worker record. Fake counters are not real
byte progress. A reader obtains the complete definition from its exact admission
or an inspection first, checks its digest and uses that definition to validate
record bindings, total coverage and outcome relationships. An event alone is not
an execution grant or a complete acquisition definition.

Sequence is one-based within the immutable operation/attempt/worker domain;
reconnect after a nonzero sequence requires that worker epoch and the exact
record digest. Full replay checks the retained record chain before projection.
A snapshot is explicit and incompatible with a nonzero cursor. Duplicate exact
records may be ignored; gaps, conflicting duplicates, changed epochs/definitions
or a future cursor are refused without advancing the client's accepted cursor.
Original capture and attempt identities remain distinct from observer identity.
Within an accepted stream, the complete worker binding is immutable, checkpoint
coverage cannot regress, and a terminal record cannot be followed by another
state. A valid record hash alone does not establish these relationships.

An acquisition event is bounded to 32 KiB; each retained record still has the
16 KiB/depth-20/2048-value/1024-byte-string bounds. The shared queue permits at
most 64 events and one MiB total without waiting for a consumer. Follow time
is 0..2000 ms; a bounded watch ending on an active worker returns accepted_running
with its operation ID. A terminal watch is a completed observation even when
copying failed or paused. CLI/stdio response batches retain the existing one MiB
wire limit, including LF. Their acquisition-watch request slot explicitly selects
that finite response bound; other calls retain the 64 KiB default. Interactive response admission remains separately bounded and needs
its own size/rendering qualification before complete acquisition frontend claims.

Torn or corrupt evidence remains unknown and unchanged. Preserve the last
validated state/cursor already delivered when later observation fails. Closing
an observer or failing its output does not cancel, restart or remove a worker's
recovery dependencies. Watching has no source/destination/map effect handles.
Provisional event support does not freeze the production journal or admit the
acquisition command before its visible review/submission checks.

## Phase-specific acquisition forms

GUI/TUI acquisition editors derive their phase and fields from the canonical
parameter schema. The discriminator is first and defaults to prepare. Prepare
shows only source/destination/map/state and acquisition options; execute shows
only the full definition, digest and four separate effect grants. An unknown or
empty phase shows only its discriminator and cannot be reviewed successfully.
Changing phase clears all other values, grants and review. No phase switch or
preparation result implicitly enables execution or supplies an effect grant.

Structured definition editors accept at most 16 KiB of compact JSON text, then
use the common strict object decoder and its independent canonical bounds.
Other editors retain their 4096-byte limit. Oversized, malformed or control input
cannot authorize a previous valid definition. Review displays the complete typed,
escaped request; a separate fresh submission consumes that review. Preparation
may be submitted independently without any output-file or effect admission.
Paging and navigation neither truncate values nor submit an operation.
The fake inventory's graph revision is not an acquisition precondition. Review
must not present it as authority or freshness for the independently bound files.
