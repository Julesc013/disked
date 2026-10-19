# Windows integration reference-plan review

This is a proposed planning amendment requested by the owner on 18 October 2026.
It extends the Windows-reference plan introduced by 7a985be3. The review began at
c667318e258db237b56f103343360d1457dcb2c7 and the final candidate is based on
9556b090b974489847683b801e6558af0dfb046f.

## Changes and scope

- Correct historical-target routing: DE-W018 and DE-050/051/052 own target work;
  DE-W070 applies to selected JC-DOS/Carbon integration. DE-W080 owns advanced
  operation/provider admission.
- Refine DE-025 and DE-W035 for one selected read-only MMC or shell adapter:
  host/ABI/bitness, exact selection, retargeting, independent instances, delayed
  callbacks, bounded host behavior, shared-service parity and owned teardown.
- Refine DE-034 for required-service applicability, distinct SCM/provider/target
  state, cancellation completion and reconnect/recovery.
- Keep the existing provider, local broker, Setup and remote execution owners.
  Retain DE-W105 -> DE-W106 -> DE-W107; only the DE-W035 work record changes.
- Add eight reviewed primary Microsoft references. These are documentation
  observations, not executed Windows experiments.

The amendment adds no native implementation, service, network listener, installer,
reference campaign or platform admission. No product expected result is changed.
Current programme and native evidence remain owned by the concurrent DE-W105 work.

## Independent review

The disked_structure_review agent reviewed the actual changed files against their
original GitHub blobs and independently checked the eight Microsoft sources. It
found no blocking issue. Two clarifications were incorporated: apply cases only
to the selected integration mechanism, and preserve each target's qualified
imports/cancellation mechanism when named APIs illustrate a modern profile.

This is agent review of a planning amendment, not owner acceptance or security,
provider, installation, hardware or product qualification.

## Actual validation

All source snapshot files were verified against their Git blob hashes before
materialization. The final selected snapshot contains 1,427 files, including
current source/tests/spec/docs/tools/external inputs and the complete declared
input closure; it is not a full historical evidence checkout.

- validation.json: the amended plan at the initial c667318e base passed the
  complete 253-test specification/tooling suite on Linux (no skips), structural
  checks, context verification, source-map coverage for all 327 source files,
  and manifest generation/verification.
- final-checks-reservation-refusal.json: the first follow-up passed the affected
  15 bundle tests and structure checks but a context reservation was refused by
  the existing storage guard. The owned context and managed workspace were
  removed. The refusal remains retained; no resource allowance was increased.
- final-checks.json: after the two reviewed clarifications and the rebase onto
  9556b090, the 15 affected bundle tests, all 1,325 structural checks, complete
  DE-W035 context, generated freshness and manifest checks passed. The context
  was removed after verification.
- workspace-results.json records observed runner completion and cleanup.

The upstream rebase changes native FAT fixture routing and its input dependencies;
this amendment's checks do not qualify those native changes. The final check
scope is explicit rather than describing the earlier full suite as a fresh full
suite at the later base. No native or Windows-reference test ran in this review.

The original W105 -> W106 -> W107 sequence remains the next product work. The
9556b090 upstream checkpoint records the private Win32 pass; full x64 and the
remaining DE-W105 criteria remain open. Its evidence is preserved independently.

