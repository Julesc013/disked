---
type: DiskEd Specification
title: Journal, recovery and durability
description: Explicit recovery classes without false transactional or rollback claims.
resource: disked://spec/de-043
tags:
- disked
- safety
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-043
  profile: disked-spec/1
  version: 0.1.4-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-042
  - DE-041
  requirements:
  - DE-REQ-043-01
  - DE-REQ-043-02
  - DE-REQ-043-03
updated:
  by: codex
  at: '2026-10-08T21:31:19.658481+00:00'
  scope: DE-W040 separate definition/receipt payload binding and recovery properties; guarded durability/effect work remains incomplete
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
- id: review-08a8246-2026-10-04
  resource: ../references/sources.json#review-08a8246-2026-10-04
---

# Journal, recovery and durability

## Recovery semantics

Classify each operation as atomic-metadata (only when proven), replayable, resumable, rollback-capable, forward-recovery-only, irreversible-after-step, backup-required or forensic-best-effort. These can combine with precise scope. A small journal does not retain the original contents of a multi-terabyte overlapping move. Once overwritten bytes are absent from all backups, metadata cannot reconstruct them.

## Required journal properties

The eventual on-disk journal needs magic, exact encoding version, target and plan identities, provider closure, sequence, record kind, bounded payload length, checksums and explicit commit/seal behavior. Its parser rejects truncated, reordered, mismatched or unsupported critical records. A durable authorization/intention record precedes a bounded external effect; a verified completion record follows required target flush and recapture. A crash between effect and completion produces uncertain state requiring observation, not blind replay.

This baseline intentionally does NOT freeze a new binary journal encoding before the storage/durability spike. `DE-DEC-004` blocks production writer implementation until exact byte layout, torn-write handling, checksum, sector assumptions, flush guarantees, recovery algorithm and fault model are reviewed. `catalog/journal-model.json` defines state transitions for design tests; it is not a runtime journal or evidence that a power-loss test passed.

## Placement and retention

Store the journal/recovery capsule on a different physical resource or an explicitly owned area proven outside affected extents and failure domains. Alignment gaps are not free space. Record storage independence limitations: another partition on the same failing disk is not an independent backup. Keep the exact recovery-compatible provider closure reachable without network dependence. Redact secrets while preserving references needed by the operator.

## Recovery capsule

Include reviewed plan, original map/boot metadata, target identity, expected states, journal bootstrap, tool hashes, verifier contract, required backup references and human procedure. Verify the capsule before admitting a high-risk step. Recovery reidentifies the disk after reboot and refuses ambiguous matches. Signed or hashed capsules do not make their operation correct; they bind what was reviewed.

## Cancellation and flush

There is no universal cancellation point or atomic GPT switch. Mark safe checkpoints by operation, and distinguish user cancellation request from confirmed quiescence. Flush is a provider capability whose guarantees depend on stack and hardware. Successful API return may not prove power-loss persistence; qualification must describe cache/controller assumptions and physical tests where claimed.

## Lifetime and generation retention

Timeout, client loss or cancellation request does not seal an unobserved effect. Preserve the affected target's quarantine and exact journal/provider/executor identities until quiescence and postconditions are established. A replacement worker cannot blindly replay. Software maintenance must retain required generations, including when the operation is unreachable, until reconciliation permits retirement.

The recovery closure includes independent code access, state, reconstruction data, credential references and physical dependencies. Configuration caches and another partition on a failing disk do not meet an independent-backup requirement. DE-DEC-004 remains unresolved: state-model checks do not prove durable runtime encoding or power-loss safety.

## Independent recovery properties and operation dimensions

The prototype plan's scalar recovery summary is insufficient for executable writers. Before DE-W040/041, define per-step resumability, backup dependence, cancellation checkpoints and irreversible boundaries, and derive a conservative plan summary. These properties can coexist; do not enumerate every combination into another scalar status.

Separate logical operation state, execution attempt, worker liveness, effect certainty, cancellation request/acknowledgement and recovery state. The current `catalog/journal-model.json` is an unguarded design graph only; reachability does not prove legal transitions. DE-W017 adds guarded fake scenarios with operation/attempt IDs, capture and worker epochs, sequence domains and explicit ownership transfer. Cover old worker late completion, client disconnect/reconnect, cancellation followed by normal effect completion and failed verification. Starting another observer cannot retire a possibly active writer or release its dependencies.

