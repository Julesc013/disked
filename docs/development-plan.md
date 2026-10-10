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

DE-W060 begins with an [offline package fixture binding](setup-fixtures.md):
exact local upstream schema/source identities, independent native payload
inventory, package/recipe agreement and owned-directory equality/retention
tests. It does not qualify a live Setup consumer or installation mode. The
existing local programme grant covers fixture work; formal owner acceptance,
actual installation and production storage privileges remain separate.

The next DE-W060 slice builds a private native C ABI source consumer from an
84-input exact CoreStatic closure under DiskEd-owned CMake. No upstream scripts
or installed SDK are used. Read-only fixture evidence distinguishes structural
ZIP inspection from content verification, preserves the FacMan-specific generic
package refusal, and leaves every live lifecycle/owner gate open. The shipped
DiskEd executable and its prior native qualification are unchanged.

The [clean source-consumer review](../.aide/evidence/2026-10-10-setup-source-consumer/REVIEW.md)
records the completed local slice and actual refusals. Continue finite
carrier/ownership fixture work under the programme grant while the generic
callable verifier, installed SDK and live lifecycle remain unqualified.

DE-W062 now develops the finite external H/D/offline ZIP fixture and read-only
servicing preview. It retains direct portable use, independently selected native
payload identities, one-owner constraints and active/unknown dependency refusal.
Embedded/native carriers, live interlocks and owner/platform/channel admission
remain at their original gates; the fixture is not an alternate installer.

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


DE-W023 supplies reproducible malformed-image recipes, bounded installed-tool
adapters and a deterministic sanitizer campaign over the private C90 readers.
It retains native findings, external tool/source-package identities, raw invalid
output and candidate-relative disagreements. Expected results precede tool
comparison; another parser never selects a GPT winner for DiskEd. Evidence belongs
to `.aide/evidence/2026-10-07-parser-campaign/`. Local review and clean campaign
reproduction govern continuation to W024. Coverage-guided campaigns, broader
sector/platform profiles and independent safety qualification remain explicit;
Further acquisition consistency belongs to W033; W024 admits only its bounded
read-only metadata observation and frontend profile.

DE-W024 adds shared `image.inspect` and `table.verify` raw-file commands in the
Windows image/fake prototype. CLI/stdio and real native GUI, isolated
TUI and shell fixtures compare geometry, independent findings, partial coverage
and source refusals. File reads use the existing bounded request channel; timeout
does not establish cancellation or free a still-executing slot. Capture remains
live-uncoordinated: equal rereads are not an atomic snapshot, whole-image check
or healthy-volume certificate. Only explicitly named ordinary local raw files
are in this initial profile; physical storage, image containers and writer gates
remain separate. Reproducible evidence and local review belong to
`.aide/evidence/2026-10-08-image-commands/`. The full 0.1.0 programme and owner
acceptance remain open. `.aide/programmes/worker-continuity.md` retains the service-
independent build/test and handoff workflow.

DE-W033 is active. Its private native acquisition pipeline defines exact typed
source/destination/map/host/executable/provider bindings and grants, bounded
chunking, explicit substitution, intention/checkpoint ordering and resume
verification. Its private Windows file adapter adds pinned source/parent/code
identities, exclusive effect handles, no-clobber output creation, growing images,
persistent LF-framed maps and explained-extent resume. Tests use independent byte
and hash expectations, actual sharing/creation races and observed owned-child
termination on generated files. The initial core and adapter checkpoint preceded public acquisition admission.
A private Windows worker then exercised real file
transfer with exact reviewed definitions and effect grants, persistent operation/
worker/attempt identities, verified-checkpoint progress, cancellation and reconnect.
It shares the four-worker memory/process budget with the fake worker. An unfinished
or corrupt admission is observed without relaunch or cleanup. Capture-record v2
preserves original provenance across same-code resume and records each attempt's
wall-clock interval and monotonic elapsed time. Shared frontend/command integration followed that checkpoint; source-bound evidence belongs to
`.aide/evidence/2026-10-09-acquisition-worker/`. The provisional
map encoding does not settle the production-journal decision. See
[DE-103](../spec/operations/acquire-image.md) for its exact profile and limits.

The next W033 component defines provisional prepare/execute command parameters,
a strictly typed full worker definition, explicit effect grants and standard
response/exit projections. A private probe exercises the common CLI/stdio/form
decoders over the actual generated-file worker and controlled callback ports.
The dev.19 checkpoint left the public copy command planned/unavailable and routed
explicit acquisition operation identities through the common inspect/cancel path.
It exposed bounded CLI/stdio watch batches and negotiated NDJSON events. Portable readers bind the independently obtained full definition,
worker/attempt identity, record digests and monotonic checkpoint coverage.
Visible GUI/TUI/shell copy review/submission and bounded rendering were required
before the dev.21 acquisition command admission described below. Other platforms and physical storage remain
separate qualification gates.

