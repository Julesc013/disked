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
  version: 0.1.16-proposed.1
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
  at: '2026-10-06T17:56:37.383921+00:00'
  scope: DE-W012/017 bounded fake event watch and frontend parity; owner acceptance pending
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

Every `accepted_running` response includes a nonempty durable `operation_id`. A completed bounded read may have `operation_id: null`. Event sequence is an exact decimal u64 and semantic validation is selected by schema identity. Sequence alone is not freshness: the DE-015 fake profile binds operation/attempt/worker identities; production asynchronous admission must also define capture epochs and event sequence domains. Late results cannot overwrite a newer observation or imply an uncertain writer stopped. Typed event payloads and resource bindings are DE-W012/017/033 gates, not inferred from the generic envelopes.

## DE-W012 synchronous admission contract

The first native protocol admits `build.inspect`, `command.list` and
`protocol.serve` (the latter selects transport, and is never recursively accepted
as a request). `mode.explain` is admitted only with a real host-observation adapter.
DE-W013 additionally admits the four fake observation commands defined in
[DE-023](presentation.md). Other descriptors stay unavailable regardless of
successful syntax recognition.
That initial DE-W012 slice is a provisional synchronous implementation. Its
completed/refused reads have `operation_id: null`. DE-W016 subsequently adds the
fake-operation commands and retained identities defined by DE-015; the current
composition can emit `accepted_running` and `unknown` for those commands. It does
not invent a durable operation for a bounded read or an unadmitted callback.

`disked protocol serve --format=json` reads one UTF-8 request from stdin to EOF and
writes one compact response plus LF. `--format=ndjson` reads one request per LF
(an optional preceding CR is framing); each response is flushed before reading
the next request. A final nonempty unterminated line at EOF is accepted. An empty NDJSON session ends successfully without a response. Empty
lines, oversized frames and malformed input are refused. Human-format transport
and interactive/GUI/TUI transport combinations are invalid. Transport uses only
the supplied standard handles, never a listener or file named by a request.

The native profile caps one request at 65,536 bytes, nesting at 32 containers,
values at 8,192 and one decoded string at 32,768 UTF-8 bytes. A session has at most
256 requests and 4,194,304 input bytes. Responses have a 1,048,576-byte cap. Bounds
include whitespace/framing bytes as applicable and are checked before unbounded
allocation. Nonfinite numeric conversions, duplicate decoded object keys,
invalid UTF-8, lone surrogates, BOMs and trailing non-whitespace data are refused.
Large exact counters and geometry remain bounded decimal strings.

Requests use the existing strict request schema, with nonempty UTF-8 request IDs
of at most 128 bytes, and no NUL. The synchronous handlers support no required
feature tokens; a nonempty `required_features` array is `unsupported_feature`,
except the explicitly negotiated operation-watch extension below.
Unknown top-level request fields are `invalid_request`. Plan digests and
idempotency keys are rejected on the synchronous handlers. DE-W013 observation
commands admit an optional `expected_revision`; other commands reject that
field as `unexpected_revision`. Parameters follow each descriptor's declared
schema: inspect requires target ID and capability explanation requires target
ID plus operation ID; the other admitted reads require empty parameters. A malformed request uses correlation ID `@unparsed`;
a structurally valid request preserves its supplied ID when refused.

Response consumers validate known fields and preserve unknown observational
fields; producers emit the exact known response shape. An unknown status, schema
version or required feature is incompatible, never success. The DE-015 fake-operation profile has its own tested identities. Production
asynchronous storage admission remains a separate gate. The fake-only watch
extension below defines its own typed records, operation/attempt/worker domain,
observer epoch and event negotiation; this does not admit a production journal.

