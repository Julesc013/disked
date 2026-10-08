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
  version: 0.1.24-proposed.1
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
  - DE-REQ-021-04
  - DE-REQ-021-05
  - DE-REQ-021-06
updated:
  by: codex
  at: '2026-10-08T11:37:12.726074+00:00'
  scope: DE-W024 initial shared raw-file command contract; prototype under local development,
    owner acceptance pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
- id: review-08a8246-2026-10-04
  resource: ../references/sources.json#review-08a8246-2026-10-04
- id: cli-refinement-2026-10-04
  resource: ../references/sources.json#cli-refinement-2026-10-04
---

# Command grammar and canonical registry

## Grammar and ownership

`disked <command-form> [operands]` names the command skeleton. Global and selected-command named options may be interspersed before the literal `--` boundary, as specified below. Domain-first forms remain canonical; the explicit session entry is `disked shell`. Stable machine IDs use dotted names such as `target.list`, `partition.resize.plan` and `operation.cancel.request`. `catalog/commands.json` owns spelling, aliases, effect class, request/result schemas, privilege need, availability and planned handlers. Help, completion, advanced forms and API discovery are generated from those descriptors.

Global aliases are not a promise that every framework has identical pixels. Human CLI, machine CLI, TUI and GUI must reach the same eligible actions and outcomes. A disabled action has a reason code. Commands whose implementation is not present remain declared/planned and cannot appear as executable capabilities.

## Exact parameters

Canonical geometry requests use `--length`, `--start` or `--end-exclusive`, with explicit units. The ambiguous historical `--end +50GiB` example is not frozen as production syntax. A resize plan must distinguish moving a start from changing length. Decimal-string integer fields preserve exact values for clients using floating-point JSON numbers. CLI parsing rejects unrecognized options, overflowing values and duplicate non-repeatable options. File names after `--` are data; never pass them through a shell.

`partition resize` and similar effectful verbs construct plans by default. Machine automation applies a separately reviewed plan ID/digest with expected state. A future interactive convenience can call the same review/apply flow but cannot invent a bypass. `--force` is not provided; typed acknowledgements bind specific risks to the plan.

## Evolution

Aliases deprecate gradually and always resolve to the original descriptor. Retired IDs are tombstoned, not recycled. Unknown future commands return `command_unavailable`. Schema incompatibility is distinct from invalid arguments. Standard output in machine mode never includes version banners, progress animation, localized labels or advertisements. Human help may be localized; command IDs, enums and field names are not.

## Early command slice

Build/mode/command discovery, target enumeration, topology inspection, image inspection, table validation, capability explanation and evidence export come first. All storage-modifying descriptors remain plan-only or unavailable until their exact admission gate is met. Compatibility dialects for DiskPart/parted are optional translators into intents and must never silently emulate immediate mutation semantics.

## Amendment command scope

The earlier architecture amendment added `filesystem.format.plan` (`filesystem format`), `setup.inspect` and `provider.resolve` as planned descriptors; the subsequent terminal amendment added the explicit `shell` entry. Provider resolution explains compatibility without acquisition; formatting produces a plan without writing. Setup apply/update/uninstall, compatibility dialects, diagnostic bundles and PowerShell projections remain explicitly deferred contracts until selected work defines their effects. The public full command contracts remain planned. DE-079 records the original human-only bootstrap. DE-W012 adds structured help, build/command inspection and explicit `protocol serve` transport in the same fake-only native lane; DE-022 defines its synchronous admission boundary. Storage commands remain unavailable.

## Stable shorthand and argument ownership

Only complete registered aliases execute: `list`, `ls`, `list targets`, `show`, `commands`, `part resize`, `fs format` and `op watch` are proposed catalog spellings bound to their canonical descriptor IDs. Prefix guessing is forbidden. Completion can suggest an expansion but cannot dispatch it. Alias/canonical collisions are rejected globally, and retiring a spelling requires a tombstone rather than reassignment. Plan review shows the expanded action and resolved target identity regardless of shorthand.

Argument contracts are separate from generic request envelopes. A descriptor declares `syntax_status`, a command-specific parameter-schema reference where defined, CLI bindings to named parameter properties, and completion policy. Every available implementation needs defined parameter shape and bindings; a planned descriptor may explicitly remain unresolved. The no-argument discovery/shell entries use an empty-parameter schema; target inspection, image-path inspection and resize proposal now have bounded scalar shapes for parser tests; those storage handlers remain unavailable. Other product parameters must be defined before handler admission. Empty bindings on an unresolved descriptor do not mean the command accepts arbitrary parameters.