The dev.20 component adds schema-derived prepare/execute forms with phase changes
that clear values and grants, bounded structured definitions, and fresh review/
submit controls. A marked private executable exercises actual native GUI/TUI
metadata preparation and ordinary-file copying through the shared Windows
adapter. These journeys supplement the model checks; they do not admit the public
copy command at that checkpoint. Dev.21 completes structured shell input and
large interactive watch rendering, then integrates ordinary-file admission with
actual frontend and lifecycle tests.

The dev.21 W033 development composition adds the ordinary-file acquisition
provider explicitly. Public CLI/stdio/GUI/TUI/shell use one canonical prepare/
execute adapter and one disked.exe worker role with exact definition/effect grants.
Native tests include no-output preparation/review, real copies, checkpoint cancel/
resume and unchanged-store observation rather than replay. All 64 watch events
fit a separate bounded profile; expanded test history is labelled synthetic.
Owner acceptance, physical/failing-media qualification, other platforms and
production writer/release decisions remain independent gates.

DE-W034 now includes a private same-file ordinary-image verification worker
with exact case/image/map/code/store bindings, explicit private-metadata grants,
checkpoint progress, independent cancellation observations and retained typed
collections. The authored verification-worker profile fixes expectations before
evaluation. Clean native reproduction and agent review govern local continuation.
Public image.verify commands, negotiated events, bounded caller requests and
actual frontend journeys are the next gate; all platform/storage and owner
acceptance remain open.

The bounded DE-W062 fixture slice has a [clean native reproduction and local
review](../.aide/evidence/2026-10-10-carrier-fixtures/REVIEW.md) at `d4102ab`.
It proves the selected external H/D/ZIP construction and private servicing
constraint model, leaving the full work unit, live effects, channels and owner
acceptance open. The selected retained historical verification bindings in
DE-W034 have separate later qualification at dev.36; Setup compatibility remains
an unresolved integration requirement.

Current inspection confirms the selected historical acquisition/verification
report export is already qualified at dev.36. DE-W030 is the next missing native
inventory prerequisite: its [private volume namespace adapter](windows-inventory.md)
now has Windows x64/x86 API-response fixtures. Exact source-bound reproduction
and import audits precede local review; live namespace, physical identities,
contained public observation and platform/owner gates remain open.

The DE-W030 contained injected namespace observer has exact-source native
qualification at `d3798a7` ([review](../.aide/evidence/2026-10-10-nt-contained/REVIEW.md)).
Each x64/x86 campaign verifies 49 adapter processes plus 24 controller invocations
and 18 actual child launches; late observation, checkpoint cancellation, reader
retirement, client disconnect and strict reply binding remain separate. The
graph slice below supplies subsequent capture/epoch-safe evidence from generated
namespace observations. Native physical identity/topology, live/public/provider
admission and the full platform/owner/release gates remain open.

The common capture publication/retirement boundary now has exact-source local
qualification at `2d753bae` ([review](../.aide/evidence/2026-10-10-capture-publication/REVIEW.md)).
Complete/partial publications retain outstanding workers until bound actual
exit; stale old-capture replies cannot authorize replacement. Proposed dev.37
passes all 77 selected native regression groups. Both x86/x64 owned-reader
lifecycle and existing worker campaigns pass, with 16 independent reducer tests.
At that revision the lifecycle adapter used empty graph fragments; namespace
node projection was still pending, alongside native physical identity/topology
and live/product/provider/platform admission. Owner and full-unit/all-platform/storage claims remain open.

The private namespace observation graph is now locally qualified at `3463fb23`
([review](../.aide/evidence/2026-10-10-namespace-graph/REVIEW.md)). Proposed dev.38
passes 77 product groups and 23 reducer tests. Both x64/x86 graph campaigns pass
30 controller invocations, 26 actual injected reader launches and 1,103 assertions
per architecture; existing adapter/worker/lifecycle regressions also pass.
Volume/mount observations retain exact names, distinct context-bound IDs and
unknown physical identity. Partial frames retain only the last complete frame
as stale background; publication and owned reader exit remain separate.
The adapter is private, and the existing frontend rejects its unadmitted profile.
Native identity/topology, observation frontend, live/product/provider/platform
and owner/full-unit qualification remain next work.

The private injected storage metadata/extent layer is locally qualified at
`e469d70f` ([review](../.aide/evidence/2026-10-10-storage-queries/REVIEW.md)).
Each x64/x86 campaign passes 70 native fixture executions and 1,987 independent
assertions. Descriptor bytes, capacity disagreements, cloned serials, duplicate
numbers and candidate extent topology remain explicit observations. Pending
queries stop the batch, including invalid returned counts. Immutable frames
project into the common graph without physical identity or mutation authority.
The selected dev.38 product's 401 input bytes remain unchanged; this private
slice does not claim a new product build or a repeated full product suite.
Actual owned-reader integration, startup/retry reconciliation, observation
frontend, native identity/raw layout, live/provider/platform and owner/full-unit
qualification remain next work. Both full and mixed native tables are refused.

