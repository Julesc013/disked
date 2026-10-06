# Development readiness and delivery plan

The amended baseline is **proposed and awaiting review**. The specification tools and the bounded DE-W010 native bootstrap work locally; there is no admitted storage provider or qualified product target. See the [native build guide](native-bootstrap.md) for the exact implemented surface. The [amendment review](../spec/roadmap/amendment-review.md) records conflicts and deferred scope. [Root TODO](../TODO.MD) is the short checklist; [work definitions](../spec/work/units.json) own dependencies, deliverables and acceptance criteria.

## Start development in bounded slices

| Work | Concrete result | Boundary |
|---|---|---|
| DE-W000 | Review the amended baseline, source layout and scoped decisions | Final content remains unaccepted until recorded review; tool success is separate. |
| DE-W010 | One native executable with a fake provider, build identity, static command registry and actual build/launch evidence | No physical storage access; create only source directories needed by code. |
| DE-W011 through DE-W016 | Common CLI/machine/TUI/Win32 semantics, graph, plans and local fake execution | Real frontend and process evidence, with unknown and denied results preserved. |
| DE-W017 | Fake hangs, bounded queues, cancellation races, stale results, frontend loss and worker exhaustion | Failure drills before expanding storage authority. |
| DE-W018 | Tiny compile/import/launch probes for selected legacy profiles | Early architectural feedback; no full product or broad compatibility certification. |
| DE-W020 through DE-W034 | Read-only image/format readers, Windows observations and coherent acquisition contracts | Follow each unit's exact prerequisites and scoped storage grant. |
| DE-W035 | Thin read-only native host adapter prototype | Fixture hosts first; real registration requires separately authorized installation work. |
| DE-W040 through DE-W043 | Recovery, offline preparation and independently verified disposable-image mutations/formatting | Journal/recovery decisions and image-only authority precede execution. |
| DE-W060/062/063 | Managed delivery, finite carrier/owner contract and independently staged artifact checks | Portable use remains viable; no signing, publishing or claimed upstream integration here. |
| DE-W080/090 | Broader target/operation qualification and a scoped release | License, provenance, exact target evidence and release authorization remain required. |

These are work groups, not new IDs or a second dependency graph. Run `python spec/tools/specctl.py next` for current dependency readiness. A dependency-ready result is not an execution grant. The explicit 0.1.0 programme grant selects every platform/storage operation specified at base 40ac8ec and permits local continuation across units after tests and agent review. Owner acceptance and release/storage privileges remain separate; see `.aide/programmes/disked-0.1.0.json`. The retained baseline review records that grant separately from the still-pending acceptance ledger; `next` therefore continues to show the unaccepted W000 dependency.

The [current validation report](../spec/reports/validation.json) records local specification tests and passive AIDE schema checks. The repository's DE-W000 handoff under `.aide/handoffs/` retains the exact base, changed files, actual results and outstanding review boundary. DE-W010 native build/launch results are retained separately under `.aide/evidence/2026-10-06-native-bootstrap/`; they do not qualify the full product or replace historical tooling results.

## Decisions that remain open

The [decision register](../spec/catalog/decisions.json) retains the original-code license and staged storage/recovery gates. Added decisions cover the `source/` prefix, finite H/D/S delivery ownership, servicing owner, constrained terminal behavior, measured resource budgets and coherent acquisition. Review decisions at the work boundary that needs them. Resolve the source-layout proposal with DE-W000; do not let later hardware, channel or public-SDK choices block a fake-only binary unnecessarily.

Conflicting attachments remain attributed proposals. The machine-readable [amendment map](../spec/catalog/amendments.json) traces 23 architecture amendments, audit findings and 33 acceptance-test designs to canonical owners and work. Those 33 designs have **not been executed**. The supplied audit's reported ZIP checks cannot certify this repository or an archive that was not supplied.

## AIDE maintenance

AIDE `dev` was fetched at `5be37bd6510977e6cb2e960859c45b33b048dade`; the exact tree, inspected file hashes and limits live in [aide-lock.json](../spec/references/aide-lock.json). The checkout is disposable at `.aide-local/upstream/aide`. No upstream runtime or worker was launched. Passive validation of DiskEd exports against the pinned queue schema is separate from the live import and isolation qualification in DE-W061.

Review upstream approximately weekly; the next review is **11 October 2026, Australia/Sydney**. Compare the current pin with the next candidate, inspect changed protocol/authority requirements, revalidate projections and record actual evidence before changing the lock. No automatic schedule, floating dependency, upstream execution or stable-release claim is installed by this policy. After a stable release appears, review and qualify an exact version before adopting it.

## Corrective review at 08a8246

The [corrective disposition](../spec/roadmap/corrective-review.md) retains the architecture while fixing mixed-path impact, task-input freshness, acceptance-history projection, event/response constraints and CLI prompt policy. Context manifest v2 embeds required prose/instructions and supplies required catalogs/schemas/fixtures under `artifacts/`; it checks the complete declared closure. Existing v1 packs must be regenerated. `specctl acceptance-status` distinguishes historical validity from current applicability without deleting old receipts.

DE-W019 adds the explicit command shell; DE-W017 includes shell parity and guarded late-event/cancellation scenarios. Typed resources and plan/recovery receipts remain scoped acquisition/writer gates. The icon report supplies no actual assets or rights evidence. GitHub PR/check enforcement remains a concrete follow-up; no protected-branch setting is claimed from this local pass. See the [planned command experience](command-experience.md).

## CLI grammar refinement

