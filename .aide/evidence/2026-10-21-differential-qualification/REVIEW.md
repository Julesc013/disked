# DE-W106 development review

The evidence/coordinator correction passes its available Windows conformance
controls at exact source `cfbde97ba65103bd0d11535c43ca257d10e73b23`.
Continue to DE-W107 under the recorded cross-unit development grant. Owner
acceptance, an independent external-reference campaign and release qualification
are separate and remain ungranted/unverified.

The comparator now requires a frozen, nonempty, exact case/participant/kind set,
consistent fixture geometry and identities, retained raw-byte hashes and observed
input preservation. Completeness, execution and behavioral agreement are separate.
The coordinator reads required receipts and consumes the complete gate; a returned
`passed=true` cannot replace evidence. Preparation, copies, receipts, compiler
output and raw streams use managed scratch. The obsolete WSL entrypoint remains
suspended; its historical evidence is unchanged.

## Actual checks

- [Host validation](validation.json.xz): 253 specification tests (two skips),
  241 tooling tests (one skip), 84 differential tests (five skips); 578 run,
  eight skipped, zero failures. All 1,328 structural checks, 329-file source-map
  inventory and 422-file manifest verification pass. Tested inputs were unchanged
  throughout that pass. [Preflight](preflight.json) records the subsequent sole
  launcher-input change: a sufficient declared context artifact allowance, still
  within the existing 32 MiB aggregate metadata limit. Actual generation and
  verification exercised that allowance before the guest run.
- [Guest receipt](receipt.json.xz), 2026-10-21 02:38:21–02:39:07 UTC: existing
  Windows 10 build 19045 guest, `Agents` coordinator, fresh restricted ordinary
  Medium/nonadministrator/non-elevated worker, MSVC 14.44.35207 and SDK
  10.0.19041.0, static CRT x64. The original capacity, outside-write, source,
  inheritance and abrupt-interruption controls pass. Actual capacity exhaustion
  returned error 112 inside the 32 MiB filesystem, followed by removal of its data.
- Sixty execution-port calls pass: eight byte-I/O controls, four native build
  steps, two protected-memory guards, 35 authored recipes/64 fixed checks,
  two protocol-fixture build steps, six positive packet calls, two native calls
  before a false callback success, and one native call before a declared interrupt.
  Each owned job is terminal and temporary stdio is removed. Job limits remain
  256 MiB commit and eight processes, within the existing aggregate limits.
- The positive packet contains two native observations, two JSON projections
  and two diagnostic-only observations. Its evidence is complete and execution
  succeeds, while comparison reports **disagreement**. The fixture's deliberate
  GPT start 36 matches neither native candidate (34/35); both remain retained.
  Missing/duplicate records, changed geometry and contradictory raw presentation
  cannot pass. False callback success and interruption preserve failed/unfinished
  receipts; the outer runner establishes quiescence separately.
- [Replay](replay.json) verifies all 224 retained entries and recomputes comparison
  from raw bytes, native expectations, source identities and the frozen manifest.
  The single [archive](retained.tar.xz) is 57,744 compressed bytes for 16,596,531
  original bytes. It was hash-verified before guest export and on replay; no
  extracted fixture/archive copy remains.
- [Cleanup](cleanup.json.xz) confirms owned actor/profile, source, media and
  qualification-root removal. Fresh observation found the root and `R:` absent.
  Host managed work was removed (1,362,177-byte peak for launch; 2,319,584-byte
  peak for replay). `.aide-local` was emptied after its readers returned. The
  shared VM backing file's **logical length** remained 34,580,987,904 bytes;
  allocated backing growth was not measured. No compaction or VM reset occurred.

## Limits and review decision

`reference_fixture.cpp` is an explicitly labelled repository-owned protocol
fixture, **not util-linux, an independent parser or Windows reference evidence**.
It recognizes only the two exact predeclared recipe hashes and creates no files.
The four actual fixture calls qualify this conformance scenario only. No installed
sfdisk/sgdisk or qualified Linux worker was available; those profiles and a fresh
sanitizer campaign remain unverified. No native-only observation is relabelled
as an independent reference result. Coordinator `qualification=not_assessed` and
`cleanup=outer_runner_pending` remain intact; actual cleanup is separate evidence.

Review compared the fixed command construction, bounded reads/writes, artifact
and executable identity checks, callback/exception paths, original worker controls,
actual receipts and replay. No product implementation or production command
semantics changed; DE-W105 remains supported by its exact `5c2f5337` evidence,
not by an invented full-product rerun here. Later status/documentation changes
are metadata and receive their own context/manifest/applicability checks.

DE-W106's available development deliverable is ready for review and integration.
DE-W107 must declare and collect its own four-case Windows API **and UI** evidence;
these conformance controls do not substitute for either. The original all-platform
and storage-operation 0.1.0 scope remains unchanged and incomplete.
