---
type: DiskEd Specification
title: TUI and OEM+ GUI experience
description: Task-oriented interfaces with progressive disclosure and accessible fallback.
resource: disked://spec/de-024
tags:
- disked
- interaction
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-024
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-023
  requirements:
  - DE-REQ-024-01
  - DE-REQ-024-02
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# TUI and OEM+ GUI experience

## Shared information architecture

The left navigator selects hosts, assets, physical devices, images and pools. The central workspace shows current/proposed topology and exact extents. An inspector displays identity, units, health observations, contradictions and capability reasons. A plan area shows dependencies, resource needs, irreversibility and recovery class. The operation timeline displays verified work, not merely bytes submitted. Evidence is inspectable before export.

The TUI projects the same model with a full-screen renderer, a linear accessible renderer and a plain noninteractive renderer. A narrow terminal switches layout rather than losing commands. Renderer adapters cover Win32 console, VT/terminfo, DOS, serial and platform terminal windows. Do not bake curses, FTXUI or direct DOS video memory into the semantic TUI controller.

## Native styling

Use the platform's controls, fonts, menu conventions, contrast and DPI APIs. XP, Windows 7 and modern Windows should look appropriate without maintaining separate application logic. An optional API must be dynamically detected and have a deliberate fallback. A window on an unsupported GUI-less target is not "native" because a custom bitmap UI can be drawn. DOS has no universal desktop GUI; its baseline is CLI/TUI, with any graphics shell a separate declared profile.

## Destructive interaction

A confirmation shows the stable target identity plus human-verifiable model/capacity/connection context, before/after state, data-loss report, exact operation steps and recovery location. Avoid habituating users to repeated generic warnings. Require stronger typed acknowledgements only for named high-risk transitions. Never use a guessed drive letter as the sole confirmation. If a device disappears, selection remains attached to its identity and cannot shift to the next list row.

Simple, Advanced, Expert, Forensic and Laboratory are visibility/workflow modes. They do not grant privilege. Forensic mode cannot silently transition to repair. Laboratory results must not acquire production evidence labels. The advanced command explorer exposes extension operations using typed forms and capabilities rather than injecting scripts into the UI.

## Startup and reconnection

No bare launch scans deeply, spins up sleeping media, repairs metadata or prompts for elevation without a requested task. Basic inventory has bounded frontend waiting and requests cancellation where supported; completion and device quiescence require observation. Long operations reconnect through durable identity. Frontend exit does not kill an admitted mutation at an unsafe checkpoint; operation lifetime is a separate policy.

## Native experience qualification

Organize normal tasks around Inspect, Change, Protect/Recover and Verify/Report, with advanced command discovery over the same actions. Qualify keyboard navigation, visible focus, screen-reader semantics, contrast, text scaling/DPI, locale/encoding, small/remote displays, exact units and stable selection. Maps retain structured equivalents. Themes cannot hide warning meaning, alter capability availability or suppress recovery state.

Test healthy, denied, malformed, delayed and crashed fake providers while interacting with other targets. Display freshness and omission reasons, bounded wait state and the next available action. [DE-045](../safety/degraded-operation.md) owns budgets and cancellation uncertainty; [DE-025](native-integration.md) owns optional installed surfaces. Native integration is not a prerequisite for the standalone GUI.

## Normative requirements

### DE-REQ-024-01

UI selection MUST remain bound to stable object identity across list refreshes and device removal.

**Verification:** Remove selected fake target and insert another at the same index.

### DE-REQ-024-02

View modes MUST NOT alter privilege or hard safety constraints; deep scans/elevation MUST be deliberate actions.

**Verification:** Replay action eligibility across all modes and inspect startup effects.

## Related specifications

- [DE-023](presentation.md)
