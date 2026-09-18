---
type: DiskEd Specification
title: Authority, acceptance and source ownership
description: Separate requirements, contracts, implementation facts, evidence and public explanations.
resource: disked://spec/de-002
tags:
- disked
- foundation
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-002
  profile: disked-spec/1
  version: 0.1.0
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-001
  requirements:
  - DE-REQ-002-01
  - DE-REQ-002-02
sources:
- id: aide-readme
  resource: ../references/sources.json#aide-readme
- id: aide-okf
  resource: ../references/sources.json#aide-okf
---

# Authority, acceptance and source ownership

## Four kinds of truth

`spec/` is the authored specification bundle: design intent, requirements, decisions, machine contracts, examples and implementation work definitions. `docs/` explains the product to users and contributors; it is not an alternative command registry. `.aide/` records development work and evidence. Runtime source and retained test artifacts establish what actually exists. An accepted specification cannot prove implementation. A passing test cannot silently amend a specification.

Each fact has one owner. Prose requirements are owned by the named concept. Structured wire fields are owned by their JSON Schema. Command spelling and flags are owned by `catalog/commands.json`. Target declarations belong to `catalog/targets.json`. Generated indexes, traceability views and publications point back to those owners. They are never independent editing surfaces.

When prose and schema disagree, do not choose the convenient interpretation: report a specification defect and block the affected implementation or release. More restrictive safety constraints remain in force until resolved. A chat request is candidate input until converted to a versioned change; explicit owner instructions still govern the current task, but do not justify hiding a repository conflict.

## Baseline status

This archive is proposed baseline `0.1.0`, not an owner-approved standard. The user's repeated product constraints are preserved as requirement inputs. New technical choices are identified as defaults, proposed decisions or experiments. Importing the ZIP does not grant agents access to physical storage, privileged credentials, releases or protected branches. `DE-W000` reviews the baseline; a reviewer must record the actual Git revision and decision hashes.

Acceptance is a record tied to a subject digest, the hashes of its reviewed specification-input closure, actor, scope, evidence and time. The local validator checks freshness, not reviewer authentication; branch review and protected evidence provide the external trust boundary. Updating a normative file invalidates its prior acceptance unless a documented semantic-equivalence review covers the change. A `status: stable` frontmatter value alone is not acceptance. Generated structure checks do not add OKF `verified: human:...` fields.

## Specification versus AIDE knowledge

AIDE's observed OKF pages are projections that explain protocol and evidence. DiskEd intentionally uses OKF also as the container format for authored normative specifications. `disked.authority` makes the distinction explicit. Future `.aide/knowledge/okf/` pages may summarize these specifications, but must reference them and never create a second normative copy.

## Migration from the earlier discussion

The latest single-entrypoint requirement supersedes the earlier two-product-executable proposal. Root `spec/` now owns canonical specifications, schemas and registries; do not simultaneously create competing root `canon/`, `contracts/` and `content/command-spec/` authorities. Code directories will be created when they contain implemented modules, not as an empty cathedral of future folders. Historical proposals remain in the decisions ledger, with reasons for supersession.

## Normative requirements

### DE-REQ-002-01

A source-of-truth class MUST have exactly one declared owner; conflicting normative sources MUST block the affected work.

**Verification:** Create a command/schema conflict and confirm a defect is reported rather than inferred away.

### DE-REQ-002-02

Approval MUST identify exact content and a real reviewer; generated validation MUST NOT manufacture acceptance or hardware qualification.

**Verification:** Inspect acceptance schema and reject a digest-mismatched record.

## Related specifications

- [DE-001](charter.md)
