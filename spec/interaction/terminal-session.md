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
  at: '2026-10-06T11:06:20.586413+00:00'
status: draft
disked:
  id: DE-026
  profile: disked-spec/1
  version: 0.1.7-proposed.1
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
  scope: DE-W014 native terminal execution contract; owner acceptance pending
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

## DE-W014 native terminal execution contract

The Windows x64 prototype admits `disked tui` / `disked --tui` using verified
console input and output handles. Additive `--terminal=auto|linear|screen` selects
presentation and requires explicit TUI selection. Auto chooses a private screen
buffer at 60 columns by 16 rows or larger, otherwise a complete linear view.
Explicit screen mode refuses insufficient geometry; explicit linear mode uses
append-only text without cursor addressing. Pipes, files, absent handles and
wrong-role handles cannot open an interactive frontend. Bare launch uses the
existing invocation policy; `--interactive=yes` still does not open a shell.
Explicit valid help remains static and never initializes a terminal or provider.

Both renderers use one toolkit-independent model and the DE-023 service. The
initial view is the cached fake inventory, including omissions, observation
state, exact IDs and explicit unknown capacities. Arrow keys move focus; Enter
selects and inspects the focused identity through revision-bound service actions.
F2 opens the canonical command explorer, F3 returns to inventory, F4 clears
selection, F5 refreshes the view from the service, and F6 switches linear/screen
presentation when available. Escape returns from a view; F10 or Ctrl+C exits.
PageUp/PageDown scroll complete wrapped data. These actions never scan real media.

The explorer lists every canonical descriptor, distinguishes implemented and
unavailable commands, and stages descriptor-owned typed forms. Target fields
default to the exact selected ID; capability operation defaults to
`target.inspect`. Tab/Shift+Tab change fields, Backspace edits, and printable
Unicode input remains inert. Enter in a form does not dispatch. F9 first opens
review, and a second F9 explicitly submits using the captured graph revision.
Escape from review returns to the form. An explicit command supplied with
`--tui` opens that same form with its parsed parameters; it does not bypass review.
The transport selector is visible as transport-only and cannot nest stdin service
inside the TUI. Later handlers stay unavailable. The command shell remains DE-W019.

Paste detection is unknown for this backend. Newline/control characters and key
repeat cannot submit forms or review: activation requires a fresh F9 key press
after key release. No text shortcut executes commands. Unsupported input is
ignored or reported without converting it into another action. All result,
review and diagnostic text is escaped at the presentation boundary; exact typed
values and identity remain separate. No history or transcript file is created.

The private model retains one snapshot, one outcome, one staged form (at most
16 fields, 4096 UTF-8 bytes each), a 1 MiB presentation budget and bounded page
state. Native screen frames are at most 240 by 80 cells; larger displays leave
unused space, and narrow views wrap/page rather than truncate identifiers or
diagnostics. Linear output emits complete logical records only after state
changes, not periodic redraws or progress animation. Rendering and selection
never recompute storage eligibility. Unknown/denied/stale states remain visible.

The console adapter changes only its required input-mode bits, restoring those
bits while preserving unrelated concurrent changes. It never changes standard
handles, console code pages, title, font or caller buffer size. Full-screen mode
creates a non-inheritable buffer and retains the actual active buffer through a
console-only `CONOUT$` handle; output handles can refer to inactive buffers.
Normal exit, Ctrl+C and caught failures restore the active buffer and input mode.
The child explicitly enables its Ctrl+C handler even if its launcher ignored
Ctrl+C; this process-local setting does not change the caller. Linear output
advances the cursor and scrollback normally while preserving viewport dimensions.
Exit 0 denotes orderly frontend shutdown; individual request refusals remain
visible outcomes and never become successful operations. Backend failures exit 4,
and unavailable channels/styles exit 3.
Forced process termination/console destruction has only best-effort host cleanup,
not a guaranteed restoration claim. No physical storage handle is opened.
`mode explain` includes a schema-checked startup terminal-capability snapshot.
It describes native API/ASCII-renderer capabilities and the explicit startup
linear preference, not the current buffer after an in-session layout switch.
Paste detection and alternate-buffer activation stay unknown until attempted;
no screen allocation or input read occurs during that observation.
These choices follow the Windows [screen-buffer API](https://learn.microsoft.com/en-us/windows/console/createconsolescreenbuffer)
and [console-handle semantics](https://learn.microsoft.com/en-us/windows/console/console-handles).

Acceptance requires model/service parity for successful and refused actions,
missing/replaced selection, stale review, inert paste/repeat input, complete
narrow/linear results, command availability and finite buffers. Actual hidden,
test-owned console launches must exercise navigation, both renderers, Ctrl+C,
caller-state restoration, resize and unavailable channels. Those tests qualify
only the exercised host/backend; screen-reader, ConPTY/remote, DOS/serial and
other Windows profiles remain separate evidence requirements.

## Normative requirements

### DE-REQ-026-01

Terminal detection and rendering MUST use bounded channel-specific capabilities and explicit ownership, preserving usable linear output and caller state.

**Verification:** Qualify native/VT/DOS/serial backends under narrow, monochrome, redirected, absent-mouse and interrupted-exit fixtures; no runtime result is claimed by the schema fixture.

### DE-REQ-026-02

Untrusted presentation text and pasted input MUST remain data until explicit command submission; presentation changes MUST NOT change storage identity or authority.

**Verification:** Exercise control characters, multiline paste, stale selection, completion/history and resize during review; verify no implicit dispatch or loss of critical context.
