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
  version: 0.1.2-proposed.2
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
  at: '2026-10-04T07:27:09.204646+00:00'
  scope: CLI syntax refinement; proposed, no native parser or acceptance claim
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

## Normative requirements

### DE-REQ-027-01

The persistent shell MUST be explicitly selected, use canonical typed dispatch and preserve inert editing/completion until submission.

**Verification:** Compare the fake inventory/inspect/propose/review/simulate journey with CLI/TUI/GUI, including ambiguous aliases, multiline paste and disconnected selection.

### DE-REQ-027-02

Shell history, prompts and transcripts MUST have explicit ownership, bounds and redaction without substituting for operation evidence.

**Verification:** Exercise disabled and session-only history, read-only payload roots, secret-bearing inputs and transient prompts; closing the shell must not fabricate operation completion.
