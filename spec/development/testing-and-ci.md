---
type: DiskEd Specification
title: Testing, validation and CI strategy
description: Differentiate schema checks, product tests, hardware evidence and recovery
  qualification.
resource: disked://spec/de-074
tags:
- disked
- development
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-074
  profile: disked-spec/1
  version: 0.1.23-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-004
  - DE-044
  requirements:
  - DE-REQ-074-01
  - DE-REQ-074-02
  - DE-REQ-074-03
updated:
  by: codex
  at: '2026-10-19T16:56:37.826562+00:00'
  scope: Separate fixture-generation allowances from product deadlines; no new qualification claim
sources:
- id: windows-reference-review-2026-10-18
  resource: ../references/sources.json#windows-reference-review-2026-10-18
- id: rea-reference-method
  resource: ../references/sources.json#rea-reference-method
- id: windows-reference-ui-automation
  resource: ../references/sources.json#windows-reference-ui-automation
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
- id: cli-refinement-2026-10-04
  resource: ../references/sources.json#cli-refinement-2026-10-04
- id: util-linux-sfdisk-campaign
  resource: ../references/sources.json#util-linux-sfdisk-campaign
- id: sgdisk-campaign
  resource: ../references/sources.json#sgdisk-campaign
- id: gcc-133-campaign
  resource: ../references/sources.json#gcc-133-campaign
---

# Testing, validation and CI strategy

## Bootstrap validation

The included tools validate OKF/profile structure, schemas/examples, links, stable IDs, requirement/test mappings, work dependencies, catalog references, invocation fixture policy and generated freshness. Their own unit tests cover malformed inputs and tooling safety. Passing these checks proves only the listed properties of this archive. No DiskEd executable, provider, physical disk or OS GUI is tested by the bootstrap.

## Native campaign time accounting

Keep product response, progress, cancellation, hang and retirement deadlines separate
from the test harness's time to generate completed fixtures and collect evidence.
A campaign controller must honour each registered CTest timeout and leave bounded
termination/reporting time after it; an equal or shorter outer timer can discard
the JUnit record of a genuine timeout.

Calibrate completion-fixture allowances from retained measurements and declared
workload sizes before evaluation. Preserve original failures, exact assertions and
fixture counts; identify every changed process/probe observation envelope. A
longer completion-fixture allowance does not authorize changing fault-test or
product deadlines, storage budgets, outcome expectations or admission rules.
Diagnostic completion under a different aggregate window does not qualify the
earlier window. The current proposed guest allowances are source-bound in the
[fixture I/O review](../catalog/native-fixture-timeouts.json)
and require actual native requalification.

## Product test pyramid

Unit and property tests cover checked arithmetic and graph invariants. Golden vectors and fuzzing cover MBR/EBR/GPT and hostile provider inputs. Differential tools expose disagreements but do not prove correctness by majority vote. State-model tests exercise authorization, attempts, journal transitions and cancellation. Fake providers enable frontend parity and negative capability tests. Images permit end-to-end mutation with fault injection. VMs cover loader, mount and boot behavior. Hardware tests cover controllers, sector sizes, removable media, locks and persistence.

Physical power loss is not equivalent to killing a VM process. A hardware-qualified claim requires real device evidence, exact firmware/controller/cache configuration and recovery exercise. No public CI worker or coding agent gets raw host disks. Use sacrificial lab assets and independent approval. Large corpora stay content-addressed outside ordinary source history.

## CI workflow

The baseline overlay includes a workflow template, not a silently activated supply-chain trust policy. Activate only after pinning actions/runners/dependencies to reviewed identities. Initial jobs: spec schema/links, generated drift, tooling tests and docs checks, all read-only. Product jobs add Windows profile compile/import audits and fake/image tests. A green PR does not authorize high-risk hardware effects or release signing.

## Efficient validation

Map module inputs to tests and record dependency hashes for reuse. Rerun impacted tests during iteration, then qualify the exact composed release. Translation or prose edits should not trigger multi-hour hardware campaigns; range arithmetic, journal, provider version or toolchain changes may invalidate broad evidence. A test command, working directory, exit code, logs, environment and artifact hashes are retained. Never mark skipped/unsupported tests as passes.

## Amendment acceptance programme

M1 adds essential startup with broken optional settings, missing providers and offline networking; healthy/denied/malformed/stalled/crashed fake targets; bounded worker replacement, queues/memory and truthful cancellation; native keyboard/accessibility/locale/scale; and CLI/TUI/GUI semantic transcripts. DE-W018 performs small constrained portability probes in parallel with independently authorized M1 work, without blocking the modern slice.

Later work adds snapshot/epoch/writer consistency, dependency/failure-domain aliases, interrupted formatting, Setup containment/payload identity, tamper refusal, external-tool ownership, selection-preserving upgrades, servicing interlocks, native adapter teardown, publication completeness and SDK compatibility. `catalog/amendments.json` maps supplied scenarios to owners/work; all product scenarios remain definition-only until executed.

