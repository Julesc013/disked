---
type: DiskEd Specification
title: Provider roles, admission and upstream reuse
description: Replace implementations without redefining operations or trusting claims as proof.
resource: disked://spec/de-033
tags:
- disked
- storage
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-033
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-030
  - DE-022
  requirements:
  - DE-REQ-033-01
  - DE-REQ-033-02
  - DE-REQ-033-03
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Provider roles, admission and upstream reuse

## Narrow roles

Providers implement discovery, identity, topology, health, map read/write, filesystem inspection/mutation, volumes, pools, arrays, encryption, images, boot, recovery or verification. Avoid a monolithic interface forcing unrelated media into one API. A semantic operation has stable meaning across providers; platform-specific constraints remain explicit.

The trust chain is declaration -> conformance profile -> actual result -> admission -> scoped invocation. A source repository being popular, open or long-lived does not qualify a compiled binary on a target. Provider manifests include exact source/build IDs, binary hashes, protocol versions, operation set, non-capabilities, privilege, isolation, limits, recovery class, test evidence and revocation status.

## Composition forms

A built-in pure parser can run unprivileged. A tightly scoped OS-native provider can run in the broker. Complex third-party tools should generally be separate processes with exact arguments, environment, locale, timeout, executable identity and captured outputs. A static one-file provider can self-host in another process, but inherits the binary's loader/static initialization risks. The broker must not load arbitrary plugins from user directories.

If an external tool accepts only a device path and requires raw privileges, the broker cannot truthfully claim to constrain its writes to one extent without an enforcing mechanism. Label that provider as a broader trusted execution boundary, restrict admission accordingly, or use an image/offline sandbox. Handle-scoped and path-scoped enforcement are different security properties.

## Candidate upstreams

Windows documented APIs lead the native lane. DiskPart is a narrow compatibility executor, never the canonical parser. libparted/libfdisk/GPT fdisk are candidate table providers or differential oracles. Filesystem tools, TestDisk, ddrescue, Partclone and smartmontools have different roles. Their exact versions, licenses and capabilities require review before bundling; this archive does not grant redistribution or imply native Windows builds exist.

A replacement provider runs the same semantic fixtures and adversarial tests as its predecessor. Selection is policy-visible and pinned in plans. On failure, do not silently switch implementation during partially executed work. Recovery uses the admitted compatible closure or refuses with a required-environment explanation.

## Acquisition, ownership and feature gates

[Capability resolution](capability-resolution.md) keeps presence, implementation, qualification, permission, freshness and resources independent. [Package acquisition](../delivery/component-acquisition.md) separates version policy from source location and servicing ownership. Existing tools are not silently adopted; package trust does not admit storage effects. A denied or failed provider preserves other successful observations.

Each provider must qualify the exact format features and intended operation. Recognition is not repair; creation is not mounting or boot compatibility. Retain old recovery-compatible generations during servicing or withdrawal. SDK conformance follows [DE-078](../development/extension-sdk.md); installing an SDK enables no privileged discovery or listener.

## Normative requirements

### DE-REQ-033-01

Provider availability MUST require declared capability plus applicable evidence and policy, not a manifest claim alone.

**Verification:** Declare an untested mutation and confirm admission is denied.

### DE-REQ-033-02

Providers MUST NOT silently substitute or execute shell strings; exact code identity and typed arguments MUST be retained.

**Verification:** Replace provider binary or inject arguments and assert refusal.

### DE-REQ-033-03

Isolation claims MUST state what is actually enforced, including whether a child can open arbitrary raw paths.

**Verification:** Threat-model review and sandbox escape/handle-scope tests.

## Related specifications

- [DE-030](identity-and-graph.md)
- [DE-022](../interaction/protocol.md)
