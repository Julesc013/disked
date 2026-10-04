---
type: DiskEd Specification
title: Machine protocol and transport
description: Versioned envelopes, bounded messages and honest operation outcomes.
resource: disked://spec/de-022
tags:
- disked
- interaction
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-022
  profile: disked-spec/1
  version: 0.1.2-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-021
  - DE-010
  requirements:
  - DE-REQ-022-01
  - DE-REQ-022-02
updated:
  by: codex
  at: '2026-10-04T06:41:03.817694+00:00'
  scope: 08a8246 review corrections; proposed, not accepted
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
- id: review-08a8246-2026-10-04
  resource: ../references/sources.json#review-08a8246-2026-10-04
---

# Machine protocol and transport

## Bootstrap transport

The initial machine transport is UTF-8 JSON for bounded request/response and NDJSON for event streams. Each line is one complete JSON value with a declared envelope schema. Reject duplicate JSON keys, invalid UTF-8, unbounded nesting, overlarge frames and nonfinite numbers. A single response is capped by profile; page large inventories. Use decimal strings for u64/large byte values and validate range semantically, not just with a digit regex.

Requests identify schema version, request ID, command ID and typed parameters. Mutating requests add plan digest, expected revision and idempotency key. Results distinguish refused, completed, accepted-running, failed, unknown and recovery-required. Error fields carry stable code, message key, parameters, platform error and safe remediation. Unknown critical request features are refused. Additive observational response fields may be retained by older readers.

## Operation identity

A request ID correlates one exchange. An operation ID outlives connections. Attempt IDs identify retry/dispatch attempts. Idempotency is bound to a canonical semantic request digest and scope; a reused key with different content is a conflict. A broken connection after dispatch does not prove cancellation, failure or success. Reconnect by operation ID and inspect retained state. Cancellation is a request with a receipt and a safe checkpoint; it is never immediate proof of no effect.

## Framing and ordering

Events carry sequence number, operation ID, type and typed payload. Sequence gaps are detectable; clients can resume from the retained sequence or request a fresh snapshot. Wall-clock time is informative, not the event ordering authority. Enforce quotas and back-pressure. Slow observers must not delay journal durability or raw storage operations indefinitely.

## Security

Stdio is suitable for a spawned unprivileged provider or client. It is not authentication by itself. Elevated IPC requires target-specific peer authentication, restrictive access, fresh session binding and bounded messages. Never accept arbitrary shell text as an execution plan. Bulk images and block data use separately authorized bounded handles or streams. Do not expose a network listener in the first product; future remote control needs a separate threat model.

## Bounded observations and evolution

Partial responses retain per-source freshness, omission and failure reasons; an unavailable contributor is not a successful empty list. Backpressure may coalesce replaceable progress only with detectable sequence loss and an explicit snapshot recovery route. Durable outcomes and journal transitions cannot be dropped to keep a view responsive.

Use decimal strings for exact wide counters/ranges. Required mutation features are negotiated and unknown critical fields refused before effects. Product, protocol, plan, journal and target versions evolve independently. A remote session requires separate authenticated policy, explicit host/job identity and reconnection semantics; the initial product has no network listener.

## Producer conformance, reader evolution and identities

The current request/response/event JSON Schemas are **strict producer-conformance review contracts**. Their `additionalProperties: false` rules are not a claim that every compatible older observational reader must reject every new field. DE-W012 must define versioned reader fixtures: safely ignorable/preserved observational extensions, unknown required-feature refusal, and limits before claiming a stable API. Mutation requests remain strict; unknown critical fields or required features cannot be ignored.

Every `accepted_running` response includes a nonempty durable `operation_id`. A completed bounded read may have `operation_id: null`. Event sequence is an exact decimal u64 and semantic validation is selected by schema identity. Sequence alone is not freshness: before native asynchronous protocol admission, define operation, attempt, worker/capture epochs and sequence domains. Late results cannot overwrite a newer observation or imply an uncertain writer stopped. Typed event payloads and resource bindings are DE-W012/017/033 gates, not inferred from the generic envelopes.

## Normative requirements

### DE-REQ-022-01

Machine messages MUST be bounded, versioned and reject duplicate keys or unknown required features.

**Verification:** Protocol malformed-message suite plus maximum-size cases.

### DE-REQ-022-02

Retry and cancellation MUST preserve operation/attempt identities and distinguish an unknown outcome from a completed one.

**Verification:** Disconnect after dispatch, reconnect and assert no duplicate effect or fabricated cancellation.

## Related specifications

- [DE-021](commands.md)
- [DE-010](../architecture/system.md)
