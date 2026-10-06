---
type: DiskEd Specification
title: InvocationPolicy v1
description: Deterministic mode routing with explicit overrides and honest ambiguity
  handling.
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
  version: 0.1.5-proposed.1
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
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
- id: review-08a8246-2026-10-04
  resource: ../references/sources.json#review-08a8246-2026-10-04
- id: cli-refinement-2026-10-04
  resource: ../references/sources.json#cli-refinement-2026-10-04
updated:
  by: codex
  at: '2026-10-06T10:05:03.721193+00:00'
  scope: Native host observations and policy implementation; shipping decision remains proposed
---

# InvocationPolicy v1

## Public controls

`--frontend=auto|cli|tui|gui|plain`, `--format=human|json|ndjson` and `--interactive=auto|yes|no` are canonical. `catalog/cli-syntax.json` owns exact spellings and expansion: `--cli`, `--tui` and `--gui` select frontend; `--json`/`-j` select JSON; `--headless` selects CLI plus noninteractive behavior while leaving output format unchanged. `--help`/`-h` selects static contextual help. These are descriptor meanings, not separate parsing branches. `disked tui` and `disked gui` are convenience entries. JSON selects noninteractive machine output. Contradictory explicit flags such as `--gui --json` are errors, not last-option-wins behavior.

## Decision order

Validate the complete argument vector first, using DE-021 option/value groups in any permitted position before `--`. The leading-options form in usage examples is not a positional restriction. Accumulate all explicit settings before routing; duplicate aliases and contradictions are diagnosed without last-option-wins behavior. Explicit `--interactive=no` prevents auto-selected interactive frontends; combining it with explicit GUI/TUI is a conflict. Full-screen rendering requires a capable terminal. Explicit TUI on a limited terminal uses a linear interactive renderer; auto mode on that terminal defaults to plain output. Machine output forbids prompts and terminal decoration. An explicit frontend is honored or returns `frontend_unavailable`; explicit GUI with redirected handles does not become CLI unless it conflicts with an explicit machine request. A domain command without a frontend is CLI. An explicit desktop activation selects GUI. Bare invocation with genuinely redirected stdin/stdout selects noninteractive help. Bare invocation with a usable inherited interactive terminal selects TUI, or plain help on a limited terminal. Bare desktop launch with a usable display selects GUI. Otherwise produce bounded plain diagnostics.

A missing or invalid standard handle is not necessarily redirection. Distinguish inherited pipe/file, terminal, absent and invalid handles. Desktop launch can allocate a console for a console-subsystem image, so `isatty()` alone cannot identify launch intent. Record terminal ownership, explicit activation flags, standard-handle provenance and display availability. Parent executable names are hints only. An ambiguous case falls back safely and reports the reason; no mutation is implied by bare launch.

## Windows trade-off

The reference hypothesis is a console-subsystem native EXE containing a Win32 GUI. One PE subsystem value cannot guarantee ideal desktop and every-shell behavior simultaneously. Never hide or detach a console owned by a caller, debugger, terminal host or ConPTY session. Installed shortcuts pass explicit GUI intent; they do not by themselves prove zero console flash. A prototype must measure actual launch behavior on XP/7/10/11 before freezing subsystem policy. `AttachConsole` is an alternative adapter experiment, not a universal fix.[^windows-pe]

## Inspection and tests

`disked mode explain --format=json` reports observations, selected mode, reason code and fallbacks without changing state. The fixture catalog covers pipes, explicit modes, headless operation, inherited consoles, desktop-created consoles and conflicts. Later native integration tests cover Explorer, cmd, PowerShell, Windows Terminal, SSH, RDP, scheduled tasks and file associations. The included fixture oracle tests the policy only; it cannot prove OS launch behavior.

[^windows-pe]: Microsoft PE format and console documentation; see the source registry.

## Setup and essential routing

Built-in build/mode/command discovery stays in the essential tier without probe, network or setup effects. Explicit `setup inspect` uses local declared maintenance metadata; future setup-changing commands require a separate reviewed lifecycle contract and cannot dispatch through the storage broker. Existing machine-format conflicts and no-prompt rules apply unchanged. Unimplemented verbs return unavailable; attached command sketches are not an additional command registry.

## Prompt permission and a persistent shell

`--interactive=yes` permits prompts for a human CLI/plain command; explicit `--cli` and inferred CLI honor it identically. It does **not** open a persistent shell. `--interactive=auto` on a one-shot command remains noninteractive; `no` forbids prompts. A capable or limited terminal can supply a prompt channel. Without usable input/output, an explicit prompt request returns `interaction_unavailable`, never silently false. A caller may explicitly provide a separate verified prompt channel while result stdout is redirected; the renderer must not read answers from pipeline data or mix prompts into machine results. The policy oracle accepts normalized observations, not actual OS handles or command-line tokens.

