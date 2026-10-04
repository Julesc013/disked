---
type: DiskEd Specification
title: Command grammar and canonical registry
description: A descriptor-owned CLI shared with TUI and native GUI command discovery.
resource: disked://spec/de-021
tags:
- disked
- interaction
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-021
  profile: disked-spec/1
  version: 0.1.2-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-020
  - DE-005
  requirements:
  - DE-REQ-021-01
  - DE-REQ-021-02
  - DE-REQ-021-03
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

# Command grammar and canonical registry

## Grammar and ownership

`disked [global-options] <domain> <verb> [arguments]` is the domain-command grammar; the explicit session entry is `disked [global-options] shell`. Stable machine IDs use dotted names such as `target.list`, `partition.resize.plan` and `operation.cancel.request`. `catalog/commands.json` owns spelling, aliases, effect class, request/result schemas, privilege need, availability and planned handlers. Help, completion, advanced forms and API discovery are generated from those descriptors.

Global aliases are not a promise that every framework has identical pixels. Human CLI, machine CLI, TUI and GUI must reach the same eligible actions and outcomes. A disabled action has a reason code. Commands whose implementation is not present remain declared/planned and cannot appear as executable capabilities.

## Exact parameters

Canonical geometry requests use `--length`, `--start` or `--end-exclusive`, with explicit units. The ambiguous historical `--end +50GiB` example is not frozen as production syntax. A resize plan must distinguish moving a start from changing length. Decimal-string integer fields preserve exact values for clients using floating-point JSON numbers. CLI parsing rejects unrecognized options, overflowing values and duplicate non-repeatable options. File names after `--` are data; never pass them through a shell.

`partition resize` and similar effectful verbs construct plans by default. Machine automation applies a separately reviewed plan ID/digest with expected state. A future interactive convenience can call the same review/apply flow but cannot invent a bypass. `--force` is not provided; typed acknowledgements bind specific risks to the plan.

## Evolution

Aliases deprecate gradually and always resolve to the original descriptor. Retired IDs are tombstoned, not recycled. Unknown future commands return `command_unavailable`. Schema incompatibility is distinct from invalid arguments. Standard output in machine mode never includes version banners, progress animation, localized labels or advertisements. Human help may be localized; command IDs, enums and field names are not.

## Early command slice

Build/mode/command discovery, target enumeration, topology inspection, image inspection, table validation, capability explanation and evidence export come first. All storage-modifying descriptors remain plan-only or unavailable until their exact admission gate is met. Compatibility dialects for DiskPart/parted are optional translators into intents and must never silently emulate immediate mutation semantics.

## Amendment command scope

The catalog adds only `filesystem.format.plan` (`filesystem format`), `setup.inspect` and `provider.resolve` as planned descriptors. Provider resolution explains compatibility without acquisition; formatting produces a plan without writing. Setup apply/update/uninstall, compatibility dialects, diagnostic bundles and PowerShell projections remain explicitly deferred contracts until selected work defines their effects. No command in this bundle has a runtime handler.

## Stable shorthand and argument ownership

Only complete registered aliases execute: `tgt ls`, `part resize`, `fs format` and `op watch` are proposed catalog spellings bound to their canonical descriptor IDs. Prefix guessing is forbidden. Completion can suggest an expansion but cannot dispatch it. Alias/canonical collisions are rejected globally, and retiring a spelling requires a tombstone rather than reassignment. Plan review shows the expanded action and resolved target identity regardless of shorthand.

Argument contracts are separate from generic request envelopes. A descriptor declares `syntax_status`, a command-specific parameter-schema reference where defined, CLI bindings to named parameter properties, and completion policy. Every available implementation needs defined parameter shape and bindings; a planned descriptor may explicitly remain unresolved. The no-argument discovery/shell entries use an empty-parameter schema; other product parameters remain work to define in DE-W012 before parser/help/form generation. Empty bindings on an unresolved descriptor do not mean the command accepts arbitrary parameters.

All command forms share typed semantic dispatch. Canonical scripts use full spellings or registered stable aliases, never personal aliases or unique-prefix assumptions. Specify quoting, `--`, exact units, negative numeric values, literal path handling and token case before parser admission. Help aliases such as `-h`/`--help` and a separately qualified `/?` are grammar decisions; slash-prefixed paths must not become options by accident. Proposed storage verbs continue to construct plans.

Static completion uses descriptors only. Dynamic identifier completion requires an explicit, bounded sufficiently fresh observation source. Tab, history selection and command exploration never trigger discovery I/O, provider acquisition, elevation or execution. External-shell integration affects only the explicitly enrolled shell; the DiskEd process does not own the parent prompt/editor.

## Normative requirements

### DE-REQ-021-01

Command discovery and dispatch MUST derive from the same canonical descriptor registry.

**Verification:** Inject a registry entry without a handler and confirm it is not advertised as executable.

### DE-REQ-021-02

All geometry input MUST have explicit units and unambiguous inclusive/exclusive semantics.

**Verification:** Reject ambiguous/overflowing input and verify exact integer round trips.

### DE-REQ-021-03

Mutating convenience commands MUST construct immutable plans and MUST NOT bypass review or broker admission.

**Verification:** Inspect handler routing using a recording fake provider.

## Related specifications

- [DE-020](invocation.md)
- [DE-005](../foundation/glossary.md)
