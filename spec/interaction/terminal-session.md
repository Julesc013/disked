---
type: DiskEd Specification
title: Terminal sessions and capabilities
description: Channel-specific terminal capabilities, bounded rendering and owned restoration.
resource: disked://spec/de-026
tags:
- disked
- interaction
generated:
  by: codex
  at: '2026-10-04T06:41:03.817694+00:00'
status: draft
disked:
  id: DE-026
  profile: disked-spec/1
  version: 0.1.2-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-020
  - DE-045
  requirements:
  - DE-REQ-026-01
  - DE-REQ-026-02
updated:
  by: codex
  at: '2026-10-04T06:41:03.817694+00:00'
  scope: 08a8246 review corrections; proposed, not accepted
sources:
- id: review-08a8246-2026-10-04
  resource: ../references/sources.json#review-08a8246-2026-10-04
---

# Terminal sessions and capabilities

## Capabilities and profiles

`schemas/terminal-capabilities.schema.json` describes input, output and diagnostic channels independently, backend, viewport/backing buffer, encoding/glyph set, cursor addressing, colour, keyboard/mouse/resize/paste features, screen ownership and accessibility choice. Unknown is not detected support. The fixture is synthetic, not a qualified DOS or Windows terminal. Profiles derive from these facts: plain stream, linear interactive, native text console, addressable terminal and enhanced terminal. Storage capabilities are a separate contract.

OS age is not a terminal capability test. A qualified DOS local backend may offer cell widgets and mouse input without ANSI; a serial channel may be plain. Windows [native console input](https://learn.microsoft.com/en-us/windows/console/reading-input-buffer-events) supplies keyboard, mouse and window events independently of [VT sequences and their mode flags](https://learn.microsoft.com/en-us/windows/console/console-virtual-terminal-sequences). Each backend needs actual host/build qualification. Accessible linear presentation is an explicit first-class choice.

## Detection and ownership

Probes are bounded, opt-in where interactive, and never injected into redirected output or allowed to consume unrelated user input. Preserve caller handles and modes; restore only state changed by DiskEd. Do not resize the user's terminal to fit a layout. Abnormal-exit restoration is best effort with documented limits. One compositor owns an active TUI screen; providers emit structured events and never print into it.

Distinguish visible viewport, terminal scrollback, render buffer, command history and durable event retention. Bound each application-owned buffer and apply backpressure. Narrow layouts preserve target identity, unresolved errors and essential confirmation content; very small channels offer a complete linear equivalent. Prefer ASCII, appropriate legacy glyphs or Unicode according to observed encoding; colour and glyphs never carry the only meaning.

## Input and presentation data

Treat labels, paths and provider messages as untrusted data. Escape control sequences and nonprinting characters at the display boundary; retain exact originals separately from display/redacted exports. Completion and history navigation never execute a command. Multiline paste is reviewable before submission; backend paste support cannot silently turn lines into independent commands. Keyboard navigation remains complete without mouse support. Mouse editing changes proposed state and never applies a storage plan.

## Normative requirements

### DE-REQ-026-01

Terminal detection and rendering MUST use bounded channel-specific capabilities and explicit ownership, preserving usable linear output and caller state.

**Verification:** Qualify native/VT/DOS/serial backends under narrow, monochrome, redirected, absent-mouse and interrupted-exit fixtures; no runtime result is claimed by the schema fixture.

### DE-REQ-026-02

Untrusted presentation text and pasted input MUST remain data until explicit command submission; presentation changes MUST NOT change storage identity or authority.

**Verification:** Exercise control characters, multiline paste, stale selection, completion/history and resize during review; verify no implicit dispatch or loss of critical context.
