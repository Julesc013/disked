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
  version: 0.1.0
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

## Related specifications

- [DE-013](../architecture/configuration.md)
- [DE-050](../platforms/windows-targets.md)
- [DE-041](../safety/broker-and-authorization.md)
