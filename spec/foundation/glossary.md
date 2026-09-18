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
  version: 0.1.0
  authority: proposed-normative
  review: pending
  risk: R1
  depends_on:
  - DE-001
  requirements:
  - DE-REQ-005-01
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

## Normative requirements

### DE-REQ-005-01

All address and size fields MUST declare units and use checked conversions; UI rounding MUST NOT become storage geometry.

**Verification:** Round-trip boundary and non-power-of-two-sector examples.

## Related specifications

- [DE-001](charter.md)
