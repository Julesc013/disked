---
type: DiskEd Specification
title: Context packs, handoffs and retrieval
description: Continue work without carrying the entire conversation or specification into every session.
resource: disked://spec/de-071
tags:
- disked
- development
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-071
  profile: disked-spec/1
  version: 0.1.2-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-070
  - DE-002
  requirements:
  - DE-REQ-071-01
  - DE-REQ-071-02
  - DE-REQ-071-03
updated:
  by: codex
  at: '2026-10-04T06:41:03.817694+00:00'
  scope: 08a8246 review corrections; proposed, not accepted
sources:
- id: review-08a8246-2026-10-04
  resource: ../references/sources.json#review-08a8246-2026-10-04
---

# Context packs, handoffs and retrieval

## Entry sequence

A new human, Codex, Claude or chat session reads root AGENTS, `spec/index.md`, the current bundle status and one selected work unit. It resolves relevant concepts by stable ID through the index rather than rereading every file. `specctl context --work DE-W010 --output ...` builds a bounded pack from mandatory safety/authority documents, the work definition, its declared context and transitive normative prerequisites. It records the Git head where available, dirty state and exact selected file hashes.

The tool counts UTF-8 bytes, not fictional provider-independent tokens. It fails if the required pack exceeds the supplied byte budget; it never silently truncates safety constraints. Split the work or enlarge the explicit budget. Optional background sources are named as omitted, not smuggled into scope. Context freshness must be checked before editing or applying a patch; a hash mismatch requires regeneration and re-review.

## Handoff content

Record task and base revision, files actually read, changed files, rationale, commands actually run, observed results, artifact hashes, uncertainty, blockers and next safe step. Use `not_run` when a test did not run. Do not record speculative completion because a model wrote code. A handoff is not approval. Negative knowledge matters: rejected alternatives, failed approaches, known defects and their exact test evidence prevent rediscovery.

## Chat mode

A chat tool may read GitHub but lack checkout, shell or write permission. It should retrieve index/status/work at one revision, fetch only relevant files and return a bounded patch or proposal with a handoff. Do not claim execution, commit or push without actual tools/results. A copied GitHub URL is a locator, not proof that the current model has access. When access fails, a user-supplied context pack is a portable fallback, not permission to invent repository state.

## Cache and staleness

Search and indexes are rebuildable. Git history and exact records remain authoritative. An embedding or vector database is optional and must carry source hashes, privacy limits and a freshness policy. The bootstrap uses deterministic keyword search and explicit context selection; no cloud, model call or vector service is required. Facts likely to change—SDKs, tool versions, capabilities—have source review tasks rather than permanent memory claims.

## Multi-agent work

One owner per active work unit; isolated worktrees and explicit allowed paths. Parallel tasks require independent outputs or a declared integration owner. A lock file in Git is not a distributed lock. Conflicting edits are reviewed against current base and affected requirements. Do not regenerate the whole spec to resolve a local merge conflict.

## Declared task-input closure (v2)

`catalog/input-dependencies.json` owns typed input declarations: canonical path, kind, content/artifact delivery, concept owners and dependency IDs. Each work unit names additional `required_inputs`. A shared resolver combines the selected work, mandatory concept prerequisites, registry edges and applicable repository `AGENTS.md`/`CLAUDE.md` chain. Context generation and impact routing consume that same closure. Unknown inputs, dependency cycles and missing required files fail explicitly. Instruction discovery stays within the selected repository; session-level instructions supplied outside it remain the coordinator's responsibility.

Context manifest v2 uses repository-relative names (`spec/` is the logical bundle root even with `--root`). Required content appears in `context.md`; required artifacts are copied byte-for-byte beneath `artifacts/`, with kinds, lengths and hashes in the manifest. Optional background is listed separately. A hash with no available artifact is insufficient for a portable work pack. Artifacts remain data: their existence does not authorize executing scripts or media content.

Verification resolves the current closure again, compares the complete input set and delivery kinds, checks source and copied bytes, and detects added instructions or removed manifest entries even when Git HEAD is unchanged or unavailable. Unrelated optional background does not invalidate a task. It proves freshness of the **declared** dependencies, not completeness of all possible semantic dependencies or an authenticated approval.

The existing default content budget remains 120,000 UTF-8 bytes. A separately declared artifact budget defaults to 8 MiB. Either overflow fails before files are written; neither permits truncation. The corrective review and broader native contexts explicitly request 180,000 content bytes because instruction and contract coverage increased. Split narrower work when its full prerequisites will not fit; never silently omit authority or safety text. Old v1 packs must be regenerated because they did not bind the full machine-input closure.

## Normative requirements

### DE-REQ-071-01

Context packs MUST name exact source hashes, required safety context, budget and omitted optional material.

**Verification:** Mutate a selected file and require context verification failure.

### DE-REQ-071-02

A handoff MUST distinguish observed work/tests from proposals and MUST NOT imply GitHub writes or execution without evidence.

**Verification:** Validate unrun-test and uncommitted-patch examples.

### DE-REQ-071-03

Required context MUST NOT be silently truncated to meet a budget.

**Verification:** Build an intentionally undersized pack and expect a typed failure.

## Related specifications

- [DE-070](aide-integration.md)
- [DE-002](../foundation/authority.md)