DE-W012 now includes flexible placement of complete option/value groups, contextual help, natural registered command forms and shared native parser conformance cases. DE-W019 adds editable syntax-error recovery and measured typing/completion usability. Catalog/schema checks and expected-result definitions are local preparation; the shared corpus now runs against the Windows native parser; no other host is qualified by that result. The [command experience](command-experience.md) and [canonical grammar](../spec/interaction/commands.md) explain the boundaries. Existing architecture and storage-admission stages remain intact.

The DE-W013 local slice adds an immutable fake graph and shared frontend service.
CLI/stdio read commands preserve denied/stale/unknown observations; revision
checks and selection identity live in the service. Real storage remains later work; the bounded fake operation subset is developed in DE-W016. Evidence is retained under
`.aide/evidence/2026-10-06-native-graph/`; owner acceptance remains separate.

DE-W014 adds the native console TUI over that service, with staged typed forms,
linear/screen presentation and isolated real-console input/restoration evidence
under `.aide/evidence/2026-10-06-native-tui/`. DE-W015 adds the Win32 frontend; accessibility and untested-backend qualification remain separate.

DE-W015 now implements a native Win32 navigator, structured inspector and typed
review/submit forms over the same fake service. Native model and actual-window
tests retain parity, keyboard behavior and host observations separately from
owner acceptance. Evidence belongs to `.aide/evidence/2026-10-06-native-gui/`;
DE-W016 is the next process/execution boundary after the clean GUI reproduction.


DE-W016 develops a same-file unprivileged fake worker with a private ordinary-file
evidence store. The synthetic counter, exact operation/attempt/worker identities,
checkpoint cancellation, no automatic replay and reconnect after client loss are
bounded by DE-015. Verification failure and worker loss stay distinct. Clean reproduction and local agent review are retained under
`.aide/evidence/2026-10-06-native-worker/`. DE-W019 is next because the combined
DE-W017 campaign depends on its shell. Owner acceptance, production journal,
elevation and real storage gates remain open.


DE-W019's local Windows slice now supplies the bounded explicit command shell,
shared dispatch, inert editing/review, cached completion, optional session history
and console restoration. Clean reproduction and agent review are retained under
`.aide/evidence/2026-10-07-native-shell/`; local work continues into DE-W017.
Human usability and additional keyboard/terminal
qualification remain open; no production planner or storage admission is implied.


DE-W017 has reached its local fake-provider review boundary. Its containment
slices separate interactive event loops from
fake-operation file requests, preserve late outcomes by view identity, bound
cooperating workers with Windows jobs, and add finite CLI/stdio callback and
output waits. Unknown outcomes never authorize automatic retries; output failure
does not cancel admitted workers. Store-boundary injections now preserve unknown
claim/cancellation receipts, residual bytes and no-replay behavior after full,
partial and failed-flush writes. Valid frontend commands now enter a common
256 MiB per-process memory job before dispatch; stricter inherited host limits
remain effective. DE-045 defines the admission failures and measured fake
CLI/stdio/GUI/TUI/shell workloads. The common ancestor preserves stricter worker
quotas and independent worker lifetime. The private observation coordinator now
retains healthy/stale fragments across native denial, malformed input, delayed
success and producer exception. Capture/worker epochs prevent superseded results
from publishing, an eight-notice ring makes gaps explicit, and allocation-failure
checks preserve snapshots and pending updates. A separate native fixture
composition exercises the shared service through stdio, GUI, TUI and shell; its
producer budgets and synthetic denial are explicitly scoped. Evidence belongs to
`.aide/evidence/2026-10-07-observation-capture/`. DE-W012/017 now adds a bounded
fake-operation watcher, typed record/snapshot events, explicit NDJSON negotiation,
digest-bound reconnect and frontend parity. Its source-bound tests and clean
reproduction belong to `.aide/evidence/2026-10-07-operation-watch/`. The retained local review
and clean reproduction govern continuation to DE-W018;
owner acceptance, real filesystem/power-loss and other-host qualification remain
separate. The full 0.1.0 programme is still active.


DE-W020 now implements one internal C90 module for exact values, checked arithmetic,
bounded views, endian fields and named half-open extents. It reuses the DE-W018
implementation instead of creating a second arithmetic copy. Local independent
integer/byte vectors and C/C++ linkage/page-boundary checks exercise the core;
source-bound results and clean reproduction belong to
`.aide/evidence/2026-10-07-portable-core/`. The module adds no storage command to
the fake product. Local review governs progression to MBR/EBR and GPT readers;
DE-W018 historical compilers/launches remain open independently.


DE-W021 implements an internal read-only MBR/EBR library over immutable supplied
blocks. The DE-032 common two-entry EBR profile bounds traversal and preserves
opaque bytes; independent synthetic layouts and malformed cases drive native
verification. Evidence belongs to `.aide/evidence/2026-10-07-mbr-ebr/` once run.
This is local implementation in review, not an admitted image provider or a
completed `table.verify` command. GPT, source-consistency integration, historical
layout profiles, owner acceptance and all writer gates remain separate.


DE-W022 adds independent private GPT header/array readers with checked resource
limits, exact CRC spans, lossless GUID/UTF-16 observations and byte comparison of
primary/backup candidates. Synthetic encoding/layout cases, a real CRC collision
and protected-memory probes exercise the implementation. Source-bound evidence
belongs to `.aide/evidence/2026-10-07-gpt/`. Local review and clean reproduction
govern continuation; provider/source consistency, external differential fuzzing,
historical profiles, owner acceptance and writer gates remain separate.
