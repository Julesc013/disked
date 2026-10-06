---
type: DiskEd Specification
title: FrontendSession and semantic parity
description: One presentation model for terminal and native visual interfaces.
resource: disked://spec/de-023
tags:
- disked
- interaction
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-023
  profile: disked-spec/1
  version: 0.1.6-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-021
  - DE-022
  requirements:
  - DE-REQ-023-01
  - DE-REQ-023-02
sources:
- id: ulk-readme
  resource: ../references/sources.json#ulk-readme
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
- id: review-08a8246-2026-10-04
  resource: ../references/sources.json#review-08a8246-2026-10-04
updated:
  by: codex
  at: '2026-10-06T10:34:13.961789+00:00'
  scope: DE-W013 private fake graph/service execution contract; owner acceptance pending
---

# FrontendSession and semantic parity

## Service contract

A frontend queries immutable `PresentationSnapshot` values, submits typed actions with an expected revision, observes `ActionReceipt` and durable `OperationProjection`, and asks for a `CapabilitySnapshot`. The service owns available actions, readiness, safety explanations and recovery state. UI-local selection, filtering, scroll positions and expanded nodes are not storage state.

`query(scope, freshness)`, `act(action, revision, request_id, idempotency_key)`, `inspect(operation_id)` and `cancel(operation_id)` are logical APIs, not a premature ABI commitment. The same semantics must pass direct-call and process-transport tests. Do not depend on Universal Launcher at runtime merely to obtain a common interface pattern.

## Parity contract

Replay an action transcript against the same initial fake graph through CLI request, TUI event reduction and GUI view-model action. Compare normalized action receipts, plan digests, final graph and refusal codes. Navigation and pixel output may differ. A frontend cannot mark a cancelled or successful state because an animation stopped. Stale views must surface revision conflict and offer refresh, never silently rebase destructive intent.

## Advanced reachability

Design common journeys deliberately: inventory, topology, health, acquire, plan, verify, recover and evidence. A generated command explorer makes all eligible advanced operations reachable, but does not replace task-oriented design. Accessibility needs tree/table equivalents of partition diagrams, full keyboard control, high contrast and meaningful announcements. Colour is supplementary information.

## DE-W013 fake service execution contract

The first service is a private C++14 API, with immutable, shared graph snapshots
and typed `Inspect`, `Select` and `ClearSelection` actions. It is confined to
compiled fake observations. No device discovery, filesystem reads, storage
effects, durable operation or authorization is implied. CLI and stdio use this
same service; GUI/TUI parity remains an implementation gate for those adapters.

Every action supplies the exact current revision. An empty or unequal revision
returns `revision_conflict` (exit 2), before target lookup or selection changes.
Inspect and select require an exact target ID. Missing IDs return
`target_not_found` (exit 2). Selection stores identity, never a row index. Refresh
preserves that identity; if it disappears, the selection is reported `missing`
with its original ID until explicitly cleared or replaced by a new selection.
Reordering, cloned serials, aliases and replacement media cannot select a row
implicitly. Reusing an ID with a different identity is a provider error. A
failed refresh leaves the prior snapshot and selection intact. Retained old
snapshots never change. Selection changes do not change storage revision.

Snapshots use `org.disked.graph/1` with the stricter private producer profile
`urn:disked:schema:fake-graph:1` (`schemas/fake-graph.schema.json`). In this development profile their revision
is SHA-256 of the compact UTF-8 JSON object with sorted keys, ordered arrays,
no whitespace and no `revision` field. String encoding uses `\"` and `\\`
for quote and backslash, lowercase `\u00xx` for every U+0000..U+001F code point
(including newline; no short escapes), and literal UTF-8 for all other code
points. Slash is unescaped. Keys in this profile are ASCII; arbitrary numeric
JSON lexemes are absent. Capture ID includes a monotonically
increasing service-local capture epoch; identical bytes in a new capture
therefore have a new revision. This is a private review encoding, not the
production plan encoding or a durable identity across runtime restarts.
The compiled fixture restarts deterministically at capture `fake:1`.

Bounds are 64 nodes, 256 edges, 64 omissions, 256-byte IDs/kinds/references,
4096-byte labels, 64 KiB graph JSON, and 1024 distinct identities retained per
service. Unknown node state, invalid UTF-8, duplicate node IDs, dangling edges,
invalid identity/quantity fields or exhausted bounds reject the capture.
Resource cycles and multiple parents remain legal. Publication is sequential
in this slice; a future concurrent provider adapter must serialize publication
and action admission at the same boundary.