Specification regressions validate new schema cross-field constraints and negative fixtures. Requirement coverage is checked against authored IDs rather than a frozen corpus count. On Windows, tests must work when TEMP and checkout reside on different drives, and manifests must sort relative POSIX paths consistently across hosts. Skipped platform-dependent tests remain explicitly skipped, not passed.

## Shared CLI grammar corpus

The command-syntax expectation corpus is not a native test result. DE-W012 runs it against the real parser and generates permutations of complete option/value groups, including help and literal tails. Compare normalized command/arguments, target scope, requested presentation and required plan/authority. Trace no effects before complete validation. At each selected target's parser admission, reuse the same cases with its real command-tail/argv encoding, quoting and resource bounds. DE-W018 can report parser cases not_run while completing unrelated early primitive probes. DE-W019 adds editable error recovery and ergonomic observations; shorter spelling alone is not measured usability.

## DE-W023 initial parser campaign profile

`tests/corpus/partition_images.py` owns deterministic ordinary-file recipes;
`tests/differential/CONTRACT.md` records the bounded campaign contract. Initial
external observations use explicitly named synthetic 512-byte-sector files under
an unprivileged account. Tool invocations have finite time, memory and output
limits, retain exact executable/library identities and source-package versions,
and verify unchanged input bytes. Installed package provenance does not imply
that its full upstream source bytes were independently retrieved or rebuilt.

Native expectations come from DE-032 and the recipes. External table projections
and diagnostics are retained independently, including malformed output, refusal,
timeouts and disagreement. A tool selecting one valid GPT copy does not resolve
DiskEd's competing candidates. Success exit does not certify complete validation.

The private C90 readers also run with fatal address/undefined-behavior sanitizers
and measured branch coverage in a bounded deterministic mutation campaign.
Raw/truncated inputs and test-only checksum reconstruction exercise different
paths without weakening the production readers. Separate positive controls
verify both detectors and failure-input replay. Record actual iterations,
uncovered branches, host/toolchain and source inputs. This initial campaign is not
coverage-guided fuzzing or exhaustive qualification; unavailable runtime support
remains a recorded follow-up, not a substituted pass. W024 owns coherent image
capture and frontend integration. Historical platforms, independent safety
qualification and owner acceptance retain their separate gates.

## Windows reference experiments

Reference-driven development extends the differential campaign; it supplies
evidence for reviewed contracts, not implementation authority or acceptance.
DE-W106 first repairs evidence-set validation and the historical coordinator's
obsolete scratch routing. DE-W107 then runs one bounded Windows inventory
experiment. The experiment contract (`tests/differential/CONTRACT.md` in the implementation repository)
defines participant identities, expected sets, effects and result dimensions;
the contributor plan (`docs/windows-reference.md` in the implementation repository) explains component roles.

Declare each question, exact expected case/reference/observation-kind set,
geometry, normalization rules and allowed effects before evaluation. Validate
uniqueness, completeness and matching recipe/input/tool identities before
projecting results. A missing or invalid observation MUST NOT produce a complete
successful campaign. Required unavailable observations remain unsatisfied; a
well-identified reference refusal is an observation, not missing evidence.
Keep evidence completeness separate from behavioral agreement and from capability
qualification. Retain diagnostics and competing candidates without majority vote.

Use separate disposable participant copies and record before/after bytes and
attachment/mount side effects. Bind raw results to OS/component/tool versions,
privilege, policies, device geometry, action and comparison-contract revision.
Label documented facts, observations, inferences and unresolved discrepancies.
Cache/reuse only when those dependencies remain applicable. Implementation tests
use reviewed independent expectations rather than deriving expected behavior
from the implementation being evaluated.

REA is an optional research aid. Keep public documentation/behavior, licensed
source and proprietary binary-analysis provenance distinct. Any required
observer/builder separation needs enforced access boundaries; shared credentials
or agent profiles are insufficient. No tool install, code reuse, exported asset
or research result automatically gains product admission or redistribution rights.
Keep all reference work within the existing managed storage, guest and cleanup
policy; coordinate the shared interactive desktop. Do not rerun the obsolete
`.aide-local` campaign recipe or replace current native qualification with a
reference-tool installation. New target declarations do not imply target support.

## Normative requirements

### DE-REQ-074-01

Spec/tooling validation MUST be labeled separately from product, OS, hardware and recovery qualification.

**Verification:** Inspect reports for explicit scope and non-capabilities.

### DE-REQ-074-02

CI MUST operate on disposable fixtures without raw host-device access or release keys.

**Verification:** Review workflow permissions and denied-path tests.

### DE-REQ-074-03

Test reuse MUST depend on actual changed inputs and a final composed-artifact qualification.

**Verification:** Modify a shared primitive/provider lock and inspect impact selection.

## Related specifications

- [DE-004](../foundation/requirements-and-traceability.md)
- [DE-044](../safety/verification-and-performance.md)