The shared owned namespace/metadata host is now locally qualified at `16259b7a`
([review](../.aide/evidence/2026-10-10-storage-worker/REVIEW.md)). Each x64/x86
metadata campaign passes 43 controllers, 35 actual reader launches and 671
assertions; five existing campaigns also pass (614 processes/8,480 assertions
combined). Preparation creates no child, post-spawn errors retain ownership,
and exact exit is observed before replacement. Parent receipt reconstruction
does not call the provider; owned process/code/request context binds graph IDs.
The dev.38 product's 401 inputs remain unchanged, with no new product/full-suite
claim. Observation frontend semantics, native identity/raw layout and actual
live/product/provider/platform/owner/full-unit admission remain next work.

The compiled private cached-observation frontend slice is locally qualified at
`8f55d867` ([review](../.aide/evidence/2026-10-10-observation-frontend/REVIEW.md)).
Dev.39 passes all 77 selected product regression groups. Each x64/x86 private
frontend campaign passes 15 controllers/26 actual
reader launches/1300 assertions; all private campaigns combine
696 processes/11080 assertions. Exact evidence focus, owned
context, missing/stale state, atomic publication, conservative target boundaries
and maximum inert display under the actual memory job are checked in existing
models. The ordinary product stays Fake. Actual new-profile visible interfaces,
native identity/raw layout, live/product/provider/protocol/platform and owner/
full-unit/all-platform/storage admission remain open. The source map now explains
all 170 files and planned ownership; private path changes preserve public IDs.

The private identifier/alignment/OS-layout query profile is locally qualified at
`b853621b` ([review](../.aide/evidence/2026-10-10-identity-queries/REVIEW.md)).
Each x64/x86 binary passes 57 generated cases and 197 assertions; affected
metadata/frame/owned-worker/cached-frontend regressions also pass (492
processes/8310 assertions combined). Exact identifier bytes, SDK layout,
GPT name units and conflicting reports stay evidence without physical identity
or effects. The dev.39 product's 403 inputs remain unchanged; no new product or
full-suite run is claimed. Integrate the new receipts into owned frames/graph
context next; raw-media comparison, composite identity, live/product/provider/
protocol/platform and owner/full-unit/all-platform/storage admission remain open.

The private /2 owned identifier/alignment/OS-layout frame and graph profile is
locally qualified at `6b883c01`
([review](../.aide/evidence/2026-10-10-identity-frame/REVIEW.md)). Each x64/x86
campaign passes 54 controllers/41 actual readers/6980 assertions; every existing
private Windows campaign also passes (1000 processes/25434 assertions
combined). Explicit profile and typed receipt reconstruction preserve /1
readability, exact context and unknown physical identity. Shared 128-detail
limits and separate nodes bound current/last-complete graphs without expanding
public output or granting effects. Product inputs are unchanged. New /2 cached
interfaces, independent raw comparison, composite identity and live/product/
provider/protocol/platform/owner/full-unit/all-platform/storage gates remain open.


The source/input ownership follow-up at `67f3cfb0`
([review](../.aide/evidence/2026-10-10-source-layout/REVIEW.md)) qualifies both
existing cached-frontend campaigns (82 processes/2600 assertions).
The dev.40 product and 77 selected native groups passed at `3f648127`;
all 404 product inputs are unchanged by the private probe fix, so those results
were retained without a second product build/full-suite run. Shell and TUI consume one private
`runtime/presentation/text_input.h` contract; shell no longer includes the TUI
model. [The file map](source-map.md) explained all 172 source files at that revision,
CLI/command/terminal boundaries and future ownership families. This is a bounded
private ownership change; /2 interfaces/raw comparison, physical identity,
live/provider/public/platform/owner/full-unit and broader 0.1.0 gates remain.

The private generated-image raw-layout slice at `4400cb71`
([review](../.aide/evidence/2026-10-10-raw-layout/REVIEW.md)) passes 218
raw-comparison processes/2684 assertions across x64/x86; existing query
regressions bring this run to 472 processes/7052 assertions. Tooling runs
215 tests with two skipped; 1057 structural checks and exact 461-input
closure pass. All 404 product inputs remain unchanged, retaining dev.40
evidence at its original source without another product build/full-suite
run. The file map covers all 176 current files. Comparison is a declared
fixture pairing, without owned-reader/physical association or provider
admission. /2 cached interfaces, owned raw-reader provenance, composite
identity and live/product/public/platform/owner/full-unit gates remain.
