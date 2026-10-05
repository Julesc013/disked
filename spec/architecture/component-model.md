---
type: DiskEd Specification
title: Components and immutable compositions
description: Small static compositions with explicit loader, provider and delivery closures.
resource: disked://spec/de-014
tags:
- disked
- architecture
generated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
status: draft
disked:
  id: DE-014
  profile: disked-spec/1
  version: 0.1.2-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-010
  - DE-012
  requirements:
  - DE-REQ-014-01
  - DE-REQ-014-02
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

# Components and immutable compositions

## Selection and ownership

A component is a selectable implementation unit; a provider supplies operation capabilities; a preset selects components. A composition binds exact components to one target. A package carries artifacts; a channel distributes them; a servicing owner maintains installed resources. None grants storage authority. The module graph, composition graph, installation-ownership graph, resource graph and action DAG remain separate.

The first build uses a small explicit manifest and static registry, not a general dependency solver. The proposed composition compiler is a build-time resolver that checks dependencies/conflicts and emits the link/resource/provider inventory and qualification inputs from canonical descriptors. Add automation as real consumers require it. Do not introduce a mandatory plugin framework or one binary per checkbox combination.

`catalog/components.json` and `catalog/compositions.json` own the initial planned component selections. `schemas/composition.schema.json` owns their composition review shape. The desktop composition remains planned. The separate DE-079 bootstrap composition has a smaller link closure with its own native evidence; it must not be confused with the full desktop slice. Exact toolchain, imports, hashes and host evidence are prerequisites for promoting a release composition.

## Load-time closure

Record mandatory loader/CRT/static-initialization dependencies separately from optional post-start providers. The loader inventory is explicitly pending or inspected; an inspected empty inventory is distinct from an unknown one. Buildable/qualified declarations require an inspected inventory and evidence references, which still require independent review. A statically imported missing GUI library can prevent even CLI startup. One GUI adapter per desktop composition is the default. Console-only or constrained compositions use the same semantics, declare exclusions, and remain explicit exceptions to the full desktop profile.

Static components change only by replacing the finalized executable. Optional coarse-grained packages retain separate identities. Never patch a signed executable on the endpoint to implement a component checkbox. A missing optional provider cannot prevent built-in help, build identity or saved-report inspection. Composition tests inspect final binaries, not only source-level dependencies.

## Buildable-composition gate

Current local validation proves dependency/shape consistency only. Before promoting a real composition to buildable/qualified, add typed OS/ABI/import/provider compatibility predicates and evidence references that resolve to matching artifact/host outcomes. A nonempty evidence string is not qualification. Keep this as a small real-consumer contract in DE-W010/031 rather than constructing a general solver in advance.

## Normative requirements

### DE-REQ-014-01

A composition MUST declare its loader closure separately from optional runtime components, and MUST reject missing dependencies, cycles and incompatible selections.

**Verification:** Validate fake manifests with unknown components, dependency cycles, multiple GUI adapters and missing required modules; inspect actual imports before any launch claim.

### DE-REQ-014-02

A resolved composition MUST preserve exact component/provider identities across build, staging and delivery; no manifest or preset alone grants admission.

**Verification:** Compare build and staged inventories; replace one provider after plan review and require rejection.
