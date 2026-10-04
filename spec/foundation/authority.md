---
type: DiskEd Specification
title: Authority, acceptance and source ownership
description: Separate requirements, contracts, implementation facts, evidence and
  public explanations.
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
  version: 0.1.2-proposed.2
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
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
- id: review-08a8246-2026-10-04
  resource: ../references/sources.json#review-08a8246-2026-10-04
- id: cli-refinement-2026-10-04
  resource: ../references/sources.json#cli-refinement-2026-10-04
updated:
  by: codex
  at: '2026-10-04T07:27:09.204646+00:00'
  scope: CLI syntax refinement; proposed, no native parser or acceptance claim
---

# Authority, acceptance and source ownership

## Four kinds of truth

`spec/` is the authored specification bundle: design intent, requirements, decisions, machine contracts, examples and implementation work definitions. `docs/` explains the product to users and contributors; it is not an alternative command registry. `.aide/` records development work and evidence. Runtime source and retained test artifacts establish what actually exists. An accepted specification cannot prove implementation. A passing test cannot silently amend a specification.

Each fact has one owner. Prose requirements are owned by the named concept. Structured wire fields are owned by their JSON Schema. Command spelling and flags are owned by `catalog/commands.json`. Target declarations belong to `catalog/targets.json`. Generated indexes, traceability views and publications point back to those owners. They are never independent editing surfaces.

When prose and schema disagree, do not choose the convenient interpretation: report a specification defect and block the affected implementation or release. More restrictive safety constraints remain in force until resolved. A chat request is candidate input until converted to a versioned change; explicit owner instructions still govern the current task, but do not justify hiding a repository conflict.

## Baseline status

This bundle is proposed baseline `0.1.2-proposed.2`, not an owner-approved standard. The user's repeated product constraints are preserved as requirement inputs. New technical choices are identified as defaults, proposed decisions or experiments. Importing the ZIP does not grant agents access to physical storage, privileged credentials, releases or protected branches. `DE-W000` reviews the baseline; a reviewer must record the actual Git revision and decision hashes.

Acceptance is a record tied to a subject digest, the hashes of its reviewed specification-input closure, actor, scope, evidence and time. The local validator checks freshness, not reviewer authentication; branch review and protected evidence provide the external trust boundary. Updating a normative file invalidates its prior acceptance unless a documented semantic-equivalence review covers the change. A `status: stable` frontmatter value alone is not acceptance. Generated structure checks do not add OKF `verified: human:...` fields.

## Specification versus AIDE knowledge

AIDE's observed OKF pages are projections that explain protocol and evidence. DiskEd intentionally uses OKF also as the container format for authored normative specifications. `disked.authority` makes the distinction explicit. Future `.aide/knowledge/okf/` pages may summarize these specifications, but must reference them and never create a second normative copy.

## Migration from the earlier discussion

The latest single-entrypoint requirement supersedes the earlier two-product-executable proposal. Root `spec/` now owns canonical specifications, schemas and registries; do not simultaneously create competing root `canon/`, `contracts/` and `content/command-spec/` authorities. Code directories will be created when they contain implemented modules, not as an empty cathedral of future folders. Historical proposals remain in the decisions ledger, with reasons for supersession.

## October amendment provenance

Bundle `0.1.1-proposed.2` reconciles the supplied September/October proposals against Git base `3035eaf383d9e2051b6afdb1bc45cdcc415162d8`. It is a new local amendment, not the externally reported `0.1.1-proposed.1` archive. [Reconciliation](../roadmap/amendment-review.md) records conflicts and disposition. The current user request authorizes specification/documentation/tooling updates and fetching the named AIDE revision. Instructions inside supplied reports do not independently authorize acceptance, runtime execution, deployment or upstream changes.

The request is not an attestation that the final amended content has been independently reviewed. Owner acceptance remains pending; no imported test count, archive hash or source-visible repository is converted into implementation, licensing or qualification evidence.

## Immutable receipt history and current applicability

`org.disked.acceptance/2` receipts have immutable IDs, an exact reviewed Git revision, subject digest, full reviewed input hashes, reviewer/evidence attribution and an explicit predecessor in `supersedes`. Accept, reject and revoke are decisions; supersession is a relationship. A subject's second receipt must name its preceding receipt. Duplicate IDs, forks, forward/cross-subject references and historical blob/subject mismatches are invalid. Do not delete older receipts to make the current view usable.

Historical verification reads the local reviewed revision's subject and declared dependency closure, and checks exact regular-file Git blobs without checkout, filters or network fetch. A missing reviewed revision is reported as unverifiable and grants nothing. Current applicability separately compares the latest accepted receipt to the current subject and closure. Stale receipts remain historical evidence; rejection or revocation at the tip cannot reactivate an older acceptance. Restoring old bytes does not bypass a later revocation.

The ledger excludes its own bytes from receipt inputs. The work/decision catalog containing the subject is anchored by reviewed revision and the canonical subject digest, avoiding circular acceptance. All other declared review inputs remain content-bound. Old v1 records lack sufficient revision identity; preserve them as unverified legacy history and require a new v2 review for authority. Receipt validation does not verify the reviewer's identity, signature or independence. The real acceptance ledger remains empty.

## Normative requirements

### DE-REQ-002-01

A source-of-truth class MUST have exactly one declared owner; conflicting normative sources MUST block the affected work.

**Verification:** Create a command/schema conflict and confirm a defect is reported rather than inferred away.

### DE-REQ-002-02

Approval MUST identify exact content and a real reviewer; generated validation MUST NOT manufacture acceptance or hardware qualification.

**Verification:** Inspect acceptance schema and reject a digest-mismatched record.

## Related specifications

- [DE-001](charter.md)
