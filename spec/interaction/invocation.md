---
type: DiskEd Specification
title: InvocationPolicy v1
description: Deterministic mode routing with explicit overrides and honest ambiguity handling.
resource: disked://spec/de-020
tags:
- disked
- interaction
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-020
  profile: disked-spec/1
  version: 0.1.0
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-010
  - DE-005
  requirements:
  - DE-REQ-020-01
  - DE-REQ-020-02
  - DE-REQ-020-03
sources:
- id: windows-pe
  resource: ../references/sources.json#windows-pe
- id: windows-console
  resource: ../references/sources.json#windows-console
---

# InvocationPolicy v1

## Public controls

`--frontend=auto|cli|tui|gui|plain`, `--format=human|json|ndjson` and `--interactive=auto|yes|no` are canonical. `--cli`, `--tui`, `--gui`, `--json` and `--headless` are aliases of descriptors, not independent parsing branches. `disked tui` and `disked gui` are convenience entries. JSON selects noninteractive machine output. Contradictory explicit flags such as `--gui --json` are errors, not last-option-wins behavior.

## Decision order

Validate arguments first. Explicit `--interactive=no` prevents auto-selected interactive frontends; combining it with explicit GUI/TUI is a conflict. Full-screen rendering requires a capable terminal. Explicit TUI on a limited terminal uses a linear interactive renderer; auto mode on that terminal defaults to plain output. Machine output forbids prompts and terminal decoration. An explicit frontend is honored or returns `frontend_unavailable`; explicit GUI with redirected handles does not become CLI unless it conflicts with an explicit machine request. A domain command without a frontend is CLI. An explicit desktop activation selects GUI. Bare invocation with genuinely redirected stdin/stdout selects noninteractive help. Bare invocation with a usable inherited interactive terminal selects TUI, or plain help on a limited terminal. Bare desktop launch with a usable display selects GUI. Otherwise produce bounded plain diagnostics.

A missing or invalid standard handle is not necessarily redirection. Distinguish inherited pipe/file, terminal, absent and invalid handles. Desktop launch can allocate a console for a console-subsystem image, so `isatty()` alone cannot identify launch intent. Record terminal ownership, explicit activation flags, standard-handle provenance and display availability. Parent executable names are hints only. An ambiguous case falls back safely and reports the reason; no mutation is implied by bare launch.

## Windows trade-off

The reference hypothesis is a console-subsystem native EXE containing a Win32 GUI. One PE subsystem value cannot guarantee ideal desktop and every-shell behavior simultaneously. Never hide or detach a console owned by a caller, debugger, terminal host or ConPTY session. Installed shortcuts pass explicit GUI intent; they do not by themselves prove zero console flash. A prototype must measure actual launch behavior on XP/7/10/11 before freezing subsystem policy. `AttachConsole` is an alternative adapter experiment, not a universal fix.[^windows-pe]

## Inspection and tests

`disked mode explain --format=json` reports observations, selected mode, reason code and fallbacks without changing state. The fixture catalog covers pipes, explicit modes, headless operation, inherited consoles, desktop-created consoles and conflicts. Later native integration tests cover Explorer, cmd, PowerShell, Windows Terminal, SSH, RDP, scheduled tasks and file associations. The included fixture oracle tests the policy only; it cannot prove OS launch behavior.

[^windows-pe]: Microsoft PE format and console documentation; see the source registry.

## Normative requirements

### DE-REQ-020-01

Explicit conflicting modes MUST return `argument_conflict`; machine modes MUST NOT prompt or initialize a GUI/TUI.

**Verification:** Evaluate conflict and machine-output fixtures.

### DE-REQ-020-02

Automatic routing MUST distinguish absent handles from genuine redirection and MUST NOT alter a caller-owned console.

**Verification:** Run owned/inherited/pipe/absent-handle fixtures plus native launch spike.

### DE-REQ-020-03

Bare invocation MUST have no storage side effects and MUST expose an explainable mode decision.

**Verification:** Trace fake-provider calls across all invocation cases.

## Related specifications

- [DE-010](../architecture/system.md)
- [DE-005](../foundation/glossary.md)