All command forms share typed semantic dispatch. Canonical scripts use full spellings or registered stable aliases, never personal aliases or unique-prefix assumptions. Specify quoting, `--`, exact units, negative numeric values, literal path handling and token case before parser admission. The admitted help spellings are `-h`/`--help`; a possible `/?` compatibility dialect remains deferred. Slash-prefixed paths must not become options by accident. Proposed storage verbs continue to construct plans.

Static completion uses descriptors only. Dynamic identifier completion requires an explicit, bounded sufficiently fresh observation source. Tab, history selection and command exploration never trigger discovery I/O, provider acquisition, elevation or execution. External-shell integration affects only the explicitly enrolled shell; the DiskEd process does not own the parent prompt/editor.

## Option placement and exact token boundaries

Usage displays canonical command order for readability; it does not constrain option position. An accepted global or selected-command named option may occur before, between or after command words and operands, until `--`. Move the complete option/value group, not an option separated from its value. All of these proposed forms resolve to the same inventory request and JSON presentation:

```text
disked --json target list
disked target --json list
disked target list --json
disked list --json
disked list --json targets
```

Command-specific option placement does not widen its scope: `--length=50GiB partition resize PARTITION_ID`, `partition --length 50GiB resize PARTITION_ID` and `partition resize PARTITION_ID --length=50GiB` have the same proposed interpretation. `--length` on `target list` is an error. The proposed resize binding accepts a nonempty target ID and a positive exact B/KiB/MiB/GiB/TiB quantity bounded by u64 after scaling. It tests parsing only: no resize handler or permission to write is implied.

`catalog/cli-syntax.json` owns global option spellings, fixed value arity, normalized settings, help domains and retired spellings. Command descriptors own complete command aliases and named argument bindings. Each named binding declares its aliases, fixed arity (zero or one value) and repeatability. Global spellings and reserved flags cannot be shadowed. A command-specific option spelling has the same lexical arity across descriptors, even where its value type or applicability differs. Variable/optional value consumption and clustered short flags are outside this initial grammar. Admission rejects ambiguous extension metadata rather than changing existing parsing.

For a one-value option, accept `--name=value` and `--name value`; in the separated form the next token is the value even if it resembles a command or another option. An absent value or a bare `--` in that position is `missing_option_value`; an exact literal `--` value needs the attached form. Validate the consumed value as that parameter, rather than reinterpreting it as a switch. An unknown option, empty invalid value, unsupported prefix or wrong-command option is an error. Negative numeric values remain parameter data and receive typed range validation. Zero-value flags cannot accept an attached value.

A bare `--` outside a consumed value ends both option recognition and command-word recognition. A complete command form must precede it; every subsequent token is operand data. `disked image inspect -- --json` inspects an image path literally named `--json` in the proposed grammar. It neither requests JSON nor permits raw-device access. `disked -- target list` has no command. Preserve operand order and original path/identifier bytes through the target's qualified tokenization/encoding rules; do not resplit an already tokenized argument, interpret shell text, or rewrite a path as a keyword. Host quoting, code pages and raw DOS command-tail tokenization need native fixtures before claiming cross-target equivalence.

Normalize aliases before detecting duplicate settings. Repeating the same non-repeatable setting through `--json` and `-j` is `duplicate_option`; selecting `--format=human` and `--json` is `argument_conflict`. Cross-setting conflicts such as `--gui --json` are also order-independent. There is no last-option-wins override. For multiple simultaneous defects, produce stable token-located diagnostics and never dispatch; error ordering itself is not operation semantics.

Resolve complete registered command forms in their declared order after accounting for option/value groups. Do not search operands for command words. When one form extends another, a different command cannot claim the extension: `show` always means target inspection, including when the target identifier resembles another noun. Longer forms for the same command, such as `list targets`, may be explicit alternatives; reserve those words rather than using them as untyped operand rescue. A future `disks` convenience would need its own explicitly scoped descriptor/filter contract and is not registered here.

Parse and validate the complete invocation before printing banners, selecting/initializing a frontend, opening output/state files, discovering storage, requesting elevation or dispatching handlers. Trailing `--json` governs the entire response. Error rendering uses only unambiguously validated output controls; do not start human output and switch formats midway. Invalid invocations produce bounded diagnostics without product effects.