Native process outcomes: 0 completed; 2 invalid arguments/message/schema; 3
unavailable command/frontend/feature; 4 output/internal failure; 5 accepted and
still running; 6 unknown outcome; 7 recovery required. Codes 5 and 6 are emitted
by the DE-W016 fake-operation extension; 7 remains a tested reader mapping until
an admitted handler requires it.
NDJSON continues after a bounded, well-framed refused request and returns the
maximum exit class encountered, including retained unknown/accepted-running
observations from fake operations. A transport failure still returns 4 because
delivery failed; that exit is not a claim that an operation failed or rolled back.
Framing/resource-limit failure ends the stream. A write failure is never success.
CLI-generated requests use correlation ID `cli`; help results are observational
objects in the same response envelope. Human diagnostics stay on stderr; machine
results and diagnostics occupy only their framed stdout response.

The native argv adapter preserves Windows UTF-16 tokens as strict UTF-8. Static
completion only suggests descriptor words/options; it never dispatches or performs
identifier discovery. DE-W011 supplies channel observations and policy routing for this Windows lane.
DE-W014 and DE-W015 add explicit native console and Win32 frontends. Explicit CLI prompt permission
requires verified console input/output; no synchronous handler actually prompts.

The current broad programme grant permits local continuation after recorded
tests and agent review. It does not create owner acceptance or expand host/storage
authority. The grant and exact source scope are retained in the repository's
development programme record.

## DE-W017 bounded request waiting

The Windows fake composition selects a 4,000 ms frontend wait for a validated
ordinary-file fake-operation call (`plan.simulate`, `operation.inspect` or
`operation.cancel.request`). This bounds waiting for the owned callback, not a
promise that Windows can cancel a blocked file API. There is one background call
and one completion slot per CLI/stdio process, as in the interactive frontends.
Only immutable request data enters that callback. Built-in and cached graph
commands do not enter the file-call channel.

Expiry returns `unknown`, exit class 6, with the original request ID and diagnostic
`request_wait_expired`. It includes the operation ID only when already known from
the request; otherwise `operation_id` is null and the result retains the explicit
state directory for reconciliation. Expiry does not cancel, replace, restart or
prove completion of the call. The CLI can return while an admitted worker retains
its independent lifetime and immutable claim. Incomplete admission can remain
unresolved. Absence of an observed record is not permission to switch stores and
repeat the operation.

NDJSON continues to serve built-in/cached requests. While a timed-out call is
still outstanding, another file call is refused as `request_resource_limit`
(exit class 3), without invoking its handler or touching its state directory.
When that callback actually completes, its late observation is consumed locally;
no unsolicited second response is emitted for the old exchange, and it never
becomes a response to a new request. The completion observation does not replace
operation truth: fake-worker records remain in the selected store and explicit
reconciliation uses DE-015's exact immutable claim. The same fake start against
an existing claim only inspects it; no new worker is spawned. A new explicit call
can use the channel only after the previous callback has completed. There is no
automatic retry or implication that an uncertain worker is quiescent.

The retained criteria are a 4 s callback wait plus a 1 s local scheduling/output
allowance in finite synthetic-delay tests, an immediate refusal for a busy slot,
continued cached responses, no duplicate late response and no duplicate effect.
An unavailable thread is `request_thread_unavailable` (exit class 3) before the
callback runs. Slow output consumers require a separate transport-write bound;
these request criteria do not qualify blocked output, arbitrary drivers or other
hosts. No public timeout tuning option is admitted by this prototype.

## DE-W012/017 fake operation-watch execution contract

`operation watch <operation_id> --state-dir <directory>` admits observation of
one existing DE-015 fake operation. It never creates a claim, worker, cancellation
flag or storage effect. Optional `--after-sequence <u64>` defaults to `0`;
a positive cursor requires `--worker-epoch <worker:32-lowercase-hex>` and
`--after-digest <64-lowercase-hex>`, the last validated record digest. The attempt
is fixed by the operation ID plus `:attempt:1` in this profile. `--snapshot` starts
from the latest validated record instead of replaying the retained prefix and
cannot accompany a positive cursor. `--follow-ms` is a decimal string from 0 to
2000, default 0. It bounds observation following, not a blocked file API. Parameter
relationships are checked before opening the state directory.

