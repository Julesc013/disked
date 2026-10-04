---
type: DiskEd Specification
title: Licensing, provenance and release trust
description: Keep licensing decisions explicit and qualify the actual dependency closure.
resource: disked://spec/de-062
tags:
- disked
- delivery
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-062
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-060
  - DE-040
  requirements:
  - DE-REQ-062-01
  - DE-REQ-062-02
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Licensing, provenance and release trust

## Owner decision

Earlier discussions alternated Apache-2.0 and MIT OR Apache-2.0. This archive does not silently choose a repository license on the owner's behalf. `DE-DEC-001` proposes dual permissive licensing for original DiskEd code and requires owner ratification before a public code release. Publication on GitHub alone is not a license grant. The archive contains original specification/tooling, not copied third-party implementation or SDKs.

Keep each dependency's actual license and provenance. Library linkage, modified upstream source, external executable and recovery image are different composition cases. A process boundary is not a universal legal exemption. Source-available Eureka/Dominium material is not automatically open-source reusable code. Adopt patterns without copying implementation unless ownership and permissions are established.

## Reproducible supply chain

Record source tree, dependency locks, toolchains, sysroots, build flags, generated resources, binary hashes, notices, SBOM, provenance and qualification receipts. Use exact versions and content identities; do not run "latest" dependencies in a release build. Network acquisition is separate from offline build and from privileged runtime. Signing keys never enter agent context or public CI artifacts.

## Signing and updates

Define trusted publishers, timestamping, revocation and offline recovery policy per OS. Obsolete OS trust stores may not validate modern signatures; do not disable integrity checking silently or claim modern authenticity on that basis. Checksums detect corruption but do not authenticate origin. A current signed release can contain an unsafe provider; revocation and capability withdrawal need explicit metadata and an offline operator path.

## Security response

Before public physical-write release, create a real vulnerability reporting route, owner roster, triage, key compromise procedure, provider revocation and supported-version policy. Do not invent a staffed safety council or security email address in the bootstrap. Branch protections and two-person approval are operational settings to establish, not assurances achieved by adding Markdown.

## Retained owner choice

The supplied proposals recommend both Apache-2.0 alone and MIT OR Apache-2.0. Neither is an explicit owner license selection in the current request. DE-DEC-001 remains open before public code distribution/external contribution policy and dependency bundling claims. This does not prevent authorized local fake-provider prototyping. DCO/CLA choices, actual security-response staffing and release signing remain explicit governance work.

Do not infer distribution rights from public source, process isolation or a proposed rescue recipe. Retain component provenance and separately review toolkit icons, historical SDKs, recovery OS images and provider packages. AIDE dev is a pinned development input, not a stable product dependency or license grant for DiskEd.

## Normative requirements

### DE-REQ-062-01

Public code release MUST wait for an explicit owner license decision and complete dependency notices.

**Verification:** DE-DEC-001 acceptance and license-closure review.

### DE-REQ-062-02

A release MUST bind exact sources, dependencies, artifacts and qualification; checksum equality MUST NOT be called authenticity.

**Verification:** Reproduce unsigned payload and independently verify release signatures where supported.

## Related specifications

- [DE-060](composition.md)
- [DE-040](../safety/threat-model.md)
