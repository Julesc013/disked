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
  version: 0.1.2-proposed.1
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
  at: '2026-10-04T06:41:03.817694+00:00'
  scope: 08a8246 review corrections; proposed, not accepted
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
- id: review-08a8246-2026-10-04
  resource: ../references/sources.json#review-08a8246-2026-10-04
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

## Terminal qualification and optional icon selection

Terminal backend qualification follows [DE-026](terminal-session.md), including text-console widgets without assuming VT, narrow layouts, linear accessibility and independent input/output channels. The built-in shell in DE-027 is an explicit interaction style, not a side effect of permitting prompts. Interface parity tests include the shell once DE-W019 exists.

The supplied icon report describes 18 extracted ICO files/107 frames and decoder disagreements; the ZIP, individual assets, inventory and provenance/permission records were **not supplied** here. Those counts are attributed claims, not local decoding results. No default icon, OS era or redistribution permission is inferred. Retain original stable IDs (including the reported numbering gap) and exact source bytes if assets are later admitted. A reviewed catalog needs source OS/build/module/resource IDs, content hashes, sizes/depths and evidence of rights for intended uses. Keep source assets separate from reviewed derived build assets.

For qualified Win32 assets, [ICON resources](https://learn.microsoft.com/en-us/windows/win32/menurc/icon-resource) can hold alternatives and [WM_SETICON](https://learn.microsoft.com/en-us/windows/win32/winmsg/wm-seticon) selects a window icon. Configuration selects an admitted stable icon ID without rewriting executable resources; retain one stable executable default. Window, shortcut, pinned/taskbar and packaged logos are separate surfaces. Setup may update only explicitly owned shortcuts in the requested scope. Native loader/resource-compiler, DPI/background and legacy mask tests remain unrun; PNG previews cannot settle every AND/XOR case.

## Normative requirements

### DE-REQ-024-01

UI selection MUST remain bound to stable object identity across list refreshes and device removal.

**Verification:** Remove selected fake target and insert another at the same index.

### DE-REQ-024-02

View modes MUST NOT alter privilege or hard safety constraints; deep scans/elevation MUST be deliberate actions.

**Verification:** Replay action eligibility across all modes and inspect startup effects.

## Related specifications

- [DE-023](presentation.md)

## Native terminal slice

DE-W014 implements the shared fake model in full-screen and explicit linear
console views, with identity selection, staged typed forms and a descriptor
explorer. [DE-026](terminal-session.md) owns the exact key/entry/lifecycle contract.
Actual console buffer/input tests and model parity establish the exercised
Windows lane; screen-reader, GUI, remote and other backend qualification remain
separate work. The implementation does not imply those checks have passed.