Machine JSON/NDJSON plus `interactive=yes` remains `argument_conflict`. GUI/TUI interaction rules are unchanged. Bare `interactive=yes` selects bounded CLI interaction/help; persistent sessions require the planned `disked shell` entry described by [DE-027](interactive-shell.md). The DE-W011 native adapter separately exercises actual channels, with alias parsing in DE-W012. The pure oracle alone does not establish host behavior.

## Help and invocation effects

Contextual help resolves a command/domain without satisfying operation operands or runtime prerequisites. `disked help partition resize` and an interspersed `--help` are meta-requests over static descriptors. Diagnose invalid syntax rather than dispatching through help. Explicit machine help/errors remain structured; deferred/invalid format selection cannot cause a partial human banner before JSON. DE-021 owns grammar and literal boundaries. The invocation oracle still consumes normalized observations only; it is not evidence that a native argv parser or help renderer exists.

## Native observation and DE-W011 admission

The first native `mode.explain` handler reports `observations`, `policy_inputs`,
`selection` and `bare_selection` in its result. The first selection describes the
actual invocation; the second evaluates bare human invocation on the same host.
No injected host observations or private launch flags are accepted by the product.
Its parameters remain empty. Human output is a compact observational JSON object;
machine output uses the normal response envelope. Transport requests describe the
transport process's startup observations and a noninteractive machine command.

Observe stdin/stdout/stderr independently as console, pipe, file, character,
unknown, absent or invalid. Retain whether the CRT has a usable descriptor and
the available console mode/geometry observations. Verify the input-buffer role
with a non-consuming console-input query; `GetConsoleMode` alone also accepts a
screen-buffer handle incorrectly passed as stdin. `GetFileType` failure is not
redirection; `GetConsoleMode` failure is not proof of a pipe. Probe no input bytes,
send no terminal queries, and open no replacement console handles during
startup observation or essential commands.
Only usable descriptors may have their private CRT translation set to binary.
Observation does not change console modes, code pages, size, visibility,
attachment or handles. An admitted interactive TUI has the separate owned-state
contract in [DE-026](terminal-session.md).

A bounded console process-list observation may establish sharing, but cannot
establish creator identity. Protect a shared console as caller-owned; otherwise
retain unknown ownership. Process names, environment hints and a lone attached
process cannot prove Explorer activation or permission to hide/detach a console.
Display and desktop activation remain unknown unless established explicitly.
The first adapter does not qualify ConPTY/SSH behavior from pipe heuristics.

Normalized policy inputs include actual GUI/TUI availability. The fixture oracle
defaults TUI availability to true for its original abstract cases; real product
compositions pass it explicitly. An explicit unavailable frontend is refused.
Automatic TUI selection without an implemented TUI falls back to bounded plain
help with `tui-unavailable`; it never advertises a running screen renderer.
DE-W014 now supplies the native console TUI in this prototype. Explicit valid
help is resolved before runtime availability checks. `--terminal=auto|linear|screen`
requires explicit TUI selection and chooses its presentation; it cannot be used
to convert pipeline input into interactive input.

Absent input does not prevent help/build/discovery. Explicit transport without
usable input returns framed `input_error`, exit 4, when stdout is usable. An
unusable required output returns 4 without attempting that CRT stream. Absent
stderr alone does not prevent a successful stdout result; a human diagnostic
that cannot be delivered is an output failure. Invalid UTF-16 argument tokens
are diagnosed without echoing them; valid later output controls still govern
error framing. No failure may initialize providers or create application files.

Qualify direct processes, cmd/PowerShell redirection, absent/invalid handles and
a hidden test-owned console with an inherited child. Compare console state before
and after the child. Record unrun Explorer/Windows Terminal/SSH/RDP/scheduled-task,
other Windows versions and no-flash experiments explicitly. Retain DE-DEC-002 as
proposed until that broader evidence justifies a shipping subsystem decision.

API basis: [standard handles](https://learn.microsoft.com/en-us/windows/console/getstdhandle),
[file type observations](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfiletype),
[bounded console membership](https://learn.microsoft.com/en-us/windows/console/getconsoleprocesslist),
[input-buffer observations](https://learn.microsoft.com/en-us/windows/console/getnumberofconsoleinputevents),
and [CRT descriptor absence](https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/fileno?view=msvc-170).

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


## Native GUI observation boundary

DE-W015 compiles the Win32 adapter but leaves desktop/display facts unknown in
headless startup observations. A valid explicit GUI request loads its required
system APIs and checks the process window station before initializing the fake
service. Its in-window `mode explain` result adds `observations.gui`, observed
display availability, current contrast knowledge and the selected thread DPI
mode. It then evaluates the same invocation policy with those observed inputs.
No headless mode query loads GUI libraries merely to claim display availability.
The console subsystem and automatic desktop-launch uncertainty are unchanged.
