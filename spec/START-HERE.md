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

1. Read [authority](foundation/authority.md) and [implementation sequence](roadmap/implementation.md).
2. Install the tested Python dependencies with `python -m pip install -r spec/tools/requirements.txt` on a development coordinator.
3. Run `python spec/tools/specctl.py check` and `python -m unittest discover -s spec/tools/tests -v`.
4. Run `python spec/tools/specctl.py next`; `DE-W000` is the initial review unit.
5. Build a bounded pack: `python spec/tools/specctl.py context --work DE-W000 --output .aide-local/context/review`.
6. Read the [amendment review](roadmap/amendment-review.md), then review before granting code work. No command here authorizes storage writes.

The spec-only ZIP can create optional root entrypoints with `python spec/tools/specctl.py bootstrap --root .` (preview) then `--apply`. The repository overlay already includes those same entrypoints. Do not use bootstrap to overwrite an existing project.

No remote repository has been modified by creation of this archive.
