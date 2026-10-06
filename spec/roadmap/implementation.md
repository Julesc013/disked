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
  version: 0.1.2-proposed.2
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
  at: '2026-10-04T07:27:09.204646+00:00'
  scope: CLI syntax refinement; proposed, no native parser or acceptance claim
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
- id: review-08a8246-2026-10-04
  resource: ../references/sources.json#review-08a8246-2026-10-04
- id: cli-refinement-2026-10-04
  resource: ../references/sources.json#cli-refinement-2026-10-04
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

## Owner-selected 0.1.0 programme

The 2026-10-06 goal explicitly selects **all platforms and storage operations**
specified at base `40ac8ec02778b7c25100421147fc1e107fa14ed5` as the 0.1.0 finish
line. This is larger than the first useful inspector milestone below. The retained
`.aide/programmes/disked-0.1.0.json` records the exact scope and development grant.
Local implementation may continue across units after tests and recorded agent
review; owner acceptance, release and storage privilege gates remain separate.
This policy permits progress without manufacturing accepted prerequisites.
Missing target environments remain unverified, not implied platform passes.

## Work model

`work/units.json` defines small dependency-ordered units with source IDs, allowed paths, deliverables, tests, gates and stop states. `specctl next` reports ready-to-review/design work; it does not grant execution. Do not convert this roadmap into one giant agent prompt. Initial units include exact acceptance outcomes and forbid creating a broad untested source tree.

## First public usefulness

The first public software can be an honest Windows Storage Inspector with one native entrypoint, exact inventory, image validation, table backup and evidence export. A later release earns "partition editor" for the operations it actually qualifies. Public docs distinguish planned, implemented and tested capability.

## Bounded development-readiness plan

The October amendment is specification/tooling work within DE-W000, stopped at needs-review. Owner acceptance binds the actual amended content; it is not manufactured from a recommendation to ratify. Once the relevant baseline review and bounded code grant exist, DE-W010 is the next native implementation unit.

Keep DE-W010 small: one native executable, essential build/mode/command discovery, declared loader closure, fake-only composition and actual build/import evidence. DE-W011-016 add invocation, command/protocol, graph and frontends, and unprivileged process roles. DE-W017 verifies the combined failure matrix; DE-W018 runs nonblocking historical primitive/text probes. Record actual native build/test commands when the toolchain is selected, not fictional commands or only the spec-tool floor.

M2/M3 image parsing and inspection can proceed without finished Setup or production journal work. DE-W035 later proves optional read-only native integration. DE-W060/062 cover pinned Setup and finite carrier/owner contracts; DE-W063 covers artifact completeness. DE-W043 covers image-only formatting after the journal gate. Shared storage, tape/optical, conversions and repair split into operation-specific work through DE-W080. The existing M0-M8 risk order remains.

License, launch, journal, elevation, canonicalization, setup-host, channel and historical-terminal decisions block only their affected implementation or release claim. A first public inspector is a selected qualified release, not completion of all historical targets. AIDE remains optional development infrastructure; roughly weekly pin reviews are tracked as DE-W061 follow-up.

## Corrective pass and scoped follow-up

Address review R01-R05 inside DE-W000: mixed-path impact, complete declared task inputs, revision-bound receipt projection, protocol bounds/identities and explicit CLI prompt policy. These fixes are specification tooling, not storage-runtime implementation. The architecture/source prefix and finite portable-first delivery stay in place.

DE-W010-016 remain the native fake slice. DE-W019 adds the explicit shell using shared command/terminal contracts; DE-W017 then covers shell parity and guarded late-result/cancellation scenarios. DE-W012 owns typed parser/help/completion and producer/reader protocol compatibility. DE-W033 gates multi-resource acquisition; DE-W040/041 gate immutable-plan receipts, recovery traits and real journal encoding. None makes every future storage or legacy decision a prerequisite for the first fake executable.

## CLI syntax refinement after 9493381

The proposed grammar now lets users append or intersperse accepted options, registers ordinary-word shortcuts and makes contextual help independent of storage prerequisites. DE-W012 owns the native parser, typed parameter completion, no-effects-before-validation traces and shared conformance corpus. DE-W019 owns editable error recovery and measured shortcut/completion usability. DE-W018/071 reuse parser cases when a target's parser is admitted; this does not expand the first fake executable or require mature historical ports first. DE-W012 now executes the shared vectors and option-position permutations against the native Windows parser. Target-specific evidence remains separate; this does not qualify other tokenizers or hosts.

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

## DE-W010 executable boundary

The scoped DE-W000 review at `95cce28f801c726ca61816b7d2a974b3c7bce07e` supports the current explicitly granted fake-only implementation. [DE-079](../development/native-bootstrap.md) closes its execution contract as part of development. This console-only composition implements human help/build/command discovery; it does not complete M1. Owner baseline and implementation acceptance remain separate and pending. Review actual native evidence before proceeding to DE-W011/012; retain legacy and storage decisions at their existing gates.

## Local programme implementation progress

Under the explicit 0.1.0 development grant, DE-W012 supplies synchronous commands,
DE-W011 supplies the current Windows invocation subset, and DE-W013 supplies the
immutable fake graph/shared service. Retained tests and agent review permit
local continuation into DE-W014/015. This does not close M1, owner acceptance,
async operation, historical-platform or release/storage qualification gates.

DE-W014 now exercises the native console frontend in screen and linear modes,
including actual input, Ctrl+C, resize and caller-state restoration. DE-W015 can
reuse the service/model semantics for the Win32 frontend under the programme
grant. This leaves screen-reader/remote/legacy and the rest of M1 unqualified.
