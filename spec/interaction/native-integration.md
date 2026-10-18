---
type: DiskEd Specification
title: Owned native integration surfaces
description: Thin optional host adapters retain exact local or remote targeting and independent teardown.
resource: disked://spec/de-025
tags:
- disked
- interaction
generated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
status: draft
disked:
  id: DE-025
  profile: disked-spec/1
  version: 0.1.2-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-023
  - DE-060
  - DE-061
  requirements:
  - DE-REQ-025-01
  - DE-REQ-025-02
updated:
  by: codex
  at: '2026-10-18T09:32:34.896855+00:00'
  scope: Proposed Windows reference experiments; no execution or qualification claim
sources:
- id: windows-reference-mmc
  resource: ../references/sources.json#windows-reference-mmc
- id: windows-reference-snap-ins
  resource: ../references/sources.json#windows-reference-snap-ins
- id: windows-reference-shell
  resource: ../references/sources.json#windows-reference-shell
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Owned native integration surfaces

## Optional surfaces

The standalone CLI/TUI/GUI is the first product. Later integration may add a DiskEd-owned MMC console/Computer Management extension, Explorer inspect/format entrypoints, a drive property page, image associations or PowerShell projection. There is no assumed universal default-disk-manager hook. Keep Microsoft tools available as independent fallback; do not overwrite system files, impersonate built-in commands or take over Microsoft COM identities.

[MMC snap-ins](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/mmc/snap-ins) are COM in-process DLLs. A genuine snap-in therefore needs a target/bitness-qualified adapter beyond the standalone EXE. One download may carry it, but that is not a one-file installed footprint. Shell adapters perform bounded object resolution and dispatch; storage parsing, long I/O and mutation run outside Explorer/MMC adapter code.

## Reference experiments

Treat `.msc` as saved MMC console composition and distinguish it from the
snap-in implementation and storage backend. Observe only the concrete surface
being implemented: host bitness, selected computer, keyboard/control behavior,
refresh, unavailable actions, error reporting, disconnect and teardown. Explorer
handlers and service lifecycle have separate native contracts. Findings enter
shared reviewed semantics; they do not authorize Microsoft identity takeover,
system-file replacement or storage operations in an in-process adapter.
Follow [DE-074](../development/testing-and-ci.md) for exact evidence and the
Windows reference plan (`docs/windows-reference.md` in the implementation repository) for staged work.
An adapter's registration remains separate managed lifecycle work.

## Registration, targeting and teardown

Each implemented surface records stable integration ID, host/build, mechanism/ABI, artifact identities, scope, servicing owner, owned registrations/shortcuts, target binding, teardown, fallback and qualification evidence. Strict portable mode creates none of these records. Registration is explicit managed lifecycle work. Uninstall removes only owned entries, preserving unrelated later changes.

A launch selector is an untrusted locator, not storage authority. Resolve it to a fresh composite identity in the shared engine. MMC remote retargeting invalidates local selection; loss of that host yields unavailable, never local fallback. A Format with DiskEd action opens a plan and does not approve it. Native styling uses host conventions and licensed/original resources, without an endorsement claim.

## Normative requirements

### DE-REQ-025-01

Native integrations MUST be thin, explicitly owned and removable; strict portable execution MUST create no persistent registrations.

**Verification:** Install/remove a fixture adapter, preserve foreign entries, and trace portable execution for zero integration writes.

### DE-REQ-025-02

Integration selectors MUST be revalidated by the shared engine with explicit host identity before any effects.

**Verification:** Change drive letter, replace media and disconnect a remote host after selection; no action may follow a stale locator or switch to local storage.
