---
type: DiskEd Specification
title: Single-entrypoint composition and release identity
description: One product command with explicit dependency, extraction and isolation properties.
resource: disked://spec/de-060
tags:
- disked
- delivery
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-060
  profile: disked-spec/1
  version: 0.1.2-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-013
  - DE-050
  - DE-041
  requirements:
  - DE-REQ-060-01
  - DE-REQ-060-02
  - DE-REQ-060-03
  - DE-REQ-060-04
updated:
  by: codex
  at: '2026-10-09T22:23:24.522988+00:00'
  scope: DE-W062 external read-only H/D/offline ZIP fixture contract; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Single-entrypoint composition and release identity

## Composition contract

Each target has one `disked` product basename and a display name DiskEd. Statically compose application semantics, command dispatch, CLI, TUI, one native GUI, eligible built-in providers, resource pack and internal process roles. Do not ship case-distinguished `disked.exe` and `DiskEd.exe` as separate files. A self-spawned broker/provider host is another process of the same verified image, not another public entrypoint.

Declare independently: single entrypoint, single distributed file, zero extraction, bundled dependencies, system-runtime prerequisites, optional helpers, app-bundle layout and privilege boundary. A one-file extractive managed app is not equivalent to a native mapped image. Prefer the latter for the reference Windows tool. Legal or security needs can justify separately packaged providers, but the exception is visible and no generic file-count rule overrides safety.

## Release identity

A product tag such as `v0.1.0` can publish multiple target/profile assets. Record product version, command/schema ABI versions, target-profile revision, provider closure, toolchain and build identity separately. The installed basename remains stable; archive names identify product/version/target. Native Windows profiles may share a tested artifact across several OS releases; do not multiply binaries without a measured reason.

## Payload identity

One staging manifest owns the portable payload. A direct binary, portable archive and Universal Setup wrapper derive from those exact bytes. Sign before computing final distribution checksums where signature insertion changes bytes. Reproducibility of unsigned output and equality of signed installed payload are separate checks. Embedded manifests cannot include their own entire final-image hash recursively; use external signed manifest bindings.

## Servicing

Avoid overwriting a running broker or provider closure. Use side-by-side versioned payload roots and explicit activation when installed. Keep the version that can recover an in-progress operation. Uninstalling DiskEd must not delete customer images, evidence, unknown files or recovery state still needed by an operation. Portable copy-and-run remains independent of setup registration.

## Finite optional Setup construction

Let H be a payload-free, product-bound Setup host; D the finalized DiskEd executable optionally containing inactive H; and S an offline Setup carrier containing exact finalized D and selected extras. Build/finalize H, embed it in D, finalize/sign D, then construct/finalize/sign S. H contains neither D nor S; D does not contain S. H cannot embed D's final whole-file hash. External release/source bindings carry final identities.

Ordinary D startup does not extract or execute H. Explicit maintenance validates H and the source/package binding through a qualified upstream adapter and protected staging where needed. Exporting H does not recreate publisher-signed S. Corrupt D requires an independent verified host/carrier and source. A linked minimal SDK adapter or external wrapper is a separately identified alternative; it cannot inherit qualification from the embedded-host design.

One entrypoint is independent of process count and installed adapter/driver footprint. The first fake build needs only a small manifest/registry from [DE-014](../architecture/component-model.md); complete H/D/S implementation and channel generators are later delivery work, not prerequisites for image parsing.

## Initial finite carrier fixture

The [carrier profile](../catalog/carrier-fixture-prototype.json) selects a
product-bound native read-only H fixture, exact separately finalized dev.36 D,
and an offline stored ZIP fixture S. This does not implement embedded H or a
native installer carrier. H is compiled from the original pinned CoreStatic
closure under DiskEd-owned CMake; its product/source inspection creates no
provider context and reports generic verification/lifecycle unavailable.

Build H without D/S inputs, select D independently, bind H/D descendants in
inner metadata, construct S, then bind S externally. This topology has no
containment cycle or final-image hash recursion. The builder copies only the
independently verified fixed D entry into new owned staging and never launches
or extracts carrier contents. Original D inventory/build-info and H observation
remain separately selected expectations; hashes/observations do not authenticate
a publisher or supply native qualification by themselves.

Retain independent decoded-byte inventory checks for exact H/D/metadata entries.
Every existing output root refuses; incomplete fixture output remains for
inspection without cleanup or replay. A verified independently selected H may
inspect source structure when a generated copy of D is damaged. That is an
inspection route, not successful repair, recovery or generic lifecycle admission.

## Normative requirements

### DE-REQ-060-01

Every composition MUST explicitly declare single-file, extraction, dependencies and helper exceptions.

**Verification:** Inspect manifests and run a clean-system one-file qualification.

### DE-REQ-060-02

Published portable and setup-installed product payloads MUST be byte-identical for the same signed target artifact.

**Verification:** Hash staged, extracted and installed trees and compare.

### DE-REQ-060-03

Servicing MUST preserve the exact execution/recovery closure needed by in-progress operations.

**Verification:** Update/uninstall during a fake active operation and require defer/refusal.


### DE-REQ-060-04

Embedded/external Setup compositions MUST have finite containment and nonrecursive identity bindings, with ordinary startup free of Setup effects.

**Verification:** Reject cyclic H/D/S and recursive-hash fixtures; verify payload equality, inactive embedded resources and independent damaged-D recovery before Setup release.

## Related specifications

- [DE-013](../architecture/configuration.md)
- [DE-050](../platforms/windows-targets.md)
- [DE-041](../safety/broker-and-authorization.md)
