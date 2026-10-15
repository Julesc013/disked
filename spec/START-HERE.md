---
type: DiskEd Howto
title: Start here
description: Read the bundle in task-sized pieces and run its local checks.
status: draft
resource: disked://spec/de-000
tags:
- disked
- onboarding
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
disked:
  id: DE-000
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: informative
  review: pending
  risk: R1
  depends_on:
  - DE-002
  - DE-080
  requirements: []
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: references/sources.json#review-inputs-2026-10-04
---

# Start here

The authoritative entry is [index.md](index.md). This bootstrap file is a routing aid.

In the implementation repository, start with root `AGENTS.md` and
`.aide/programmes/disked-0.1.0.json`. Resolve its `current_work`, retained incomplete
work and `next_action` against `work/units.json`. The programme records actual
development state; it does not grant authority or baseline/implementation
acceptance. The archive-first sequence below applies when no programme exists.

1. Read [authority](foundation/authority.md) and [implementation sequence](roadmap/implementation.md).
2. Install the tested Python dependencies with `python -m pip install -r spec/tools/requirements.txt` on a development coordinator.
3. Run `python spec/tools/specctl.py check` and `python -m unittest discover -s spec/tools/tests -v`.
4. Run `python spec/tools/specctl.py next`; `DE-W000` is the initial review unit.
5. Build a bounded pack: `python spec/tools/specctl.py context --work DE-W000 --output .aide-local/context/review --byte-budget 700000`.
6. Read the [amendment review](roadmap/amendment-review.md), then review before granting code work. No command here authorizes storage writes.

The example budget fits the current baseline-review closure. Select the actual
work ID and an explicit budget that retains its complete required context; do not
truncate prerequisites to fit a stale example.

The spec-only ZIP can create optional root entrypoints with `python spec/tools/specctl.py bootstrap --root .` (preview) then `--apply`. The repository overlay already includes those same entrypoints. Do not use bootstrap to overwrite an existing project.

No remote repository has been modified by creation of this archive.

The bounded first native executable is described by [DE-079](development/native-bootstrap.md). Its task-specific grant and evidence are distinct from baseline acceptance; the spec-only archive does not contain a built executable.