Each node has exact string identity, positive decimal-u64 media generation,
label, observation state (`current`, `denied`, `stale`, `unknown`), up to 64
aliases, and decimal-u64 capacity bytes. Unobserved capacity is null, never a
fabricated zero; only a non-current observation may omit capacity. All nodes
carry `scope: fake-only`. Aliases and cloned labels never replace composite
identity. Empty labels are legal. Identity/reference strings exclude NUL.

The admitted commands are `target list`, `target inspect <target_id>`,
`topology show` and `capability explain <target_id> <operation>`. The first
returns the complete graph plus ordered target IDs; topology returns the graph;
inspect returns cached node observations and capture/revision. Denied, stale
and unknown observations remain inspectable as explicitly labelled cached data.
Capability explanation returns the existing ten-dimensional assessment for a
catalog command ID. Qualification stays `unknown`, execution eligibility false,
and authorization false: fixture observation is not provider admission.
Unknown operations are refused as `operation_unavailable` (exit 3).

All four read commands accept an optional machine-envelope `expected_revision`.
An unequal value is refused without rebasing. CLI read requests capture the
current snapshot before invoking the same action; scripts needing a previously
observed revision use the envelope. Plan digests and idempotency keys remain
unavailable. Read commands do not create an asynchronous operation. Refresh,
selection and fault injection are private test/service APIs, not hidden product
commands. Essential help, build information, mode inspection and discovery
remain independent of provider initialization, including malformed read requests.

Human rendering of graph-derived data uses an ASCII JSON view: control and
non-ASCII code points are escaped, including terminal controls, bidi controls
and line separators. Machine output retains exact UTF-8 values with JSON
control escaping. Display escaping never changes identity or stored labels.
This provisional linear view does not claim screen-reader or rich-widget
qualification.

Acceptance covers snapshot retention, stale actions, removal/replacement,
clone/alias distinction, invalid refresh atomicity, cycles, finite limits,
cached partial observations, strict graph/assessment schemas, independent
SHA-256 comparisons, direct/CLI/stdio agreement and the essential-command
provider trap. Expected behavior in this section precedes implementation.
The SHA-256 implementation follows [FIPS 180-4 sections 4–6](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.180-4.pdf);
independent vectors do not establish cryptographic-module certification.

## Native composition

The Windows reference uses Win32 controls and host fonts/metrics. WinForms and WinUI are alternate target compositions; macOS uses AppKit/SwiftUI, other targets their native adapters. No toolkit initializes during headless command execution. Missing optional GUI dependencies in auto mode can degrade to terminal/plain operation; explicit GUI mode must report the precise unavailable dependency rather than silently changing meaning.

## Partial-result and dependency semantics

Every surface renders the same denied/stale/unknown capability dimensions, plan consequences and recovery state. An inventory refresh can add observations without waiting for every provider; it cannot silently change selected identity or erase outstanding errors. UI-local animation or timeout never becomes operation truth.

A runtime fallback exists only after the executable loads. Mandatory framework imports belong in the composition's loader closure; optional GUI initialization must not raise a declared headless loader floor. Availability reasons and native accessibility outcomes are tested independently of pixel equality.

## Terminal, shell and shared widgets

[Terminal sessions](terminal-session.md), [the explicit shell](interactive-shell.md) and [output/progress](output-and-progress.md) extend the existing frontend service. Tables, trees, lists, forms, plan review, operation timeline and command explorer share actions and identity-bound selection. Every rich widget has keyboard behavior and a usable linear equivalent. An action without a dedicated menu remains discoverable through the typed command explorer; it does not gain authority from a UI control.

## Normative requirements

### DE-REQ-023-01

Frontends MUST obtain eligibility and outcomes from the application service, not recalculate storage legality.

**Verification:** Parity tests compare stale-revision, refused and successful action traces.

### DE-REQ-023-02

Every visual storage map MUST have a keyboard- and assistive-technology-usable structured equivalent.

**Verification:** Accessibility inspection and native screen-reader qualification.

## Related specifications

- [DE-021](commands.md)
- [DE-022](protocol.md)
