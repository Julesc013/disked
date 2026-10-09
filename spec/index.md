---
title: DiskEd specification index
okf_version: "0.2"
---

# DiskEd specification

**Proposed baseline 0.1.48-proposed.1. Owner acceptance pending. No product or hardware qualification.**

Start with [Start here](START-HERE.md), [authority](foundation/authority.md), [roadmap](roadmap/implementation.md), and [open decisions](roadmap/decisions.md).

## Working entrypoints

```text
python spec/tools/specctl.py check
python -m unittest discover -s spec/tools/tests -v
python spec/tools/specctl.py next
python spec/tools/specctl.py context --work DE-W000 --output .aide-local/context/review --byte-budget 180000
```

The `specctl` utility manages this specification only. It does not execute DiskEd, apply AIDE work, elevate or access raw storage. [Work definitions](work/units.json), [source registry](references/sources.json), [command catalog](catalog/commands.json), [target catalog](catalog/targets.json), [schemas](schemas/index.md) and [tool contract](development/specctl.md) are local, reviewable files.

## Entry

- [DE-000 — Start here](START-HERE.md): Read the bundle in task-sized pieces and run its local checks.

## Architecture

- [DE-010 — System architecture and module boundaries](architecture/system.md): Ports-and-adapters architecture compiled into target-specific product compositions.
- [DE-011 — Repository architecture and ownership](architecture/repository.md): Root spec authority, deliberate source modules and no duplicated canonical trees.
- [DE-012 — Language, ABI and build policy](architecture/languages-and-build.md): Small portable C strata with target-qualified native implementations behind stable contracts.
- [DE-013 — Configuration, state roots and resource packs](architecture/configuration.md): Portable payloads remain immutable while state and evidence have explicit ownership.
- [DE-014 — Components and immutable compositions](architecture/component-model.md): Small static compositions with explicit loader, provider and delivery closures.
- [DE-015 — Essential startup and execution roles](architecture/execution-topology.md): Keep built-in diagnostics available before probes and bind roles to explicit hosts and resources.

## Delivery

- [DE-060 — Single-entrypoint composition and release identity](delivery/composition.md): One product command with explicit dependency, extraction and isolation properties.
- [DE-061 — Universal Setup boundary and installation modes](delivery/universal-setup.md): Setup owns software lifecycle; DiskEd owns storage operations.
- [DE-062 — Licensing, provenance and release trust](delivery/licensing-and-supply-chain.md): Keep licensing decisions explicit and qualify the actual dependency closure.
- [DE-063 — Deployment effects and state ownership](delivery/deployment-profiles.md): Portable, user, machine and native-package modes declare effects and preservation separately.
- [DE-064 — Provider packages and acquisition policy](delivery/component-acquisition.md): Separate implementation choice, version selection, source location, ownership and storage admission.
- [DE-065 — Distribution channels and servicing owners](delivery/channels-and-servicing.md): Generate carriers from finalized payloads and assign one owner to each managed resource.

## Development

- [DE-070 — AIDE integration without a second control plane](development/aide-integration.md): Bounded work, real evidence and projections over pinned upstream contracts.
- [DE-071 — Context packs, handoffs and retrieval](development/context-and-handoffs.md): Continue work without carrying the entire conversation or specification into every session.
- [DE-072 — Codex, Claude and chat entrypoints](development/agent-entrypoints.md): Thin tool-specific adapters over one shared project instruction source.
- [DE-073 — Public documentation and generated reference](development/documentation.md): Docs orient readers while specifications retain normative ownership.
- [DE-074 — Testing, validation and CI strategy](development/testing-and-ci.md): Differentiate schema checks, product tests, hardware evidence and recovery qualification.
- [DE-075 — Governance, review and change safety](development/governance-and-review.md): Lean ownership with risk-scaled review rather than ceremonial committees.
- [DE-076 — Specification tool contract](development/specctl.md): Local indexing, checks, contexts and safe bootstrap without a product runtime.
- [DE-077 — Artifact completeness and publication checks](development/artifact-completeness.md): Verify required content independently of archive integrity and distinguish historical audit claims.
- [DE-078 — Extension tiers and compatibility](development/extension-sdk.md): Stabilize real C/protocol consumers and require conformance without granting implicit privilege.
- [DE-079 — Bounded native bootstrap](development/native-bootstrap.md): Exact DE-W010 executable surface, build identity and acceptance boundary.

## Foundation

- [DE-001 — Product charter and scope](foundation/charter.md): Windows-first storage administration with one target-native entrypoint and evidence-qualified operations.
- [DE-002 — Authority, acceptance and source ownership](foundation/authority.md): Separate requirements, contracts, implementation facts, evidence and public explanations.
- [DE-003 — DiskEd OKF authoring profile](foundation/okf-profile.md): OKF v0.2 Markdown with namespaced requirements and deterministic machine projections.
- [DE-004 — Requirements and traceability](foundation/requirements-and-traceability.md): Stable requirement IDs connect decisions, implementation units, test procedures and evidence.
- [DE-005 — Canonical glossary and naming](foundation/glossary.md): Unambiguous names for identity, state, effects, evidence and delivery.

## Interaction

