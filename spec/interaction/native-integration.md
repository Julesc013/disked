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
  version: 0.1.3-proposed.1
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
  at: '2026-10-18T10:43:10+00:00'
  scope: Bounded MMC/shell host, selection and lifetime experiments; proposed, no native qualification
sources:
- id: windows-reference-mmc
  resource: ../references/sources.json#windows-reference-mmc
- id: windows-reference-snap-ins
  resource: ../references/sources.json#windows-reference-snap-ins
- id: windows-reference-shell
  resource: ../references/sources.json#windows-reference-shell
- id: windows-reference-computer-management-nodes
  resource: ../references/sources.json#windows-reference-computer-management-nodes
- id: windows-reference-computer-management-retargeting
  resource: ../references/sources.json#windows-reference-computer-management-retargeting
- id: windows-reference-shell-activation
  resource: ../references/sources.json#windows-reference-shell-activation
- id: windows-reference-shell-modern-menu
  resource: ../references/sources.json#windows-reference-shell-modern-menu
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

Select one integration surface and exact host/build/ABI/bitness profile for each
bounded prototype. Qualify activation, typed dispatch, multiple instances and
callback lifetime separately from storage-provider capability. Unsupported hosts,
missing engines, denied providers and delayed responses produce explicit bounded
outcomes while the host remains usable. Compare the adapter's typed requests and
results with the existing standalone service for the same fixtures; introduce no
second parser, planner, command registry or storage interpretation.

Apply each case to the selected mechanism. Unsupported or omitted contexts retain
explicit refusal/unavailable behavior and recorded scope; completing one prototype
does not require implementing another surface.

### MMC and Computer Management

Record saved-console composition separately from standalone, extension or dual
snap-in roles. Use DiskEd-owned COM identities and documented extension nodes;
Computer Management's Storage node is the relevant candidate. Qualify the actual
MMC/snap-in host architecture rather than inferring support from the standalone
executable's successful launch.

Retargeting removes the old extension subtree while its component instance can
survive. Bind selection and pending presentation to the exact computer and view
generation. Invalidate the old selection on retarget; reacquire the new target
from the host contract. A delayed result from computer A may remain historical
evidence for A, but cannot publish as computer B or drive B's next request.
Independent adapter instances retain independent selection/callback ownership.

### Shell activation profiles

Choose the simplest sufficient native activation contract. Classic executable
verbs, COM local-server verbs and Windows 11 package/sparse-package context-menu
commands have separate registration and hosting profiles. Qualify the selected
mechanism's process architecture, item contexts and actual activation behavior;
do not assume all handlers are executable launches or share one COM host model.
Property-page and namespace handlers need their own selected contracts.

Preserve the invocation's structured shell selection where the mechanism supplies
it. An executable verb accepts only its declared locator subset, with lossless
encoding and tested argument boundaries; unsupported namespace items are refused.
Do not reinterpret display labels or concatenated shell text as a storage request.
Cover supported single/multiple selections, spaces, non-ASCII names, malformed
locators and removal/replacement between menu construction and invocation.
Menu-state callbacks perform bounded presentation work; dispatch long operations
through the existing execution model after invocation.

## Registration, targeting and teardown

Each implemented surface records stable integration ID, host/build, mechanism/ABI, artifact identities, scope, servicing owner, owned registrations/shortcuts, target binding, teardown, fallback and qualification evidence. Strict portable mode creates none of these records. Registration is explicit managed lifecycle work. Uninstall removes only owned entries, preserving unrelated later changes.

A launch selector is an untrusted locator, not storage authority. Resolve it to a fresh composite identity in the shared engine. MMC remote retargeting invalidates local selection; loss of that host yields unavailable, never local fallback. A Format with DiskEd action opens a plan and does not approve it. Native styling uses host conventions and licensed/original resources, without an endorsement claim.

Adapter unload or host closure retires only adapter-owned presentation and callback
state. It does not establish an independently owned operation's cancellation,
exit or recovery outcome; preserve the lifetime and identity rules in
[DE-015](../architecture/execution-topology.md),
[DE-022](protocol.md) and [DE-045](../safety/degraded-operation.md).
The first read-only prototype can test remote selectors through injected states.
Actual remote observation/execution still requires its separate authenticated
host/provider/transport contract; no listener or local fallback is admitted by
these integration tests. Relevant gates remain in DE-015/DE-022,
[DE-041](../safety/broker-and-authorization.md) and
[DE-052](../platforms/other-hosts-and-media.md).

## Normative requirements

### DE-REQ-025-01

Native integrations MUST be thin, explicitly owned and removable; strict portable execution MUST create no persistent registrations.

**Verification:** Exercise the selected host/ABI/bitness, failed activation, independent instances, load/unload and missing/stalled backend fixtures. Compare typed requests/results with the shared standalone service. Install/remove a fixture adapter, preserve foreign and subsequently changed entries, and trace portable execution for zero integration writes.

### DE-REQ-025-02

Integration selectors MUST be revalidated by the shared engine with explicit host identity before any effects.

**Verification:** Exercise supported structured selections and quoted/non-ASCII/malformed locators. Change drive letter, replace media and disconnect or retarget a remote host after selection; deliver the old host's delayed result after retargeting. No action may follow a stale locator, adopt another instance's selection or switch to local storage.
