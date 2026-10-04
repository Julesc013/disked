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
  version: 0.1.1-proposed.2
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
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
---

# FrontendSession and semantic parity

## Service contract

A frontend queries immutable `PresentationSnapshot` values, submits typed actions with an expected revision, observes `ActionReceipt` and durable `OperationProjection`, and asks for a `CapabilitySnapshot`. The service owns available actions, readiness, safety explanations and recovery state. UI-local selection, filtering, scroll positions and expanded nodes are not storage state.

`query(scope, freshness)`, `act(action, revision, request_id, idempotency_key)`, `inspect(operation_id)` and `cancel(operation_id)` are logical APIs, not a premature ABI commitment. The same semantics must pass direct-call and process-transport tests. Do not depend on Universal Launcher at runtime merely to obtain a common interface pattern.

## Parity contract

Replay an action transcript against the same initial fake graph through CLI request, TUI event reduction and GUI view-model action. Compare normalized action receipts, plan digests, final graph and refusal codes. Navigation and pixel output may differ. A frontend cannot mark a cancelled or successful state because an animation stopped. Stale views must surface revision conflict and offer refresh, never silently rebase destructive intent.

## Advanced reachability

Design common journeys deliberately: inventory, topology, health, acquire, plan, verify, recover and evidence. A generated command explorer makes all eligible advanced operations reachable, but does not replace task-oriented design. Accessibility needs tree/table equivalents of partition diagrams, full keyboard control, high contrast and meaningful announcements. Colour is supplementary information.

## Native composition

The Windows reference uses Win32 controls and host fonts/metrics. WinForms and WinUI are alternate target compositions; macOS uses AppKit/SwiftUI, other targets their native adapters. No toolkit initializes during headless command execution. Missing optional GUI dependencies in auto mode can degrade to terminal/plain operation; explicit GUI mode must report the precise unavailable dependency rather than silently changing meaning.

## Partial-result and dependency semantics

Every surface renders the same denied/stale/unknown capability dimensions, plan consequences and recovery state. An inventory refresh can add observations without waiting for every provider; it cannot silently change selected identity or erase outstanding errors. UI-local animation or timeout never becomes operation truth.

A runtime fallback exists only after the executable loads. Mandatory framework imports belong in the composition's loader closure; optional GUI initialization must not raise a declared headless loader floor. Availability reasons and native accessibility outcomes are tested independently of pixel equality.

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
