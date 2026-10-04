---
type: DiskEd Specification
title: Specification tool contract
description: Local indexing, checks, contexts and safe bootstrap without a product runtime.
resource: disked://spec/de-076
tags:
- disked
- development
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-076
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-003
  - DE-071
  - DE-074
  requirements:
  - DE-REQ-076-01
  - DE-REQ-076-02
  - DE-REQ-076-03
---

# Specification tool contract

## Supported commands

`doctor` reports Python/dependency availability. `check` validates the bundle, examples, cross-references and generated state. `index` deterministically regenerates navigation and trace projections. `show ID` resolves a stable concept ID. `search QUERY` returns bounded matching concepts. `context --work ID --output PATH` exports a task pack; `verify-context PATH` checks freshness. `next` lists dependency-ready planned units without authorizing execution. `impact PATH...` conservatively maps changed source/spec paths. `aide-export --output PATH` writes unprivileged planned AIDE-shaped work records. `bootstrap --root PATH` previews root entrypoints; `--apply` performs a non-overwriting install. `manifest` regenerates file-integrity metadata; `verify-manifest` checks it.

The CLI is a bootstrap specification utility, not `disked`. It never opens raw devices, runs product commands, executes exported work or changes GitHub state. Python 3.10+ is the intended coordinator floor; this archive is tested only on the actual Python environment recorded in its report until additional CI qualifies it. PyYAML and jsonschema are explicit dependencies, pinned to the tested versions. Reading Markdown requires none of them.

## Safe filesystem behavior

Resolve the bundle from the script's own path. Reject path traversal, symlink destinations outside allowed roots, duplicate keys and case-colliding files. Bootstrap preflights every destination before writing and refuses conflicts; it does not merge or overwrite user files. Outputs are regular files under explicitly chosen directories. Packaging uses relative safe paths and excludes local caches, credentials and product images.

## Determinism and integrity

Generated indexes sort by stable IDs/paths and record exact source hashes. Manifest paths sort by serialized POSIX relative strings on every coordinator, avoiding Windows/POSIX case-order differences. The manifest excludes itself and documented ephemeral files to avoid recursive hashing. Context packs state the selected input closure. No tool labels content as approved or verified on behalf of a person. A user can edit the source and regenerate; integrity mismatch is expected after legitimate edits until a new manifest is created. Signing/authenticity is outside this bootstrap tool.

## Local composition and claim checks

`check` validates the small component registry, composition dependencies, target references, exactly one entrypoint, default single GUI, declared scope and finite containment/hash graphs. Buildable compositions distinguish inspected loader inventories from unresolved ones. Target qualification declarations require exact-artifact fields and reject visibly unresolved ABI labels; this does not authenticate their evidence. Capability assessments keep eligibility separate from authority. Amendment and acceptance-design mappings resolve canonical concept and work IDs.

The first native task uses DE-014's small composition contract; full Setup/release context is allocated to DE-W060/062. Mandatory safety closure and the default 120,000-byte refusal remain intact. Tests derive corpus coverage from authored requirement IDs, not a frozen historical count. Relative-root tests create fixtures on the current working drive, since Windows cannot express a cross-drive relative path.

## Known limits

Structural checks cannot prove a filesystem algorithm, detect every factual mistake, validate unavailable OS environments or enforce a malicious worker's privileges. Work-unit readiness is computed from local acceptance records; it is not a distributed scheduler or lock. The Markdown link checker supports the authored project's link forms, not every possible Markdown extension. Schema validation is offline and resolves local references only.

## Normative requirements

### DE-REQ-076-01

Bootstrap tooling MUST never execute work definitions or mutate physical storage/GitHub state.

**Verification:** Inspect code paths and exercise all commands against fixture directories.

### DE-REQ-076-02

Generated context and indexes MUST be deterministic and detect changed source inputs.

**Verification:** Repeat generation and compare, then corrupt one input.

### DE-REQ-076-03

Validation failures MUST be nonzero and explicit; partial checks MUST NOT be called complete qualification.

**Verification:** Negative test matrix across YAML, JSON Schema, links and work DAG.

## Related specifications

- [DE-003](../foundation/okf-profile.md)
- [DE-071](context-and-handoffs.md)
- [DE-074](testing-and-ci.md)
