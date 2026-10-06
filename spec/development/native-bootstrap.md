---
type: DiskEd Specification
title: Bounded native bootstrap
description: Exact DE-W010 executable surface, build identity and acceptance boundary.
resource: disked://spec/de-079
tags: [disked, development]
generated:
  by: codex
  at: '2026-10-05T21:27:36.675325+00:00'
status: draft
disked:
  id: DE-079
  profile: disked-spec/1
  version: 0.1.3-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on: [DE-012, DE-014, DE-015, DE-020, DE-021]
  requirements: [DE-REQ-079-01, DE-REQ-079-02, DE-REQ-079-03]
---

# Bounded native bootstrap

## Scope and subsequent slices

This document and `fixtures/native-bootstrap.json` retain the DE-W010 human-only
contract implemented at `e08a12f620beb5e21efd56e153e256f6efeee625`. The current
composition extends that bootstrap through DE-W012; DE-021/022 own the new parser,
structured help and synchronous transport. Historical W010 evidence does not
qualify those additions. The current catalog selects the active subset; the
two-command selection below describes the recorded W010 revision.

## Execution contract

DE-W010 is a console-only, fake-only bootstrap composition, smaller than M1.
The owner's current request authorizes this implementation and its local tests;
it does not accept the baseline or the resulting implementation. DE-W000's scoped
review recommends this slice while retaining the empty acceptance ledger and
production decisions. Dependency readiness continues to report that distinction.

`catalog/native-bootstrap.json` selects the prototype target, build tools and two
implemented command IDs. Command spellings, aliases and summaries come exclusively
from `catalog/commands.json`. Its public command contracts remain planned: this
prototype implements only the human essential subset below, without admitting
their future machine envelopes. Do not promote the full command API by inference.

The selected lane is Windows x64, PE32+ console, VS 2022 v143 toolset
14.44.35207, Windows SDK 10.0.19041.0, C++14 and static release CRT (`/MT`).
These are prototype choices, not the production language or minimum-OS decision.
Use CMake's `windows-bootstrap` configure/build/test presets from a Git checkout.
Python 3.10+ and Git are build coordinator dependencies; neither is a deployment
dependency. The build downloads nothing. Refuse other compiler/architecture/SDK
combinations in this lane rather than relabeling their output.

## Observable subset

The executable is `disked.exe`. It prints bounded ASCII human text, no ANSI escape
sequences, prompts or localization. Matching is case-sensitive and exact.

| Input | Outcome |
|---|---|
| No arguments; `help`; `--help`; `-h` | Plain bootstrap help, exit 0. This composition has no auto GUI/TUI. |
| `build inspect` | Product, prototype version, Git revision, dirty/clean state, input digest, target, composition, compiler, SDK, configuration, CRT and fake provider identity; exit 0. |
| `command list`; `commands` | Static TSV rows: ID, contract status, implementation status, availability, reason, canonical form; exit 0. |
| One `--help`/`-h` anywhere before `--`, with an exact registered command or alias; `help <exact command>` | Static command summary and actual composition availability, exit 0; no operands needed. |
| Exact planned command or alias, optionally followed by ordinary operands | `command_unavailable`, exit 3. No operand interpretation or storage dispatch. |
| Unknown/incomplete command, including unknown help subject | `command_unavailable`, exit 3. |
| Unknown option, duplicate help, attached value on a help flag, extra operands on an implemented command, or extra tokens after help subject | `invalid_arguments`, exit 2. |
| Any catalogued global control other than help, including machine output selection | `feature_unavailable`, exit 3. Full flag value/conflict semantics belong to DE-W012; this prototype does not claim to parse them. |

Before `--`, scan the complete vector for invalid options/help duplication before
reporting unavailable controls. After `--`, every token is literal; it cannot
become an option or part of a command spelling. Implemented commands accept no
operands. A trailing empty `--` is permitted. `help` plus a help flag is duplicate
help. Unknown tokens are never echoed in diagnostics (including control characters).
Every refusal writes exactly `disked: <code>: <fixed message>\n` to stderr and
nothing to stdout. Output failure returns 4 (`output_error`, best-effort diagnostic).
These numeric outcomes are local to this provisional human bootstrap contract.
Machine response/event and eventual operation exit mappings remain DE-W012 work.

The fake component contains only a static identity and an inert initialization
boundary. No command invokes that boundary. There is no fake disk graph yet;
`target list` remains unavailable until DE-W013. No application path opens a file,
device, network connection, service, subprocess or configuration source. The CRT
and Windows loader still have their normal OS dependencies and startup behavior.

## Acceptance and evidence

`fixtures/native-bootstrap.json` defines expected cases before implementation.
Native tests launch the real executable from an unrelated empty directory with
closed stdin, a minimal PATH and isolated TEMP/TMP; compare output/status, enforce
timeouts and check for created files. A test-only poison provider fails any
initialization attempt; run the same cases against that linked variant. This
checks the application's provider boundary, not all Windows/CRT system calls.

Build identity hashes an explicit source/configuration/catalog input closure and
reports Git HEAD plus checkout dirtiness. Generate it on every build, so changed
inputs or revisions cannot silently reuse an old identity. Preserve the exact
input list/hashes alongside build outputs. A clean, independent local clone must
configure, build and pass the native tests using the recorded commands. Retain
compiler/linker logs, PE headers/imports/manifest, exact artifact hashes and host.
Record direct imports and host dependency observations separately; a developer
host launch is not a clean-VM or older-Windows compatibility qualification.

XP toolchain inventory is a read-only observation in this task. XP compilation,
imports and actual launch remain DE-W018/031 evidence, not inferred from installed
legacy SDK files. GUI, full CLI/machine API, shell, process containment, physical
storage, recovery, Setup and signing remain outside this task.

## Normative requirements

### DE-REQ-079-01

The bootstrap MUST expose only its declared essential human subset and disclose unavailable commands without provider initialization or application file creation.

**Verification:** Run the predefined positive/negative native fixture against the product and poison-provider variant, including literal boundaries, hostile arguments and closed stdin.

### DE-REQ-079-02

The bootstrap MUST bind product, exact source inputs, revision, target and build configuration, with explicit dirty-state and dependency observations.

**Verification:** Compare embedded identity with independently hashed inputs; change an input and rebuild without reconfiguring, then require the new digest; inspect final PE imports and manifest.

### DE-REQ-079-03

DE-W010 evidence MUST include a clean-checkout native build and actual host launches while leaving untested environments and owner acceptance explicit.

**Verification:** Reproduce the named presets in an independent clean clone and retain commands, exit codes, hashes, limitations and the needs-review handoff.
