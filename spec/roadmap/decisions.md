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
  version: 0.1.0
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-080
  requirements:
  - DE-REQ-081-01
  - DE-REQ-081-02
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

## Superseded proposals

Two separate public CLI/GUI binaries are superseded by the single-entrypoint preference. A universal MZ/NE/PE executable is rejected as the general delivery strategy. A giant source tree created before code is rejected in favor of ownership roots added when used. OKF as execution authority is rejected; it is a container for authored specs and projections. Generic `--force`, static version-based capability assumptions, journals hidden in unknown gaps, and automatic recovery success claims are rejected.

## Refinement without paralysis

Review M0 and start fake/image work while high-risk runtime decisions remain open. A journal encoding blocker does not stop CLI parsing or native inventory development. Task gates are granular so unresolved future systems do not block today's useful safe slice.

## Normative requirements

### DE-REQ-081-01

Unresolved decisions MUST block only their affected implementation/release scopes and MUST remain visible in work readiness.

**Verification:** Decision-gate test with unrelated read-only work remaining eligible.

### DE-REQ-081-02

A superseded proposal MUST retain its rationale and replacement identity rather than disappearing from history.

**Verification:** Inspect decision catalog and migration entries.

## Related specifications

- [DE-080](implementation.md)
