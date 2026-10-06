---
type: DiskEd Specification
title: Decision register and experiments
description: Resolve high-cost ambiguities before treating a proposed baseline as frozen.
resource: disked://spec/de-081
tags:
- disked
- roadmap
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-081
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-080
  requirements:
  - DE-REQ-081-01
  - DE-REQ-081-02
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Decision register and experiments

## Decisions already preserved from the user

One product identity `disked`, native GUI per eligible target, CLI/TUI/machine parity, Windows NT first, strong XP/7/10/11 coverage, copy-and-run preference, optional Universal Setup lifecycle, small replaceable modules, and durable repo knowledge are binding product inputs. The spec/docs separation is now explicit and supersedes overlapping canonical roots proposed earlier.

## Open decisions

| ID | Question | Default/proposal | Blocks |
|---|---|---|---|
| DE-DEC-001 | Original-code license | MIT OR Apache-2.0 proposed; owner chooses | Public code release |
| DE-DEC-002 | Windows subsystem/router | Console-subsystem prototype with safe ownership-aware GUI activation | Shipping invocation behavior |
| DE-DEC-003 | Native language/toolchain floor | Small C portable core plus target-qualified C++; prove XP/7 early | Production build matrix |
| DE-DEC-004 | Runtime journal byte format | Model first, then reviewed encoding and durability proof | Any production mutation journal |
| DE-DEC-005 | Same-file elevation identity | Exact-image binding/secure staging experiment | Elevated physical broker |
| DE-DEC-006 | Carbon/JC-DOS current ABI | Pin and inspect upstream headers/specs | Carbon physical/provider implementation |
| DE-DEC-007 | AIDE live integration | Pinned WorkUnit mapping; no scheduler assumed | Claims of AIDE runtime interoperability |
| DE-DEC-008 | Crypto canonicalization | Exact canonical encoding and trust policy reviewed separately | Signed mutation plans |
| DE-DEC-009 | Initial native GUI floor | Win32 reference; managed toolkits remain alternatives | Alternate GUI release claims |

An experiment has a hypothesis, alternatives, fixture/procedure, measurable results, risks and decision owner. Store outcomes at an exact revision. Do not call a proposal "frozen" merely because it was repeated by assistants.

## DE-DEC-002 development evidence

The DE-W011 native adapter now reports standard-channel kinds, CRT usability,
bounded console sharing/geometry and explicit unknown display/desktop intent.
Direct, detached, cmd, Windows PowerShell, PowerShell 7 and a hidden test-owned
console exercise the current console-subsystem artifact on Windows 10 x64.
Caller modes, code pages, handles and dimensions are compared before/after.
The exact source/artifact evidence is retained under
`.aide/evidence/2026-10-06-native-invocation/`.

Retain the console-subsystem prototype while CLI and fake frontends develop.
A Windows-subsystem/AttachConsole alternative still needs its own process,
redirection and launch evidence; switching a linker flag is not qualification.
Explorer, Windows Terminal/ConPTY, SSH/RDP, scheduled tasks, file associations,
XP/7/11 and visible no-flash experiments remain unrun. Do not infer creator
identity from console membership or a parent executable name. DE-DEC-002 stays
proposed and continues to block shipping invocation claims.

## Superseded proposals

Two separate public CLI/GUI binaries are superseded by the single-entrypoint preference. A universal MZ/NE/PE executable is rejected as the general delivery strategy. A giant source tree created before code is rejected in favor of ownership roots added when used. OKF as execution authority is rejected; it is a container for authored specs and projections. Generic `--force`, static version-based capability assumptions, journals hidden in unknown gaps, and automatic recovery success claims are rejected.

## Refinement without paralysis

Review M0 and start fake/image work while high-risk runtime decisions remain open. A journal encoding blocker does not stop CLI parsing or native inventory development. Task gates are granular so unresolved future systems do not block today's useful safe slice.

## October reconciliation decisions

| ID | Proposed direction | Scope blocked pending applicable review/evidence |
|---|---|---|
| DE-DEC-010 | One `source/` prefix retaining current module names/IDs | Initial source-map ratification in DE-W000. |
| DE-DEC-011 | Small static composition manifest first; finite optional H/D/S | Setup/carrier release, not the first fake executable. |
| DE-DEC-012 | Exactly one servicing owner; separate channel projections | Managed/channel release. |
| DE-DEC-013 | Early Win16 terminal and constrained loader probes | Historical terminal/compatibility claims. |
| DE-DEC-014 | Per-target failure/resource budgets, measured during fake slice | Responsiveness/containment claims. |
| DE-DEC-015 | Explicit acquisition consistency and snapshot epoch | Coherent/application-consistent acquisition claims. |

The external candidate IDs were not canonical allocations: DE-014/035/036/045/063/064/065/077 each had competing meanings. [Amendment review](amendment-review.md) and the canonical concept index resolve those proposals once. No acceptance field has been populated. Source recommendations for separate CLI/GUI applications, exhaustive composition solvers before a first binary, mandatory installer-before-reader ordering and independent root contracts are not adopted.

## Normative requirements

### DE-REQ-081-01

Unresolved decisions MUST block only their affected implementation/release scopes and MUST remain visible in work readiness.

**Verification:** Decision-gate test with unrelated read-only work remaining eligible.

### DE-REQ-081-02

A superseded proposal MUST retain its rationale and replacement identity rather than disappearing from history.

**Verification:** Inspect decision catalog and migration entries.

## Related specifications

- [DE-080](implementation.md)
