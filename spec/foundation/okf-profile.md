---
type: DiskEd Specification
title: DiskEd OKF authoring profile
description: OKF v0.2 Markdown with namespaced requirements and deterministic machine projections.
resource: disked://spec/de-003
tags:
- disked
- foundation
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-003
  profile: disked-spec/1
  version: 0.1.0
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-002
  requirements:
  - DE-REQ-003-01
  - DE-REQ-003-02
  - DE-REQ-003-03
sources:
- id: okf-02
  resource: ../references/sources.json#okf-02
---

# DiskEd OKF authoring profile

## Base format and local extension

Use upstream Open Knowledge Format v0.2: UTF-8 Markdown, YAML frontmatter, optional reserved `index.md` and `log.md`, ordinary links, and producer-defined metadata. The root index declares `okf_version: "0.2"`. A concept's OKF identity remains its path without `.md`; the separate `disked.id` is DiskEd's stable cross-move identity. Do not describe that extension as an upstream OKF rule.

Every authored concept carries `type`, `title`, `description`, `resource`, `tags`, `generated`, `status` and `disked`. The namespaced object records stable ID, profile version, document version, authority, review state, risk, dependencies and requirement IDs. Use `draft`, `stable` or `deprecated` for OKF status; use `disked.review` for the finer project state. Trust metadata is not an authorization mechanism. This initial content is generated and not independently human-reviewed.

## Writer conventions

Use descriptive lowercase kebab-case filenames. One concept owns one coherent contract or design concern. Prefer several 300–900 word concepts to a repeatedly rewritten giant master document. Longer algorithm specifications are acceptable when splitting would obscure invariants. Use relative Markdown links so GitHub navigation works from the repository's `spec/` subdirectory; the resolver checks their destination. Explicit requirement headings use `DE-REQ-...` IDs. Never reuse retired IDs.

Use safe YAML: no custom tags, executable values, aliases, anchors or duplicate mapping keys in this producer profile. Upstream OKF may accept broader YAML; the stricter writer profile is for reproducible reviews, not a claim about all OKF consumers. Unknown safe extension keys are preserved. The bootstrap tooling uses PyYAML SafeLoader with duplicate/alias rejection, not a home-grown general YAML parser.

## Sources and freshness

`references/sources.json` records source identities, exact revisions where read, retrieval date and limitations. A `sources` entry can name that local registry plus a stable source key. Place per-claim attribution beside external factual claims. Do not copy entire third-party manuals into this bundle. Revalidate runtime/platform facts before implementing against a newer SDK; a source observation is not a permanent compatibility guarantee.

## Deterministic projections

`specctl index` builds the concept index and requirement/test trace views. These are disposable outputs. The authored statement remains in its concept; the tool refuses mismatched registered IDs. A bundle manifest records exact file bytes without hashing itself recursively. An integrity digest detects changes; it is not an authenticity signature. Git commits, reviews and signed release artifacts provide separate provenance.

## Legacy reading

AIDE's observed v0.1-style `timestamp` documents can be read as external inputs; migration to `generated.at` is explicit. Do not bulk-rewrite sibling repositories to fit DiskEd. All substantive Markdown in the specification bundle follows this profile; reference templates may be stored as `.txt` until installed outside the bundle.

## Normative requirements

### DE-REQ-003-01

Each concept MUST have a unique `disked.id`, valid frontmatter and a resolvable index entry; reserved index/log documents MUST remain navigational/history documents.

**Verification:** Run the structural validator and duplicate-ID/invalid-frontmatter tests.

### DE-REQ-003-02

Generated projections MUST be reproducible from canonical inputs and MUST NOT be hand-edited.

**Verification:** Regenerate twice and compare exact bytes; check stale-index failure.

### DE-REQ-003-03

Consumers MUST distinguish OKF path identity from the stable DiskEd ID and MUST preserve unknown safe extension metadata.

**Verification:** Move a fixture using an alias and round-trip an unknown extension.

## Related specifications

- [DE-002](authority.md)