The observer validates the immutable claim, host/directory binding and complete
bounded record chain exactly as inspection does. It checks a supplied worker
epoch even at cursor zero. A wrong epoch is `watch_epoch_mismatch`; a cursor above
the observed sequence is `watch_cursor_ahead`; a mismatched retained digest is
`watch_cursor_conflict` (exit 2). None starts a replacement.
This prototype retains all of its at most 64 records; no successful empty batch
represents an unreadable, truncated or corrupt history. Such a failure is unknown
with its reason and the last validated observation, without tail repair.

Events use the existing `org.disked.event/1` envelope. Types
`fake.operation.record` and `fake.operation.snapshot` carry a typed
`org.disked.fake-operation-event/1` payload: request correlation, fresh observer
epoch, and the exact hash-chained record. Top-level operation ID and sequence must
match the record's immutable binding and decimal-u64 sequence. The operation,
attempt and worker domain orders records; the fresh `watch:` observer identity
binds one request and is not a new operation/attempt or writer generation.
A snapshot deliberately establishes a new reader cursor. Record events are
contiguous after that cursor; a gap, conflicting duplicate, regressed sequence or
changed operation/attempt/worker requires explicit resnapshot/reconciliation.
Reconnect repeats watch with the last fully validated sequence, digest and worker epoch,
or requests `--snapshot`. No receipt implies delivery of a partial output line.

Watching starts with available records and polls at 25 ms intervals until a
terminal state, unknown observation, or the requested follow budget. It uses one
owned callback and a finite queue of at most 64 events/1 MiB total, with a 16 KiB
event bound; no producer waits on the consumer. The complete validated fake store
retains operation truth independently. Queue exhaustion ends observation with an
explicit error, never a successful gap or dropped durable outcome. A future
production retention policy needs its own admission contract.

JSON, human and interactive views receive one bounded response containing events,
the final inspected state, observer identity and last emitted sequence. A live
nonterminal operation at the follow boundary is `accepted_running` (exit 5); a
completed observation of a terminal operation is `completed` (exit 0), even when
the operation outcome is verification failure. Unknown stays exit 6. These are
observations, not acceptance of a new operation. CLI/stdio callback waiting retains
DE-017's 4 s limit and occupied slot until actual completion. Interactive frontends
return pending immediately and preserve cached navigation; their occupied request
slot remains pending until the callback actually completes.

Direct CLI `--format=ndjson` explicitly selects event frames followed by one final
response. NDJSON protocol clients opt in only for `operation.watch` using the
single required feature `org.disked.fake-operation-events/1`. Without it, the
existing one-response behavior is preserved, including the bounded event array.
The feature on JSON transport or another command is refused before store access;
unknown or duplicate feature tokens are refused. The streaming final response
has an empty event array and the same cursor/state metadata, avoiding retransmitting
events. Request processing remains sequential; no unsolicited late event may
follow its final response or become part of the next exchange.

The frontend thread drains the queue and owns output; callbacks hold only immutable
inputs and shared observation state, never UI/output references. The existing 3 s
output bound applies to each frame. A failed stream is sealed, returns exit 4,
and dispatches no subsequent queued request. Closing a client or failing output
cannot cancel, terminate or replay the worker. A callback timeout closes only its
observation queue and returns unknown; a still-running file call retains its slot.

Producer schemas are strict. Compatible readers preserve additive top-level and
payload observational fields, but reject unknown schema/type/required features,
invalid wide counters, inconsistent identities, record hash failure and illegal
fake-operation state. These fake records remain provisional, unauthenticated
review encodings; this does not admit production journals, remote transport,
privileged providers or new storage authority.

Acceptance requires native record/cursor validation, actual live NDJSON events,
reconnect and snapshot recovery, terminal/unknown/cancellation/verification-failed
outcomes, bounded follow and output, malformed history, reader evolution and
cached GUI/TUI/shell responsiveness. Expected behavior here precedes implementation.

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
