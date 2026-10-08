---
type: DiskEd Specification
title: Interactive command shell
description: Explicit persistent DiskEd sessions over the shared command model.
resource: disked://spec/de-027
tags:
- disked
- interaction
generated:
  by: codex
  at: '2026-10-04T06:41:03.817694+00:00'
status: draft
disked:
  id: DE-027
  profile: disked-spec/1
  version: 0.1.10-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-021
  - DE-026
  requirements:
  - DE-REQ-027-01
  - DE-REQ-027-02
updated:
  by: codex
  at: '2026-10-08T19:14:13.655056+00:00'
  scope: DE-W033 structured acquisition input and bounded observation presentation; owner acceptance pending
sources:
- id: review-08a8246-2026-10-04
  resource: ../references/sources.json#review-08a8246-2026-10-04
- id: cli-refinement-2026-10-04
  resource: ../references/sources.json#cli-refinement-2026-10-04
---

# Interactive command shell

## Entry and command boundaries

The planned `disked shell` descriptor opens a persistent DiskEd command session. `--interactive=yes` only permits prompts for one invocation. The shell does not replace COMMAND.COM, cmd or PowerShell and supplies no implicit operating-system shell escape, scripting language or privileged execution path. All submitted lines resolve the canonical command descriptors and typed arguments. Unknown or ambiguous shorthand is refused; personal abbreviations cannot become script compatibility guarantees.

Editing, history, completion and a contextual host/selection prompt are capabilities, with linear fallbacks. Static completion reads metadata. Dynamic completion uses bounded existing observations; pressing Tab never scans devices, acquires software or requests elevation. Pending edits/history selection remain inert until explicit submission. A disconnected/retargeted host invalidates affected selection; a session's remembered target is never write authority.

## Editing after diagnostics

After a syntax error, preserve the editable command and token location so the operator can append a missing option or correct the value without reconstructing the line. Keep the buffer inert and apply the same literal boundary, option-group placement and exact alias rules as one-shot CLI. Help/completion display canonical names and available aliases; correction suggestions require explicit acceptance. Token diagnostics must not execute pasted text or expose redacted arguments in logs. Native keyboard/history behavior and usability measurements remain DE-W019 evidence requirements.

## Prompts, history and transcripts

Transient prompts may compact decoration after submission while preserving the canonical action, target context, warnings and result. They never erase durable operation truth. A frontend switch does not apply a plan or change selected storage identity. Closing a session does not imply a dispatched operation stopped; follow-up uses its durable operation identity.

Declare whether history is disabled, session-only or explicitly persisted to an owned user state root, with bounds, redaction and retention. No automatic history file beside a read-only/recovery executable. Secret arguments and customer data are not silently retained. External shell completions/prompts require separately selected integration and leave ownership with the parent shell.

## DE-W019 native fake-shell execution contract

The native Windows profile admits `disked shell [--history=off|session]` on
qualified console channels. History defaults to off. `--terminal=auto|screen|linear`
selects the same native console backend used by the TUI; explicit GUI/TUI,
noninteractive and machine-output controls conflict with shell entry. Redirected
or unusable interactive channels are refused before fake-provider initialization.
The stdin protocol cannot nest an interactive shell. This is a DiskEd frontend,
not a host shell, script interpreter or general storage admission.

The editor holds at most 65,536 UTF-8 bytes and 128 tokens. This admits a bounded
16 KiB acquisition definition with literal quoting; it does not enlarge the
shared argument, definition, depth or value limits. Spaces delimit tokens.
Single/double quotes preserve literal spaces and may join adjacent token segments;
matching doubled quotes inside a quoted segment encode one literal quote. Empty
quoted tokens are preserved. Backslashes, `$`, `%` and `~` remain literal data;
there is no escape, environment, glob or command expansion. Unquoted `|`, `&`,
`;`, `<` and `>` are refused as unsupported operators. Quoted versions are data.
Unclosed quotes and parser errors retain the exact editable line and byte/token
location. No already-tokenized argument is split again.

