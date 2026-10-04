---
type: DiskEd Specification
title: Extension tiers and compatibility
description: Stabilize real C/protocol consumers and require conformance without granting implicit privilege.
resource: disked://spec/de-078
tags:
- disked
- development
generated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
status: draft
disked:
  id: DE-078
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-012
  - DE-033
  - DE-023
  requirements:
  - DE-REQ-078-01
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Extension tiers and compatibility

## Surfaces and authority

Public surfaces are a narrow C ABI, versioned process protocol, provider contract and presentation contract, stabilized when real consumers exist. Do not publish private C++ layouts, toolkit types or allocator ownership as ABI. Native structs are never copied directly as wire bytes: widths, byte order, calling convention, alignment and ownership are explicit.

Presentation extensions provide themes/translations/layouts without storage handles. Workflow extensions compose existing typed actions. Read-only providers, mutation providers and privileged native components have increasing qualification and admission obligations. An SDK install does not start a network service or enroll plugins in the broker. User-writable plugin directories are never privileged discovery roots.

Compatibility dialects and PowerShell projections translate into canonical commands and immutable plans, not shell strings or immediate writes. Semantic theme/keymap tokens cannot hide warnings, recovery state or accessibility requirements. Optional assistance is advisory and local by default; external model use requires explicit privacy/network consent and cannot authorize or verify effects.

## Evolution

Version product, ABI, command/protocol, plan, journal, recovery, target and package contracts independently. Negotiate required features; refuse unknown mutation-critical fields; retain opaque observational fields where allowed without changing signed source bytes. Define readers/migration windows, deprecation and tombstones per durable format. Retain older recovery-compatible closures while operations depend on them. No future-system compatibility claim follows from extensibility alone.

Conformance includes independent C/C++ clients, cross-bitness framing, allocation/cancellation behavior, provider positive/negative fixtures and frontend semantic transcripts. Passing a shape check never qualifies the provider's effects.

## Normative requirements

### DE-REQ-078-01

Extensions MUST use explicit versioned contracts and authority tiers; installation or syntactic conformance MUST NOT grant storage authority.

**Verification:** Reject unadmitted plugins, unknown critical features and language-private ABI types; compare typed frontend/provider conformance transcripts.
