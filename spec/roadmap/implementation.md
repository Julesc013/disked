---
type: DiskEd Specification
title: Implementation sequence and first usable release
description: A small Windows-native vertical slice before expanding storage authority.
resource: disked://spec/de-080
tags:
- disked
- roadmap
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-080
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-001
  - DE-074
  - DE-075
  requirements:
  - DE-REQ-080-01
  - DE-REQ-080-02
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Implementation sequence and first usable release

## Gate sequence

**M0 — Review and bootstrap.** Accept the source/authority model, resolve foundational open decisions, install shared instructions, run the spec/tool tests and commit a baseline. This is not a code release or physical-write grant.

**M1 — One executable over fake storage.** Build native `disked` with build/mode/command inspection, fake target inventory, machine output, TUI and a minimal Win32 GUI. Qualify invocation behavior on XP and current Windows. Exercise self-spawn/IPC without real elevation/storage effects. Freeze command spelling and image-subsystem policy only after evidence.

**M2 — Read-only format core.** Implement checked arithmetic and raw-image MBR/EBR/GPT parsing, hostile metadata diagnostics and independent comparison. Add fake-provider frontend parity. Do not use VHD mounting when a raw image reader can avoid host effects.

**M3 — Native Windows inspection.** Enumerate disks/volumes/mounts with fresh composite identity, preserve unknown layers, audit imports and test XP/7/10/11. Read-only acquisition has a separate case/data policy and no claim of media safety. Build a useful workshop inventory and evidence product.

**M4 — Imaging and evidence.** Resumable image acquisition, bad-sector map, explicit substituted bytes, hashes and case reports. Verify known images and preserve privacy. Refuse repair of original failing media by default.

**M5 — Image-only mutation.** Accept journal encoding/durability design. Implement map changes only on disposable image fixtures with simulated interruption, then filesystem-provider plans. No host raw-device writes.

**M6 — Privileged NT broker and constrained physical operations.** Independent security review and lab qualification. Admit selected healthy non-system basic MBR/GPT operations one at a time. No system move, encryption, pools or unknown metadata under a generic capability.

**M7 — Offline recovery and system tasks.** Exact recovery closures, cross-boot identification, boot/BitLocker dependencies and interruption exercises. Only then admit nonoverlapping moves, overlapping moves and start-boundary movement as separate capabilities.

**M8 — Broader systems and media.** Following early nonblocking primitive/text probes, full Carbon/DOS/OS2, additional GUIs, filesystems, pools, tape/optical/flux and enterprise coordination grow behind stable contracts without blocking useful NT releases.

## Work model

`work/units.json` defines small dependency-ordered units with source IDs, allowed paths, deliverables, tests, gates and stop states. `specctl next` reports ready-to-review/design work; it does not grant execution. Do not convert this roadmap into one giant agent prompt. Initial units include exact acceptance outcomes and forbid creating a broad untested source tree.

## First public usefulness

The first public software can be an honest Windows Storage Inspector with one native entrypoint, exact inventory, image validation, table backup and evidence export. A later release earns "partition editor" for the operations it actually qualifies. Public docs distinguish planned, implemented and tested capability.

## Bounded development-readiness plan

The October amendment is specification/tooling work within DE-W000, stopped at needs-review. Owner acceptance binds the actual amended content; it is not manufactured from a recommendation to ratify. Once the relevant baseline review and bounded code grant exist, DE-W010 is the next native implementation unit.

Keep DE-W010 small: one native executable, essential build/mode/command discovery, declared loader closure, fake-only composition and actual build/import evidence. DE-W011-016 add invocation, command/protocol, graph and frontends, and unprivileged process roles. DE-W017 verifies the combined failure matrix; DE-W018 runs nonblocking historical primitive/text probes. Record actual native build/test commands when the toolchain is selected, not fictional commands or only the spec-tool floor.

M2/M3 image parsing and inspection can proceed without finished Setup or production journal work. DE-W035 later proves optional read-only native integration. DE-W060/062 cover pinned Setup and finite carrier/owner contracts; DE-W063 covers artifact completeness. DE-W043 covers image-only formatting after the journal gate. Shared storage, tape/optical, conversions and repair split into operation-specific work through DE-W080. The existing M0-M8 risk order remains.

License, launch, journal, elevation, canonicalization, setup-host, channel and historical-terminal decisions block only their affected implementation or release claim. A first public inspector is a selected qualified release, not completion of all historical targets. AIDE remains optional development infrastructure; roughly weekly pin reviews are tracked as DE-W061 follow-up.

## Normative requirements

### DE-REQ-080-01

Implementation MUST proceed through explicit phase gates; no physical mutation may be admitted by completing a fake/image-only milestone.

**Verification:** Inspect work dependency/gate graph.

### DE-REQ-080-02

Every selected work unit MUST have bounded outputs, context, tests and a needs-review stop state.

**Verification:** Validate the work catalog and export projection.

## Related specifications

- [DE-001](../foundation/charter.md)
- [DE-074](../development/testing-and-ci.md)
- [DE-075](../development/governance-and-review.md)