Typing, cursor movement, deletion, recall and completion never dispatch. The first
fresh F9 validates and displays the canonical request, parameters and captured
graph revision for graph commands (null for other commands); a second fresh F9
submits it. Other handlers receive no fake graph revision. Enter shows the current inert line
and never submits. A text insertion containing a control/newline is rejected as
a whole, preserving the previous line. A rejected control/oversized insertion
into an acquisition-execution line prevents reviewing that older definition until
an actual text correction or replacement; empty input and cursor movement do not
clear the rejection. Held/repeated activation keys cannot submit.
Any edit, recall, selection or completion invalidates pending review. Escape
returns from review/candidates/navigation without executing. F10 or Ctrl+C closes
the frontend without cancelling a dispatched operation.

Left/Right and Home/End move by Unicode scalar boundaries; Backspace/Delete edit
without splitting UTF-8. Tab first lists at most 64 descriptor/cache candidates;
another fresh Tab accepts the highlighted candidate, with Up/Down choosing among
them. Completion is insertion only. Static command/alias/options and schema enum
candidates use the canonical registry; target suggestions use the existing bounded
fake snapshot only. Dynamic discovery is never triggered. F2 lists commands and
their actual availability. F3 opens cached targets, with arrows/Enter selecting
an exact identity through the shared service. F4 clears selection; F5 refreshes
the cached view; F6 switches the supported terminal layout. Selected identity is
prompt context, not an implicit operand or authority.

With `--history=session`, Up/Down in the editor recall only explicitly submitted,
available, validated commands, capped at 32 entries and 64 KiB with oldest-first
eviction. Syntax errors and unavailable commands are not remembered. Parameters
annotated `writeOnly` are masked in review/transcripts and prevent retaining the
line in history. Editing retains its explicit live input only; successful submission
clears it. No history/transcript/configuration file is created. Session transcript
memory is capped at 256 KiB and 64 complete records; eviction preserves record
boundaries and reports the dropped count. Operation evidence remains in its
separately selected state directory.

Qualified acquisition-watch outcomes use DE-103's separate response/display
profile. While such a complete record is retained, the transcript has an explicit
8 MiB/64-record cap. After its last acquisition-watch record is evicted, admission
again enforces the ordinary 256 KiB cap. Evict whole oldest records, including a
large outcome; never cut its identity, diagnostics or events to fit a quota.
History remains 32 entries/64 KiB, with opt-in ownership and redaction unchanged.

The linear backend emits complete new records once and edits only its owned
prompt row. Long input uses a horizontal editor window; it does not truncate the
retained input or a request. The shared presentation encoder also bounds each
JSON value (64 KiB, 32 KiB per string, depth 32 and 8,192 values). A result beyond
the presentation/transcript limits displays an explicit unavailable marker,
retains the request outcome and never repeats dispatch to recover display.
Acquisition watch selects the bounded larger profile; other responses retain
these limits. Prompt encoding admits the full bounded editor even when literal
quotes or Unicode expand its display; only the visible horizontal window is
cropped, never the retained line.

`exit` (alias `quit`) is the `shell.close` descriptor and follows the same explicit
review/submission path. Outside a shell it returns `command_requires_shell`.
Nested shell/transport/frontend entry is refused. Command lines cannot change the
session's established presentation into a machine stream. Help, command discovery,
fake graph reads and the existing fake-worker commands use the shared handlers and
preserve refusals, operation IDs and unknown outcomes. Unimplemented proposal and
storage handlers remain unavailable; the shell does not create a parallel planner.

Native tests must cover quoted paths, Unicode editing, literal operators, error
correction, completion/history bounds and inert paste/repeat input. Actual hidden
test-owned consoles must exercise screen/linear/narrow layouts, restoration,
redirected-channel refusal, alias/parity journeys and closing with a live worker.
Record synthetic input latency/correction traces as synthetic measurements;
unavailable keyboards, screen readers and human usability remain unqualified.

## Normative requirements

### DE-REQ-027-01

The persistent shell MUST be explicitly selected, use canonical typed dispatch and preserve inert editing/completion until submission.

**Verification:** Compare the fake inventory/inspect/propose/review/simulate journey with CLI/TUI/GUI, including ambiguous aliases, multiline paste and disconnected selection.

### DE-REQ-027-02

Shell history, prompts and transcripts MUST have explicit ownership, bounds and redaction without substituting for operation evidence.

**Verification:** Exercise disabled and session-only history, read-only payload roots, secret-bearing inputs and transient prompts; closing the shell must not fabricate operation completion.
