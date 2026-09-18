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
  version: 0.1.0
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
---

# Command grammar and canonical registry

## Grammar and ownership

`disked [global-options] <domain> <verb> [arguments]` is the human grammar. Stable machine IDs use dotted names such as `target.list`, `partition.resize.plan` and `operation.cancel.request`. `catalog/commands.json` owns spelling, aliases, effect class, request/result schemas, privilege need, availability and planned handlers. Help, completion, advanced forms and API discovery are generated from those descriptors.

Global aliases are not a promise that every framework has identical pixels. Human CLI, machine CLI, TUI and GUI must reach the same eligible actions and outcomes. A disabled action has a reason code. Commands whose implementation is not present remain declared/planned and cannot appear as executable capabilities.

## Exact parameters

Canonical geometry requests use `--length`, `--start` or `--end-exclusive`, with explicit units. The ambiguous historical `--end +50GiB` example is not frozen as production syntax. A resize plan must distinguish moving a start from changing length. Decimal-string integer fields preserve exact values for clients using floating-point JSON numbers. CLI parsing rejects unrecognized options, overflowing values and duplicate non-repeatable options. File names after `--` are data; never pass them through a shell.

`partition resize` and similar effectful verbs construct plans by default. Machine automation applies a separately reviewed plan ID/digest with expected state. A future interactive convenience can call the same review/apply flow but cannot invent a bypass. `--force` is not provided; typed acknowledgements bind specific risks to the plan.

## Evolution

Aliases deprecate gradually and always resolve to the original descriptor. Retired IDs are tombstoned, not recycled. Unknown future commands return `command_unavailable`. Schema incompatibility is distinct from invalid arguments. Standard output in machine mode never includes version banners, progress animation, localized labels or advertisements. Human help may be localized; command IDs, enums and field names are not.

## Early command slice

Build/mode/command discovery, target enumeration, topology inspection, image inspection, table validation, capability explanation and evidence export come first. All storage-modifying descriptors remain plan-only or unavailable until their exact admission gate is met. Compatibility dialects for DiskPart/parted are optional translators into intents and must never silently emulate immediate mutation semantics.

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
