---
type: DiskEd Specification
title: System architecture and module boundaries
description: Ports-and-adapters architecture compiled into target-specific product compositions.
resource: disked://spec/de-010
tags:
- disked
- architecture
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-010
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-001
  - DE-005
  requirements:
  - DE-REQ-010-01
  - DE-REQ-010-02
  - DE-REQ-010-03
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# System architecture and module boundaries

## Execution path

```text
capture -> observations -> current graph
intent + policy + capabilities -> desired graph
current/desired diff -> action DAG -> immutable plan
simulation + admission + review -> broker
re-identify -> journal -> execute -> flush -> recapture -> verify
result + recovery state + evidence -> presentation snapshots
```

Core semantics have no GUI, shell, network or physical-device dependencies. Platform adapters implement inward-facing interfaces. The composition root selects implementations; the planner asks a capability registry rather than importing the Windows provider. Frontends send typed actions and render returned state. Bulk block data travels through bounded native streams/handles, not JSON.

## Initial modules

`source/portable/` owns checked arithmetic, byte order, bounded byte views, extents and small parsers. `source/runtime/` owns observations, graph, policy, planning, invocation, command dispatch and operation state. `source/providers/` owns actual storage integration. `source/apps/disked/` composes CLI, TUI and one GUI. `source/platform/` contains host process, console, filesystem and security adapters. Create directories only when they have implementations or build targets.

The public SDK initially uses process contracts and a narrow C ABI. Avoid freezing internal classes before a second consumer exists. Static linking is a composition decision, not permission for modules to reach across ownership boundaries. A single-file build can contain many libraries and launch multiple isolated processes.

## Dependency enforcement

Each implemented module has a stable ID, owned paths, public surfaces, required modules and test identifiers in the project graph. Paths may change without changing IDs. Layer checks prohibit frontend-to-raw-I/O calls, platform headers in portable code, core imports of concrete providers, and Setup calls into storage mutation. Generated files identify their generator and source hashes.

## Failure propagation

Typed errors preserve the original platform code, operation context and safe remediation. Do not convert access-denied or identity-ambiguous into an empty list. Partial capture preserves successful observations with explicit omissions. No action is inferred from a display label. An unknown provider result transitions to uncertain/recovery-required state rather than success.

## Composition and execution

[DE-014](component-model.md) defines the small component model and build-time composition checks. [DE-015](execution-topology.md) separates essential startup, inspection and execution roles. Control/presentation, bounded data transfer and independent recovery keep their own contracts. Select process boundaries for actual fault/privilege needs; do not create a mandatory microservice framework.

Optional end-user assistance can explain observations and propose typed intents. It never authorizes effects, chooses an ambiguous physical target, certifies results or silently uploads storage data. AIDE remains development-only and is not a product runtime dependency.

## Normative requirements

### DE-REQ-010-01

The application core MUST depend on interfaces rather than concrete platform or GUI providers.

**Verification:** Static dependency scan plus fake-provider composition test.

### DE-REQ-010-02

All frontends MUST dispatch the same semantic handlers and consume the same operation outcomes.

**Verification:** Replay one fixture through CLI, TUI action simulation and GUI action simulation.

### DE-REQ-010-03

Bulk data MUST use bounded streaming outside the JSON control channel.

**Verification:** Stress a large sparse image and measure bounded control-message size.

## Related specifications

- [DE-001](../foundation/charter.md)
- [DE-005](../foundation/glossary.md)
