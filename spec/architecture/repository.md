---
type: DiskEd Specification
title: Repository architecture and ownership
description: Root spec authority, deliberate source modules and no duplicated canonical trees.
resource: disked://spec/de-011
tags:
- disked
- architecture
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-011
  profile: disked-spec/1
  version: 0.1.0
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-002
  - DE-010
  requirements:
  - DE-REQ-011-01
  - DE-REQ-011-02
---

# Repository architecture and ownership

## Root ownership

```text
README.md       public product introduction, not a progress transcript
AGENTS.md       short cross-agent routing and safety entrypoint
CLAUDE.md       thin Claude-specific import of shared instructions
spec/           authored OKF specs, schemas, catalogs, work definitions, tools
 docs/          publication-oriented guides and generated reference pages
.aide/          integration declarations and durable development records
.aide-local/    ignored context packs, temporary runs, caches and tool outputs
portable/       implemented bounded platform-free primitives
runtime/        implemented semantic application modules
platform/       implemented host services
providers/      implemented storage adapters
apps/disked/    composition and frontend hosts
include/        implemented public C headers only when needed
sdk/            implemented bindings and provider examples
 tests/         executable product tests and corpus manifests
 tools/         thin stable wrappers and product build/release tooling
release/        composition locks, setup binding and release metadata
external/       exact dependency provenance and approved patches
```

The indentation above is descriptive, not literal directory names. Do not generate an empty directory for every future platform. Avoid `src/`, parallel modern/legacy source copies and OS-specific long-lived branches. Differences belong to target profiles and adapter modules. Keep raw images, builds and old distributions outside Git; retain recipes and content hashes.

## Spec substructure

`foundation/` owns vocabulary and authority. `architecture/` owns boundaries. `interaction/` owns invocation/CLI/TUI/GUI behavior. `storage/` owns data semantics. `safety/` owns privilege/recovery invariants. `platforms/` and `delivery/` own target and packaging laws. `development/` owns governance, AIDE and documentation workflow. `operations/` contains independent operation contracts. `schemas/`, `catalog/`, `examples/` and `fixtures/` carry machine-readable material. `work/` holds bounded work definitions. `generated/` is regenerable. `tools/` is bootstrap tooling, not the disk engine.

## Branches and changes

Use protected `main` once initialized, an optional integrated `dev`, bounded task worktrees and short-lived release qualification branches. Do not force-create branches or settings while unpacking. No unrequested GitHub write is performed by this archive. Refactors carry module-ID maps, old-path aliases when external references exist, impacted test runs and a migration note.

## Interfaces, not incidental paths

Stable command IDs, schema IDs and requirement IDs are public contracts. Internal filenames and functions are not. The generated index permits lookup by ID after movement. Spec links must remain valid or have deliberate aliases; code tools should resolve ownership through the project graph rather than hard-coding directory folklore.

## Normative requirements

### DE-REQ-011-01

Canonical specs and machine catalogs MUST remain in `spec/`; generated copies elsewhere MUST identify source paths and hashes.

**Verification:** Change a catalog and verify stale generated reference detection.

### DE-REQ-011-02

Repository paths MUST be case-collision-free, portable and ownership-mapped; runtime artifacts MUST remain outside tracked source.

**Verification:** Path audit with reserved Windows names, case collisions and traversal fixtures.

## Related specifications

- [DE-002](../foundation/authority.md)
- [DE-010](system.md)
