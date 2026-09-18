---
type: DiskEd Specification
title: Public documentation and generated reference
description: Docs orient readers while specifications retain normative ownership.
resource: disked://spec/de-073
tags:
- disked
- development
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-073
  profile: disked-spec/1
  version: 0.1.0
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-002
  - DE-071
  requirements:
  - DE-REQ-073-01
  - DE-REQ-073-02
---

# Public documentation and generated reference

## Editorial contract

Root README introduces DiskEd, intended use, actual availability, safety posture and entrypoints. It is not a rolling engineering report or a place to display the latest agent task. `docs/` contains publication-quality task guides, contributor onboarding, platform support, recovery guidance and API/CLI reference. Preserve authorial purpose when updating: a local code change is not permission to rewrite the product homepage.

Narrative docs are authored for people. Small reference sections—command lists, target declarations, requirement IDs—can be generated from canonical registries. Generated pages show source hashes and generation method. A publication map links each human page to relevant specs and triggers review when their hashes change. A drift alert is not permission to replace a narrative with raw specification text.

## Knowledge projection

Specs are authored OKF, not generated from changing implementation by an unchecked summarizer. Implementation/evidence summaries in `.aide/knowledge/okf/` are projections with provenance and freshness. They explain known state without rewriting requirements. Discussion, ADR and rejected alternative records prevent repeating decisions; editorial changelog records semantic changes without duplicating Git history line by line.

## Web/wiki

A static site can render `docs/` and link stable spec IDs. GitHub wiki is optional navigation, never the sole authoritative content store. All essential information remains readable from an offline checkout. Avoid custom wiki-link syntax that breaks plain GitHub Markdown. An internal `disked://` ID is useful machine identity but ordinary relative links are required for reader navigation.

## Documentation tests

Validate links, schema examples, command spellings and generated reference freshness. Executable examples run only on disposable images. Mark future commands as planned; no copy/paste destructive demo targets PhysicalDrive0. Do not publish machine policy tokens, real customer names or unredacted device serials. Accessibility and localization include help and recovery instructions, not just UI labels.

## Normative requirements

### DE-REQ-073-01

README and public guides MUST preserve product-facing purpose; development progress belongs in status/evidence records.

**Verification:** Editorial review against the documentation map.

### DE-REQ-073-02

Generated references MUST bind canonical source hashes and fail freshness checks when the source changes.

**Verification:** Alter command registry and verify docs generation/check detects drift.

## Related specifications

- [DE-002](../foundation/authority.md)
- [DE-071](context-and-handoffs.md)