- [DE-020 — InvocationPolicy v1](interaction/invocation.md): Deterministic mode routing with explicit overrides and honest ambiguity handling.
- [DE-021 — Command grammar and canonical registry](interaction/commands.md): A descriptor-owned CLI shared with TUI and native GUI command discovery.
- [DE-022 — Machine protocol and transport](interaction/protocol.md): Versioned envelopes, bounded messages and honest operation outcomes.
- [DE-023 — FrontendSession and semantic parity](interaction/presentation.md): One presentation model for terminal and native visual interfaces.
- [DE-024 — TUI and OEM+ GUI experience](interaction/tui-and-gui.md): Task-oriented interfaces with progressive disclosure and accessible fallback.
- [DE-025 — Owned native integration surfaces](interaction/native-integration.md): Thin optional host adapters retain exact local or remote targeting and independent teardown.
- [DE-026 — Terminal sessions and capabilities](interaction/terminal-session.md): Channel-specific terminal capabilities, bounded rendering and owned restoration.
- [DE-027 — Interactive command shell](interaction/interactive-shell.md): Explicit persistent DiskEd sessions over the shared command model.
- [DE-028 — Output, progress and completion](interaction/output-and-progress.md): Separate human display, protocol events, diagnostics and recovery records.

## Operations

- [DE-101 — Bounded native inventory](operations/inventory.md): Independent operation contract for target.inventory.
- [DE-102 — Read-only partition-map verification](operations/map-verify.md): Independent operation contract for table.verify.
- [DE-103 — Read-only image acquisition](operations/acquire-image.md): Independent operation contract for image.acquire.
- [DE-104 — Explicit GPT-copy repair](operations/gpt-repair.md): Independent operation contract for table.gpt.repair.
- [DE-105 — Create or delete a partition entry](operations/partition-create-delete.md): Independent operation contract for partition.edit.plan.
- [DE-106 — Grow a partition and filesystem to the right](operations/grow-right.md): Independent operation contract for filesystem.grow-right.plan.
- [DE-107 — Shrink a filesystem and its container](operations/shrink-right.md): Independent operation contract for filesystem.shrink-right.plan.
- [DE-108 — Copy or move an extent-backed volume](operations/move-copy.md): Independent operation contract for partition.move.plan.
- [DE-109 — Filesystem-aware migration and representability](operations/filesystem-migrate.md): Independent operation contract for filesystem.migrate.plan.
- [DE-110 — Offline system and boot-dependent operations](operations/offline-boot.md): Independent operation contract for boot.offline.plan.
- [DE-111 — Health assessment and forensic workflow](operations/health-forensics.md): Independent operation contract for health.assess.
- [DE-112 — Sanitize, firmware and advanced administration](operations/destructive-admin.md): Independent operation contract for media.destructive.plan.
- [DE-113 — Create a filesystem through an explicit format plan](operations/filesystem-format.md): Formatting is a separately admitted destructive operation with consumer compatibility and verification.

## Platforms

- [DE-050 — Windows target profiles and qualification](platforms/windows-targets.md): NT-first builds with explicit loader, runtime, frontend and security limits.
- [DE-051 — DOS, JC-DOS, Carbon and OS/2 portability](platforms/dos-carbon-os2.md): Constrained native profiles without inventing device or BIOS guarantees.
- [DE-052 — Other hosts and storage domains](platforms/other-hosts-and-media.md): Preserve the universal direction without making distant ports release blockers.

## References

- [DE-090 — Research scope and unresolved verification](references/research-scope.md): Source provenance distinguishes inspected current files from inherited project discussion.

## Roadmap

- [DE-080 — Implementation sequence and first usable release](roadmap/implementation.md): A small Windows-native vertical slice before expanding storage authority.
- [DE-081 — Decision register and experiments](roadmap/decisions.md): Resolve high-cost ambiguities before treating a proposed baseline as frozen.
- [DE-082 — October amendment reconciliation](roadmap/amendment-review.md): Disposition of all supplied proposals, conflicting candidate IDs and bounded development readiness.
- [DE-083 — Review corrections at 08a8246](roadmap/corrective-review.md): Disposition of reproduced tool defects and staged terminal, protocol and asset recommendations.

## Safety

- [DE-040 — Threat model and trust boundaries](safety/threat-model.md): Adversarial media, local privilege boundaries and recovery failures are first-class inputs.
- [DE-041 — Broker identity and bounded authorization](safety/broker-and-authorization.md): Authenticate the request, exact executable, operator intent and live target.
- [DE-042 — Planner, action graph and simulation](safety/planning.md): Compile intents into explicit dependencies, resources and recovery obligations.
- [DE-043 — Journal, recovery and durability](safety/journal-and-recovery.md): Explicit recovery classes without false transactional or rollback claims.
- [DE-044 — Independent verification and efficient execution](safety/verification-and-performance.md): Optimize verified work, never cache away fresh safety checks.
- [DE-045 — Bounded responsiveness and failure containment](safety/degraded-operation.md): Bound waiting and resources without treating timeout as proof that effects stopped.

## Storage

- [DE-030 — Storage graph, identity and leases](storage/identity-and-graph.md): Layer-aware observations and live target revalidation.
- [DE-031 — Address spaces, geometry and data fidelity](storage/address-spaces.md): Checked half-open extents and multiple media semantics.
- [DE-032 — Partition-map parsing and validation](storage/partition-tables.md): Independent bounded readers for MBR, EBR and GPT before any writer.
- [DE-033 — Provider roles, admission and upstream reuse](storage/providers.md): Replace implementations without redefining operations or trusting claims as proof.
- [DE-034 — Windows NT provider strategy](storage/windows.md): Windows-native depth without treating storage restrictions as bypass targets.
- [DE-035 — Explainable capability resolution](storage/capability-resolution.md): Keep implementation, qualification, permissions, freshness and resource eligibility independent.
- [DE-036 — Acquisition consistency and observation effects](storage/acquisition-consistency.md): Distinguish byte capture from point-in-time consistency and separately authorize destination effects.
- [DE-037 — Filesystem features and media capabilities](storage/filesystem-capabilities.md): Qualify each operation against exact format features, consumers and address-space semantics.

## Change discipline

Edit canonical concepts/registries. Run `index` to refresh generated views, then `check`, tests and `manifest`. Existing integrity manifests become stale after legitimate edits. Checks do not approve content or prove runtime safety.
