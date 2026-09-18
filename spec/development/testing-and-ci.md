---
type: DiskEd Specification
title: Testing, validation and CI strategy
description: Differentiate schema checks, product tests, hardware evidence and recovery qualification.
resource: disked://spec/de-074
tags:
- disked
- development
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-074
  profile: disked-spec/1
  version: 0.1.0
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-004
  - DE-044
  requirements:
  - DE-REQ-074-01
  - DE-REQ-074-02
  - DE-REQ-074-03
---

# Testing, validation and CI strategy

## Bootstrap validation

The included tools validate OKF/profile structure, schemas/examples, links, stable IDs, requirement/test mappings, work dependencies, catalog references, invocation fixture policy and generated freshness. Their own unit tests cover malformed inputs and tooling safety. Passing these checks proves only the listed properties of this archive. No DiskEd executable, provider, physical disk or OS GUI is tested by the bootstrap.

## Product test pyramid

Unit and property tests cover checked arithmetic and graph invariants. Golden vectors and fuzzing cover MBR/EBR/GPT and hostile provider inputs. Differential tools expose disagreements but do not prove correctness by majority vote. State-model tests exercise authorization, attempts, journal transitions and cancellation. Fake providers enable frontend parity and negative capability tests. Images permit end-to-end mutation with fault injection. VMs cover loader, mount and boot behavior. Hardware tests cover controllers, sector sizes, removable media, locks and persistence.

Physical power loss is not equivalent to killing a VM process. A hardware-qualified claim requires real device evidence, exact firmware/controller/cache configuration and recovery exercise. No public CI worker or coding agent gets raw host disks. Use sacrificial lab assets and independent approval. Large corpora stay content-addressed outside ordinary source history.

## CI workflow

The baseline overlay includes a workflow template, not a silently activated supply-chain trust policy. Activate only after pinning actions/runners/dependencies to reviewed identities. Initial jobs: spec schema/links, generated drift, tooling tests and docs checks, all read-only. Product jobs add Windows profile compile/import audits and fake/image tests. A green PR does not authorize high-risk hardware effects or release signing.

## Efficient validation

Map module inputs to tests and record dependency hashes for reuse. Rerun impacted tests during iteration, then qualify the exact composed release. Translation or prose edits should not trigger multi-hour hardware campaigns; range arithmetic, journal, provider version or toolchain changes may invalidate broad evidence. A test command, working directory, exit code, logs, environment and artifact hashes are retained. Never mark skipped/unsupported tests as passes.

## Normative requirements

### DE-REQ-074-01

Spec/tooling validation MUST be labeled separately from product, OS, hardware and recovery qualification.

**Verification:** Inspect reports for explicit scope and non-capabilities.

### DE-REQ-074-02

CI MUST operate on disposable fixtures without raw host-device access or release keys.

**Verification:** Review workflow permissions and denied-path tests.

### DE-REQ-074-03

Test reuse MUST depend on actual changed inputs and a final composed-artifact qualification.

**Verification:** Modify a shared primitive/provider lock and inspect impact selection.

## Related specifications

- [DE-004](../foundation/requirements-and-traceability.md)
- [DE-044](../safety/verification-and-performance.md)