## Contextual help and discoverability

`--help`/`-h` may occur in any permitted option position; `help <command-form>` is a reserved meta-entry over the same descriptors. For example, `partition resize --help`, `partition --help resize`, `--help partition resize` and `help partition resize` address the same help. With no command, `disked --help`, `disked -h` and `disked help` show product-level static help. Missing operation operands, unavailable providers and lack of storage authority do not prevent static help. Incomplete forms show the deepest unambiguous domain, including `help part`. A help request does not hide malformed options or ambiguities: explain them and show relevant help without dispatch. `--help` after the literal boundary or consumed as a value is data, not help. Machine help is structured under the selected JSON/NDJSON output contract.

Help and completion display canonical forms beside all registered alternatives and distinguish planned, unavailable and executable capabilities. A narrowed build keeps spellings bound to their canonical meanings; it returns unavailability rather than reassigning a shortcut. Basic syntax is independent of terminal richness. Completion may search prefixes and offer spelling corrections; execution never accepts a suggestion implicitly. `--fo`, `p` and `-jh` are not accepted shortcuts. `/?` is not admitted in this grammar; a future qualified compatibility dialect needs explicit path/option rules.

Prefer short ordinary words before consonant codes. `list`/`ls`/`list targets` mean `target list`, `show` means `target inspect`, and `commands` means `command list`. `part`, `fs` and `op` are recognizable families whose executable forms are still individually registered, not automatic text substitutions. `tgt ls` was an unimplemented proposal at 9493381 and is now retired with a retained tombstone; no released compatibility claim is invented. No alias is empirically optimal yet: measure correct-entry time, corrections, completion keystrokes, hesitation and delayed recall across selected operator groups/keyboards/terminal profiles in DE-W019.

## Conformance evidence and parser selection

`fixtures/command-syntax.json` records token-vector equivalence groups, expected command identity/scope, control settings, literal operands, help and diagnostics. Its records remain expectation definitions (`definition_only`); `native_execution: not_run` describes evidence stored in that source fixture, not the current executable. Actual Windows parser executions are recorded separately with the exact code revision. Local tooling checks their schema/references and descriptor consistency; it does **not** implement or certify the DiskEd argv parser. Partial alias examples do not complete unresolved storage parameter schemas. DE-W012 must run these cases plus generated option-position permutations against the actual parser, comparing normalized typed requests, plan requirements and effect traces. Repeat the shared suite for admitted DOS, OS/2 and Windows compositions; record actual host tokenization limits separately.

Library defaults are not this contract. [GNU getopt](https://sourceware.org/glibc/manual/latest/html_node/Using-Getopt.html) documents argument permutation and modes that stop at non-options; [argparse](https://docs.python.org/3/library/argparse.html#intermixed-parsing) documents long-option abbreviation and intermixed/subparser limits. These are implementation-selection cautions, not a decision to use either in native DiskEd. [DiskPart list syntax](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/list) supplies a familiar verb-first precedent; no implicit selection or mutation behavior is adopted.

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

### DE-REQ-021-04

Moving an accepted complete option/value group among permitted positions MUST preserve normalized command identity, parameters, presentation settings, target scope and safety requirements.

**Verification:** Run shared equivalence groups and native metamorphic permutations, including command-specific options before the domain and after operands; preserve literal-tail data and reject misplaced/inapplicable options.

### DE-REQ-021-05

The entire invocation MUST be resolved and validated before product effects or presentation initialization; parsing MUST NOT guess command words from operands or resolve unknown prefixes implicitly.

**Verification:** Inject late conflicting/unknown flags, missing values, option-looking filenames and command-looking values; recording fake handlers, output-open hooks and frontend hooks observe no dispatch or initialization.

### DE-REQ-021-06

Contextual help MUST use descriptor-owned meanings, expose registered alternatives and remain available without operation operands, target discovery or elevated authority.

**Verification:** Compare help at all permitted positions, incomplete domains, unresolved commands and structured output; malformed input remains diagnosed and literal/consumed help tokens stay data.

## Related specifications

- [DE-020](invocation.md)
- [DE-005](../foundation/glossary.md)


The DE-W024 initial ordinary-local-raw-file command profile is owned by
[DE-102](../operations/map-verify.md). `image.inspect` and `table.verify` share
explicit path/unit parameters and captured-region findings; prototype admission
does not qualify whole-image verification, physical storage or image containers.
