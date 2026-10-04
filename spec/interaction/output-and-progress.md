---
type: DiskEd Specification
title: Output, progress and completion
description: Separate human display, protocol events, diagnostics and recovery records.
resource: disked://spec/de-028
tags:
- disked
- interaction
generated:
  by: codex
  at: '2026-10-04T06:41:03.817694+00:00'
status: draft
disked:
  id: DE-028
  profile: disked-spec/1
  version: 0.1.2-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-022
  - DE-023
  - DE-026
  requirements:
  - DE-REQ-028-01
updated:
  by: codex
  at: '2026-10-04T06:41:03.817694+00:00'
  scope: 08a8246 review corrections; proposed, not accepted
sources:
- id: review-08a8246-2026-10-04
  resource: ../references/sources.json#review-08a8246-2026-10-04
---

# Output, progress and completion

## Channels and records

Human stdout carries the requested result. Diagnostics and optional progress use an appropriate separate channel; explicit prompt channels follow DE-020. JSON/NDJSON output is UTF-8, unadorned and noninteractive. A machine consumer never parses human banners, locale text, cursor frames or prompts. No background worker bypasses the frontend compositor.

The presentation transcript, diagnostic/event logs and durable operation journal are distinct. None substitutes for the others. State roots, quotas, privacy and retention are declared; launching from recovery media must not silently write beside the executable. Captured output uses stable complete records, while limited interactive channels receive complete periodic lines.

## Truthful progress and wait policy

Distinguish phase, attempted/completed work, independently verified work, known total, elapsed time and uncertainty. A spinner is decoration, not proof of provider health; waiting for a device is not advancing progress. Unknown totals remain indeterminate and cannot produce fabricated percentages or ETAs. Coalesced progress uses explicit sequence gaps/resnapshots while durable operation truth remains retained.

Submission and successful completion are separate outcomes. An accepted-running response carries a durable operation ID; a wait/follow policy has bounded waiting, reconnect behavior and a distinct still-running result. DE-W012 must assign/test native exit-code mappings before implementation; no numeric success code is invented here. Cancellation is a request until completion/quiescence are observed. Final summaries preserve partial/unknown/recovery-required outcomes and all unsupported claims.

## Normative requirements

### DE-REQ-028-01

Every presentation MUST derive progress and completion from operation truth, preserving uncertainty and channel separation.

**Verification:** Compare rich, linear and captured fake transcripts for unknown totals, stale/late events, slow consumers, cancellation and failed verification; accepted submission cannot appear as completed success.
