---
type: DiskEd Specification
title: Canonical glossary and naming
description: Unambiguous names for identity, state, effects, evidence and delivery.
resource: disked://spec/de-005
tags:
- disked
- foundation
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-005
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R1
  depends_on:
  - DE-001
  requirements:
  - DE-REQ-005-01
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Canonical glossary and naming

| Term | Meaning |
|---|---|
| Target | A selected resource or source whose identity must be established. |
| Device | An observed hardware or virtual presentation; not necessarily a disk. |
| Extent | Half-open range `[start, end)` in an explicitly named address space. |
| LBA | Logical block address; its unit comes from the device, never implicitly 512 bytes. |
| Partition | A region described by a partition map; not synonymous with a volume or filesystem. |
| Volume | A storage-manager object, possibly spanning or transforming multiple extents. |
| Observation | A source-specific captured fact, including uncertainty. |
| Claim | An interpretation backed by observations; may conflict with another claim. |
| Snapshot | Immutable captured graph, not necessarily an OS/filesystem snapshot. |
| Revision | A version identifier for a captured state. |
| Fingerprint | Digest of selected canonical state; not a hardware identity by itself. |
| Intent | Requested semantic outcome. |
| Plan | Immutable ordered/dependent effects and their preconditions. |
| Approval | A bounded authorization referencing an exact plan; not a general privilege bit. |
| Operation | Durable execution identity across clients and retries. |
| Attempt | One dispatch/execution try associated with an operation. |
| Journal | Durable progress/recovery records, not an audit summary. |
| Evidence | Recorded observations of actual actions or tests with source identity. |
| Admission | Policy decision permitting one qualified capability in one scope. |
| Recovery | A defined response to partial execution; not automatically rollback. |
| Self-contained | Product dependencies are included or guaranteed system components. |
| Single-file | One delivered product file; independent of extraction and process count. |
| Zero-extraction | No executable code unpacked to another location during normal startup. |
| OEM+ | Native platform conventions with better workflows, not a simulated skin. |

Use the spelling DiskEd in prose, `disked` in machine identifiers and executable basename, and `org.disked.*` for protocol identifiers. Use ASCII lowercase kebab-case paths and commands. Preserve arbitrary user filenames as data rather than forcing that source-code convention onto media. Case-only source paths are prohibited for Windows portability.

Units are IEC for binary quantities (`KiB`, `MiB`, `GiB`) and SI when explicitly selected. A bare size argument is invalid unless a command declares its unit. Relative resize syntax must name whether it refers to length, start or end. UI display rounding must never alter exact requested geometry.

## Composition and qualification vocabulary

| Term | Meaning |
|---|---|
| Component / preset | Selectable module / convenient selection, not a privilege profile. |
| Provider | Exact implementation of operation capabilities; declaration is not admission. |
| Composition | Immutable selected component/provider and loader closure for a target. |
| Target profile / host qualification | Build/runtime contract / evidence for an exact artifact on a named host. |
| Package / carrier / channel | Immutable delivery unit / its container format / distribution route. |
| Servicing owner | Sole mechanism authorized to maintain a managed resource. |
| Execution role | Coordinator, observer, planner, executor, verifier or recovery executor bound to a host. |
| Alias set / effect footprint | Known locators of one resource / bounded objects or ranges an action may affect. |
| Consumer compatibility | Ability of an intended OS/firmware/application to use the resulting format. |
| Quiescence | Established absence of conflicting outstanding effects; not a timeout or cancellation request. |
| Recovery closure | Exact code, state, backups, credentials references and resources needed to reconcile work. |
| Support claim | Scoped assertion tied to implemented behavior and retained qualification evidence. |

Host OS, guest/on-disk format, firmware, access path, granted authority and assurance are independent. ANSI/Unicode describes text interfaces, not processor bitness. Files-only portability concerns deployment effects, not reversal of storage writes or absence of OS-generated traces.

## Normative requirements

### DE-REQ-005-01

All address and size fields MUST declare units and use checked conversions; UI rounding MUST NOT become storage geometry.

**Verification:** Round-trip boundary and non-power-of-two-sector examples.

## Related specifications

- [DE-001](charter.md)