## DE-W040 private binary codec proposal

The first native spike is `source/runtime/journal/codec.*`, a private C++14
codec exercised by `journal_codec_probe`. It is **not linked to disked.exe** and
offers no file writer, effect dispatch, tail repair or production admission.
[The exact profile](../catalog/journal-prototype.json) owns the byte layout.
All multibyte integers are unsigned little endian; payloads are opaque bytes.
No native struct layout, JSON canonicalization or sector atomicity is assumed.

The 192-byte file header starts with ASCII `DEJPR001`, format major/minor 1/0,
header length 192, zero flags and payload limit 65536. It binds a nonzero 16-byte
journal identity and three nonzero 32-byte digests: immutable plan definition,
participating target identities/epochs and provider/executor closure. Bytes
136..159 are zero. SHA-256 of bytes 0..159 occupies bytes 160..191. Supplied
expected bindings must match exactly before any record is visited. They must
come from independently established plan/resource/code observations, not from
the untrusted header itself; this codec cannot establish their authority.

Each record has a 112-byte prefix, a payload of 0..65536 bytes, and a 32-byte
trailer. Prefix fields are ASCII `JREC`, kind/flags (u16 each), prefix/payload
lengths (u32 each), sequence (u64), journal publisher identity (16 bytes),
publisher epoch (u64), previous digest (32 bytes) and payload SHA-256 (32 bytes).
Sequence starts at one and increases by one in the journal's sequence domain;
publisher identity/epoch are separate observations, not effect-worker authority.
The first previous digest is the file-header digest. The trailer hashes the
file-header digest followed by the complete prefix and payload. Hashes detect
alteration and bind context; they do not authenticate receipts or storage.

Known critical record kinds 1..9 are PlanDefinition, ReviewReceipt, Grant,
AdmissionReceipt, Intention, VerifiedCompletion, CancellationRequest,
RecoveryObservation and Seal. Their flags must be exactly one. Observation
kind 32769 has zero flags. Strict producers emit only these kinds. Compatible
readers may preserve/ignore unknown zero-flag kinds in 32768..65535; unknown
critical kinds, unknown low kinds and all other flag bits are rejected.
Observational compatibility never permits unknown mutation semantics.

The scanner visits one verified record at a time, limits a source to 16 MiB and
4096 records, and requests no read larger than 65536 bytes. It does not retain
the whole source or all payloads. Ports must return exact requested lengths;
short/oversized reads or exceptions are observation failures. A complete invalid
record, chain/order mismatch, unsupported critical record or data after Seal
is invalid, not a repairable torn tail. A partial final prefix/body/trailer is
reported as a torn tail with the last verified prefix. A partial/invalid file
header establishes no verified journal identity. Neither a verified prefix nor
an observed Seal authorizes replay, truncation, release of dependencies or a
completed logical operation. An optional semantic visitor may reject a record;
such a record does not extend the accepted prefix.

This codec qualifies byte framing and bounded reading only. The separate
`definitions.*` fake-model component now proposes exact immutable payloads,
receipt bindings and composable recovery properties under
[DE-042](planning.md#de-w040-private-immutable-definition-proposal). Definition,
resource and provider digests can supply the three header digest bindings;
review/grant/admission receipts and execution event kinds match framing kinds
1..8. No integrated semantic journal scanner or authenticated publisher exists
yet. Guarded effect/flush transitions, freshness/ownership, reconciliation and
the provider durability model remain subsequent DE-W040 work. Intention must be retained and qualified
durable before an effect; verification/required target flush precede completion.
An uncertain effect requires observation, never replay solely from codec output.
DE-DEC-004 remains proposed and blocks the production journal writer.

## Normative requirements

### DE-REQ-043-01

Every admitted mutation MUST declare its recovery class and MUST NOT claim rollback without retained reconstruction data.

**Verification:** Review overlapping-move fixture and require backup/recovery classification.

### DE-REQ-043-02

Journal encoding and durability assumptions MUST be accepted before any production journal writer is admitted.

**Verification:** Decision gate DE-DEC-004 blocks physical-write work.

### DE-REQ-043-03

Recovery MUST reidentify the target and inspect uncertain effects instead of blindly replaying unsealed steps.

**Verification:** Crash-at-every-transition model and target-swap tests.

## Related specifications

- [DE-042](planning.md)
- [DE-041](broker-and-authorization.md)
