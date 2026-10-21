# Development readiness and delivery plan

The amended baseline is **proposed and awaiting owner acceptance**. The native Windows development composition and bounded image/format prototypes build and run on the recorded host. The programme links each implemented slice to its exact tests and evidence; this does not establish full product, provider, historical-platform or release qualification. See the [native build guide](native-bootstrap.md) for the exact implemented surface. The [amendment review](../spec/roadmap/amendment-review.md) records conflicts and deferred scope. [Root TODO](../TODO.MD) is the short checklist; [work definitions](../spec/work/units.json) own dependencies, deliverables and acceptance criteria.

## Windows reference and compatibility plan

DE-W105 passes the full180-group x64 gate,69 standalone headers,14 executable/import
observations,the same-source18-group private Win32 slice and strict C90 at
`5c2f5337`. All six actual product GUI images and both closed archives pass review.
The earlier179/180 watch failure and stopped focused build remain preserved;
the deterministic125ms sink regression and all reconnect tests now pass.
The [qualification review](../.aide/evidence/2026-10-21-product-capture/REVIEW.md)
records final tooling and dev/main integration separately from owner acceptance.

Continue DE-W106's bounded evidence/coordinator qualification,then DE-W107.
Keep existing storage limits and protected records. No account,UAC,authentication
or confined-worker setup grant is missing.

The [Windows reference plan](windows-reference.md) explains Disk Management,
MMC/`.msc`, Computer Management, storage APIs, services and Explorer ownership.
DE-W105's qualified native checkpoint feeds DE-W106's differential evidence
completeness and bounded campaign routing work. DE-W107 observes four generated
partition layouts through declared API and UI actions on an exact Windows build.
Reviewed findings improve existing provider/integration contracts. REA is an
optional research tool; it is not installed or a runtime dependency. These are
planned tasks with explicit inputs and completion criteria in
[work definitions](../spec/work/units.json), not completed experiments or extra
prerequisites for the already-running native work. The original all-platform/
storage objective and release gates remain unchanged.

## Bounded implementation sequence

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

The owner authorized the repository workflow on 12 October 2026: develop and
push checkpoints on `dev`, then merge tested, agent-reviewed checkpoints to
`main` and push them. Retain the earlier goal branch as history. This grants
source-repository synchronization, with owner acceptance and release artifact
publication, installation, signing and storage privileges still separate.

Current work is routed through the programme. NTFS bootstrap, stream, record
closure, directory collection, held-file and owned-worker paths have source-bound
evidence. [DE-W093](../.aide/evidence/2026-10-16-ntfs-directory-command/REVIEW.md)
adds bounded directory-index access through common Windows x64 frontends and
passes all 163 registered native groups. Complete namespace/target membership,
collation, lookup and content remain required. The
[exFAT review](../.aide/evidence/2026-10-16-exfat-tree-review/REVIEW.md) supersedes
older campaigns as active integration blockers while retaining failures and
unknown causes. The [structure assessment](structure-review.md) links ownership,
qualification and remaining release gates without reducing original 0.1.0 scope.

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

The [dated bootstrap validation report](../spec/reports/validation.json) retains its original specification tests and passive AIDE schema checks. Latest revision-bound native/tooling results are linked from the programme record and the evidence below. The repository's DE-W000 handoff under `.aide/handoffs/` retains the exact base, changed files, actual results and outstanding review boundary. DE-W010 native build/launch results are retained separately under `.aide/evidence/2026-10-06-native-bootstrap/`; they do not qualify the full product or replace historical tooling results.

## Decisions that remain open

The [decision register](../spec/catalog/decisions.json) retains the original-code license and staged storage/recovery gates. Added decisions cover the `source/` prefix, finite H/D/S delivery ownership, servicing owner, constrained terminal behavior, measured resource budgets and coherent acquisition. Review decisions at the work boundary that needs them. Resolve the source-layout proposal with DE-W000; do not let later hardware, channel or public-SDK choices block a fake-only binary unnecessarily.

Conflicting attachments remain attributed proposals. The machine-readable [amendment map](../spec/catalog/amendments.json) traces 23 architecture amendments, audit findings and 33 acceptance-test designs to canonical owners and work. Those 33 designs have **not been executed**. The supplied audit's reported ZIP checks cannot certify this repository or an archive that was not supplied.

## Priorities for 19â€“25 October 2026

The supplied status review and Windows integration amendment sharpen the current
sequence without replacing the original 0.1.0 scope. These are priority slots,
not guaranteed daily completion dates:

1. Finish DE-W105's ordinary confined-worker and managed-fixture proof, then its
   current full x64/native/tooling qualification and reviewed `dev` â†’ `main`
   integration. Preserve protected product ACLs, fixture bytes and resource limits.
2. Complete DE-W106's expected-evidence accounting and bounded differential
   coordinator before relying on a new reference campaign.
3. Run DE-W107's four partition cases with the declared API and UI observations.
   Preserve refusals, disagreement and any observation effects on owned media.
4. Replay findings through the existing DE-W030/035 ownership and demonstrate
   an image inspection/acquisition/verification/report workflow. Prepare a
   reproducible internal checkpoint only when its applicable checks pass.

Defer later slots when earlier evidence is incomplete. A weekly checkpoint is
not the finished all-platform/storage 0.1.0 release. Retain the five source owners
and existing provider, integration, broker, Setup and release gates. The supplied
reports are advisory evidence; they grant no new execution or release authority.

## AIDE maintenance

The current reviewed AIDE `dev` pin is `7877e05655ee33fa99583afe4855fac6a4910292` (19 October 2026); the exact tree, selected Git blob hashes and limits live in [aide-lock.json](../spec/references/aide-lock.json). This review used selected blobs and complete tree identity comparison, with no clone or checkout. Use one bounded managed workspace if a disposable source comparison needs files, then remove it after retaining compact identities/results. Never clone into `.aide-local/`. No upstream runtime or worker was launched. Passive validation of all98 current DiskEd WorkUnit exports against the unchanged queue schema is separate from live import and isolation qualification in DE-W061. Published Lite1.1.0 remains an unqualified DiskEd consumer.

Review upstream approximately weekly; the next review is **26 October 2026, Australia/Sydney**. Compare the current pin with the next candidate, inspect changed protocol/authority requirements, revalidate projections and record actual evidence before changing the lock. No automatic schedule, floating dependency or upstream execution is installed by this policy. Review and qualify an exact published version for the selected consumer before adopting it as a runtime dependency.

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
run. The file map covered all 176 files at that checkpoint. Comparison is a declared
fixture pairing, without owned-reader/physical association or provider
admission. /2 cached interfaces, owned raw-reader provenance, composite
identity and live/product/public/platform/owner/full-unit gates remain.

The private /2 cached frontend/actual CLI slice at `829de03c`
([review](../.aide/evidence/2026-10-10-identity-frontend/REVIEW.md)) passes
564 native processes/32350 assertions across x64/x86. A fresh clean
dev.41 product build/launch and all 77 native groups pass; 215 tooling
tests (2 skipped), 1059 structural checks and exact 467-input
closure pass. Every selected current/stale storage row remains evidence-only;
the actual CLI uses existing bounded cached presentation without widening
wire limits. This does not qualify a live /2 product provider or actual /2
window/terminal. Continue owned raw-reader provenance and composite identity;
physical/live/provider/public/platform/owner/full-unit acceptance stays separate.

The owned ordinary-image/layout slice at `c30b6834`
([review](../.aide/evidence/2026-10-12-owned-layout/REVIEW.md)) passes
1362 controller/reader processes and 40412 assertions across 18
x64/x86 campaigns, plus 213 tooling passes/2 skips
and 1061 structural checks. Its private reader binds actual file/process/
capture/context/content observations and independently reconstructs the bytes
before the pure comparison. Unstable or partial-sector captures are incomparable.
The 404 unchanged product inputs reuse dev41's earlier build/77 groups; no new
product execution is claimed. Physical association/current freshness/atomic
consistency, live/provider/public/other-host/owner and full-unit gates remain.
Continue composite identifier/freshness observations under the existing grant.

The owned composite reported identity/epoch comparison slice at `8ca6053d`
([review](../.aide/evidence/2026-10-12-composite-identity/REVIEW.md)) passes
1754 controller/reader processes and 46926 assertions across 20
x64/x86 campaigns, plus 213 tooling passes/2 skips
and 1063 structural checks. Exact /2 process/frame/context/capture bindings
precede immutable derivation; weak identifiers, collisions, conflicts and
original name bytes remain explicit. Caller-declared lookup continuity and
advancing epochs do not prove physical identity or current freshness.
A bound specification changed, so dev.41 was freshly rebuilt/launched and all
77 product groups rerun. Complete evidence and implementing-agent review are
retained. Full-unit/live/provider/public/other-host/owner gates remain open.
Continue cached interface integration under the existing grant.

The coordinator-domain slice at `f1edd134`
([review](../.aide/evidence/2026-10-12-capture-domain/REVIEW.md)) passes
1794 controller/reader processes and 47550 assertions across 22
x64/x86 campaigns, plus 213 tooling passes/2 skips
and 1065 structural checks. Sealed native tokens reject foreign capture
keys, native graph projections and owned identity/raw joins even when counters
match or advance. Tokens survive as evidence without creating a new stream;
serialized labels and process-local ordinals do not admit reconnect or media
identity. Actual u64-boundary refusal uses a separate compiled probe, with the
testing define absent from normal builds. Fresh dev.41 build/launch and all 77
product groups pass; the 25 reducer tests are retained from that same run.
Full-unit/live/provider/public/other-host/owner gates remain open. Continue
bounded composite summary/reference integration into cached interfaces.

The compact identity projection at `d3c23fc0`
([review](../.aide/evidence/2026-10-12-identity-projection/REVIEW.md)) preserves
original detail IDs and adds bounded quality/collision/comparison rows. Exact
complete frame/identity/comparison references resolve through retained native
objects; serialized hashes provide no grant or persistence guarantee. Current
and last complete evidence remain separate through repeated partial captures.
1980 controller/readers and 61730 assertions across 24 x64/x86
campaigns pass, including 34/59/7090 per architecture for the new projection.
Fresh dev.41 launch and 77 product groups, 213 tooling passes/
2 skips and 1067 structural checks pass. This qualifies
private projection/model fixtures; actual owned adapter/coordinator integration
and live/provider/public/historical-host/owner/full-unit gates remain open.

The owned identity adapter at `4666c6f7`
([review](../.aide/evidence/2026-10-12-identity-adapter/REVIEW.md)) prepares matching
immutable graph/evidence before publication and retains exact current/last-complete
owners through repeated partial, rejected, superseded and failed attempts. Explicit
prior-digest/subject comparisons, pure complete references and separate reader
retirement pass 34/60/4338 per architecture. Clean 26 x64/x86 campaigns pass
2168 controller/readers and 70406 assertions; fresh dev.41 build/launch
and 77 product groups, 213 tooling passes/2 skips and
1069 structural checks pass. Original /1 and /2 frame defaults and budgets are
unchanged. This qualifies private owned adapter/model fixtures; the serialized
frontend observation port integration and full live/provider/public/product/
historical-host/owner/full-unit/storage/release admission remain open.

The mixed native inventory port at `2e2f1fb8`
([review](../.aide/evidence/2026-10-12-inventory-port/REVIEW.md)) owns exact
immutable CaptureView/frame/identity publications. Cached callbacks return
aliased pointers without reader advancement or allocating rebuilds; generic
frontend snapshots retain matching native backing through newer delivery and
provider teardown. Provider/frontend allocation failures preserve originals
and the same input remains eligible for retry. Source retirement stays explicit.
New 23/88/7503 controllers/readers/assertions per architecture and 28 clean x64/x86
campaigns (2390 processes/85412 assertions), fresh dev.41 build/launch
and 77 product groups, 213 tooling passes/2 skips and
1071 structural checks pass. Existing defaults and budgets remain. This is
private model/provider composition evidence; actual cached frontend integration,
live/physical/provider/public/product/platform/owner/full-unit/storage/release
admission and the full 0.1.0 programme remain open.

Actual private cached native renderers at `a72454e9`
([review](../.aide/evidence/2026-10-12-inventory-frontend/REVIEW.md)) use the existing
Windows GUI/TUI/linear shell over frozen mixed inventory. Native sources are
explicitly retired and the source session destroyed before rendering; readonly
ports/snapshots retain exact complete frame/reference backing through teardown.
Profile-correct labels, original inert details/focus/manual cached refresh,
health/unavailable-command refusals and hidden console restoration pass.
New 59/36/916 controllers/readers/assertions per x64/Win32 architecture, including
15 actual renderer cases and 44 launcher refusals, pass. Six clean campaigns
total 546 processes/31208 assertions; fresh dev.41 x64 build/launch,
77 product groups, 213 tooling passes/2 skips and
1073 structural checks pass. Existing Fake product defaults and budgets remain.
Ongoing native source advancement, live/physical/provider/public/product/other-host/
accessibility/owner/full-unit/storage/release gates and the full 0.1.0 scope stay open.

Private active native observation delivery at `6e4c2059`
([review](../.aide/evidence/2026-10-12-inventory-advance/REVIEW.md)) wires explicit
serialized application pulses into actual Windows GUI/TUI/linear-shell hosts.
Cached model delivery preserves exact selected IDs, editors and staged review
revision; stale review conflicts, pending replacement refusal, cancellation,
late results, finite hung-reader deadlines, startup recovery and separate actual
retirement pass. Older complete native backing survives newer delivery and
host/session teardown. Shell chooser closure prevents row-index rebinding;
editor/cursor/completion candidates remain exact. GUI/TUI reducer tests separate
late pending-operation completions after changed delivery. Per architecture:
50 controllers/81 readers, including 20 actual hosts and 30 private refusals.
Eight clean campaigns total 808 processes/37960 assertions;
fresh dev.41 x64 build/launch/imports, 77 product groups, 213 tooling
passes/2 skips and 1075 structural checks. Fake product
supplies no source callback. Active screen-mode TUI/callback-failure checks,
live/physical/provider/public/product/other-host/accessibility/owner/full-unit/
storage/release gates remain open; full 0.1.0 scope continues.
The private port fixture alone was corrected at `8cf67f0d` and freshly tested
on both architectures. Each artifact keeps its real source identity; all 404
production inputs are unchanged. The retained parallel joined-report exit-wait
failure is still under investigation despite isolated and full serial passes.

Private native host qualification `b42c23fd`
([review](../.aide/evidence/2026-10-12-inventory-host/REVIEW.md)) adds actual screen
TUI refresh across metadata/full-frame/compact-identity compositions and pending
application-callback failures in GUI and linear/screen TUI/shell. Exact old review
conflicts, retained original owners, internal-error4/unavailable final model sample,
independent actual reader retirement and original console restoration pass.
Per architecture: 62 controllers/113 readers; two campaigns total 350
processes/9190 assertions. Fresh same-source dev.41 x64 build/launch/imports,
77 serial product groups, 213 tooling passes/2 skips
and 1075 structural checks. Production source files/composition and all budgets
remain unchanged. Normal active screen-shell update and actual asynchronous operation
completion remain separate work. The earlier parallel joined-report exit-delay cause
is still unestablished. All broader admission gates and the full 0.1.0 goal remain.

Private deferred delivery `f7b4376f` ([review](../.aide/evidence/2026-10-12-inventory-completion/REVIEW.md)): Private independently controlled deferred read-only completion through native snapshot updates at f7b4376f: GUI, linear/screen TUI and linear shell preserve the exact original target.inspect request, typed parameters, reviewed revision and complete old result; null operation ID. GUI/TUI late results are separate from the new view, shell retains its original request/result transcript. Closing before completion retains an explicitly queued, undelivered result while actual outstanding readers are retired separately. Two x64/Win32 campaigns: 446 processes/11802 assertions, fresh same-source dev.41 x64 build/launch/imports, 77 serial product groups, 213 tooling passes/2 skips and 1075 structural checks. This is synchronously computed and privately withheld interface delivery, not production asynchronous storage execution or durable reconnect. DE-W030 partial, implementer review only; all owner/storage/platform/release gates remain separate.

Private exit-wait diagnostics `b5d6ddfc` ([evidence](../.aide/evidence/2026-10-12-report-exit-diagnostics/README.md)) pass18 owned-process and286 native joined-export checks,213toolpasses/twoskips/1075structure. Failure observations retain the original3000-ms budget, raw wait result, elapsed time and exact state/identity. Native producer remains `f7b4376f`; this private test change adds no current-product rebuild/full-suite or original parallel-cause claim. DE-W030/full0.1.0 and separate admission gates remain open.

GPT repair planning `6b025fdc` ([evidence](../.aide/evidence/2026-10-12-gpt-repair-planning/README.md)): Private immutable GPT-copy repair planning at 6b025fdc98e47f6f5d2e56fb67ee42be1a3dd9af: independently expected capture digest, explicit authoritative source and declared disagreement decision, preserved target layout, owned exact byte patches and scoped shared-parser simulation. Sixteen independent Python byte/CRC tests pass107 native runs; clean current dev.41 build/launch/imports passes78 product groups in one parallel4 campaign,213toolpasses/twoskips/1077structural checks,417source/blob and410product inputs. Source map covers188files once. No image allocation proportional to geometry, file/provider/writer/public-command/journal/recovery admission. DE-W041 partial; owner and full all-platform/storage0.1.0 gates stay open.
Next: Reproduce and repair independent execution-context memory admission using owned Windows job/process fixtures while preserving every per-process/resource limit and typed refusal. Keep the original parallel exit-delay cause unknown unless actual evidence establishes it. Continue GPT footprint/review/admission/image execution work only at the applicable journal/writer/authority gates; preserve full all-platform/storage0.1.0 scope.

Frontend caller coexistence `98a5b593` ([evidence](../.aide/evidence/2026-10-12-job-coexistence/README.md)): Independent compatible Windows frontend caller jobs at 98a5b593f410ae1f63994e7c07c9c138ecd26b0e: verified fresh child retains256MiB per-process cap and every inherited host restriction; shared worker4/128MiB/512MiB quotas unchanged. Twelve native memory/real-product/guard cases and one focused disconnected-client quota test pass, plus78parallel product groups,213toolpasses/twoskips/1079structure and exact current build/launch/import/source evidence. No storage privilege, worker relocation, arbitrary/older-host, owner or full0.1.0 admission.

Weekly AIDE review2026-10-12 ([evidence](../.aide/evidence/2026-10-12-aide-weekly/README.md)) pins dev `6f2abc4c` with36passive WorkUnit validations and unchanged schema. Published Lite1.0.0 remains a separately scoped, unqualified DiskEd consumer. Next source review2026-10-19; no upstream execution/install/import or new native-product claim.

Read-only GPT command `3ff136f1` ([evidence](../.aide/evidence/2026-10-12-gpt-repair-command/README.md)): Ordinary-local-file GPT repair preview at 3ff136f19138ac50dfedcc1c841cccd9ecec1fbc: explicit selected authoritative copy, independently recomputed owned capture binding, five bounded metadata regions and stable rereads, exact immutable patch/plan digests and no output creation or effects. Actual CLI/stdio/GUI/linear-TUI/shell and timeout-slot journeys pass59 independent native cases, one clean dev.42 x64 build/launch/import campaign passes79 parallel4 product groups, 213tooling passes/2skips/1085structural checks, 425source/blob and418product inputs. Source map covers190files once. Writer/recovery/baseline owner/platform/provider/full0.1.0 admission remain separate; DE-W041 partial.

Next: Continue independent image planner/review/receipt and runtime/platform work under the full all-platform/storage0.1.0 goal. Actual image mutation must wait for the concrete journal/durability, original-metadata backup, exact-plan review/grant/admission and independent verification gates. Preserve opaque observation epochs separately from non-unique planning timestamps. Owner/physical/elevation/customer/install/sign/release and untested-host/accessibility qualification remain open.

Owned-image GPT effects `b890f9d3` ([evidence](../.aide/evidence/2026-10-12-gpt-owned-effects/README.md)): Private create-only GPT image execution at b890f9d3afd4ff5080e48bf470ce74a418afcc90: exact independent basis/plan/controller review/grant, actual held file/root/code identities, complete original metadata backup, proposed binary intentions before exact bounded patches and target flush/recapture before completions. Fresh190cases include70 actual own-process exits, all28 normal-run native write/flush boundaries, partial writes/failed or lost acknowledgements, mid-chunk faults, cancellation, no-change, malformed/torn/forged history, foreign bytes and unsafe identity/path refusals. Independent full-image/backup/journal byte oracles and read-only reopening pass. Clean dev.42 x64 build/launch/imports passes80parallel4 product groups,213tooling passes/2skips/1087structural checks,432source/blob and425product inputs. Source map194files once. Product repair stays read-only; production journal/writer, power-loss/recovery/owner/full0.1.0 qualification remain open.

Next: Continue concrete image recovery/review/admission and remaining platform/storage work under the full all-platform/storage0.1.0 goal. A production writer still requires accepted journal/durability, exact resource/code/authority closure, independent backup placement and postcondition qualification. Read-only history inspection supplies no replay/restore/retirement authority. Keep owner/physical/elevation/customer/install/sign/release and untested-host gates separate.

Interrupted owned-image GPT restoration `b2c6a4e3` ([evidence](../.aide/evidence/2026-10-12-gpt-restoration/README.md)): Private DE-W042 interrupted owned-image GPT restoration at b2c6a4e3fa0d4e0c678612617d90ef1797c13c69: read-only immutable whole-image observation, original plan/manifest/backup/journal/code binding, separately validated new review/grant, CREATE_NEW attempt journal and exact reverse patches with native target flush/full-image recapture. 138 focused cases include 51 actual restoration-process exits, all 24 normal-run write/flush boundaries, partial effects, changed review snapshots, replaced objects, journal collisions and interrupted 1 MiB arrays followed by fresh attempts. Original backups/journals and earlier restoration logs remain unchanged. Fresh 190-case original-execution regression and 81 parallel-4 native groups pass; clean dev.42 build/launch/imports retain 213 tooling passes/2 skips/1089 structural checks, 436 source/blob and 429 product inputs, and 196 current source files mapped once. Restoration returns the exact possibly damaged original fixture, not healthy-GPT or general rollback qualification. Product recovery/writes, production journal/durability, independent hardware protection, owner and full 0.1.0 remain open.

Next: Continue bounded DE-W042 read-only inspection of restoration histories and evidence applicability, with explicit semantic receipt/event checks and independent corruption/interruption fixtures. Preserve fresh observation/review/grant requirements and exact resource/code closure for another attempt. Broader recovery/resume, accepted production journal/durability, independent backup placement, real provider/platform and full all-platform/storage0.1.0 qualification remain open; keep owner/physical/elevation/customer/install/sign/release gates separate.

Read-only GPT restoration histories `6c4393b9` ([evidence](../.aide/evidence/2026-10-12-gpt-restoration-inspection/README.md)): Private DE-W042 read-only GPT restoration history inspection at 6c4393b9122a3151b997bde8228e6cd2ffe909c7: exact retained original/pre-restoration observations reconstruct the immutable reviewed definition; current image/artifact state stays separate from accepted receipt/event history. A distinct GENERIC_READ-only existing-store adapter preserves original/new file identities and the same creator executable generation. Independent 121-case semantic/framing/current-state fixtures and 124 inspections within the 138 restoration cases pass, including checksum-valid critical forgeries, torn/corrupt/post-seal histories, old-artifact applicability, native read failures and aliased/replaced store refusals. Fresh 190 execution cases and 82 parallel-4 native groups pass; exact clean dev.42 build/launch/imports retain 213 tooling passes/2 skips/1091 structural checks and 438 source/blob/431 product inputs, with 196 source files mapped once. No inspection writes, replay, product writer/recovery, historical-generation compatibility, physical/power-loss/owner or full 0.1.0 qualification.

Next: Apply the supplied 2026-10-12 structure/release review through targeted build/include/dependency and contributor clarity changes, preserving the existing ownership tree, public IDs and historical evidence. Continue the full all-platform/storage0.1.0 programme and broader DE-W042 recovery/resume qualification; production journal/durability, independent protection, real providers/hosts, owner/physical/elevation/customer/install/sign/release gates remain separate.

Core build-boundary maintenance `7f86f6bf` ([evidence](../.aide/evidence/2026-10-12-build-boundaries/README.md)): JSON codec, command/protocol/lexer and invocation targets are separated with actual consumer declarations and preserved pinned compilation settings. Clean build/launch/imports pass84native groups,16boundary-checker fixtures and5standalone header compilations;120generated targets/3435quoted header edges pass bounded lexical/build-closure checks.215tooling tests ran(213pass2skip). Module-qualified includes, broader header coverage and shared GUI/TUI invariants remain pending; no full-unit/owner/release/all-platform-storage0.1.0 qualification.

Shared GUI/TUI rules055bd850 ([evidence](../.aide/evidence/2026-10-12-shared-presentation/README.md)): Pending request identity/local view epoch and command discovery eligibility are shared in existing presentation owners.34native rule cases/8cross-model tests and all85native groups pass;7standalone headers, bounded generated graph/header checks and213tooling passes/2skips retained. Invalid/duplicate delivery preserves pending/current state; late delivery remains separate. No worker/storage/release authority is inferred. Continue SR-03 and the full programme; owner/platform/storage/recovery/release gates remain separate.

Qualified private headers at 3598ac40 ([evidence](../.aide/evidence/2026-10-13-qualified-headers/README.md)): Cross-module includes identify layer/module under the existing source namespace. CMake header ownership and direct/interface compile-usage checks prevent private header leaks independently of build closure;166 C/C++ files change include directives only.85 native groups/29 checker fixtures/7 header compilations/20 standalone Windows adapter builds pass;213 tooling passes/2 skips retained. No device execution, other-platform/ABI/public SDK or full-unit/owner/release admission. Continue the full programme and broader recovery implementation.

DE-W025 advances supplied-byte FAT allocation inspection independently of the pending production journal gate. Its private profile defines expected results before implementation. Directory/name, extraction, provider/frontend and target qualification remain separate unfinished work; the full 0.1.0 goal is unchanged.

DE-W025 supplied-byte FAT allocation metadata at 97a377d7 has exact clean Windows evidence: 1,335 independent cases, protected bounds, 87 native groups and strict GCC 15.2 syntax. [Evidence](../.aide/evidence/2026-10-13-fat-allocation/README.md). Continue directory/name, allocation/extraction and provider/frontend capability work; this private reader does not close full FAT or 0.1.0 qualification.

DE-W026 FAT directory/name observations at 205e6cd8 retain 6,790 independent cases, protected full/partial records and 89 native regression groups. [Evidence](../.aide/evidence/2026-10-13-fat-directory/README.md). No lookup, extraction, provider/frontend, mount/writer or full 0.1.0 admission; continue bounded traversal and volume integration.

DE-W027 bounded FAT capture at f98712a4 has 149 independent supplied-reader/ordinary-file cases and 91 native regression groups. [Evidence](../.aide/evidence/2026-10-13-fat-capture/README.md). It adds real volume tree/file extents while preserving separate global allocation, namespace, extraction, worker/frontend, host and storage/release admission.

DE-W028 optional global FAT allocation at 0e414ccd has 86 independent cases, including 21 ordinary-file cases and 92 native groups. [Evidence](../.aide/evidence/2026-10-13-fat-allocation-scan/README.md). Coverage, tree/copy applicability and detail omissions stay separate; auxiliary/namespace/extraction/worker/frontend/host and full release gates remain open.

DE-W029 auxiliary FAT metadata at 87e7e246 has 257 independent cases (24 ordinary-file) and 94 native groups. [Evidence](../.aide/evidence/2026-10-13-fat-auxiliary/README.md). Source/driver/advisory/backup dimensions remain separate; namespace, extraction, actual worker/frontend/host and full 0.1.0 gates remain open.

DE-W036 FAT namespace at `330c223c` retains original aliases and explicit Windows
text/rule models, with 171 independent cases, 95 native groups and 12 headers.
[Evidence](../.aide/evidence/2026-10-13-fat-namespace/README.md). Actual consumers,
larger coverage, extraction, contained worker/frontend and full 0.1.0 gates remain
open. Current work is owned by the programme record, rather than historical
checkpoint paragraphs in this plan.

DE-W037 contained FAT reader at `56effc8f` retains exact file/process/region evidence with 109 focused cases and 96 native groups. [Evidence](../.aide/evidence/2026-10-13-fat-worker/README.md). Continue shared command/frontend admission, larger coverage and extraction under the original full platform/storage goal; owner and release gates remain open.

DE-W038 shared FAT image inspection at `57cfd113` passes 62 focused cases and 97 native groups with 17 independent headers. [Evidence](../.aide/evidence/2026-10-13-fat-command/README.md). This qualifies the bounded Windows ordinary-file prototype; larger coverage, retrieval/extraction, mounted consumers, other hosts and full platform/storage/release remain open.

DE-W039 allocation windows at `543826fe` pass 34 interval / 44 command cases and 99 native groups. [Evidence](../.aide/evidence/2026-10-13-fat-window/README.md). Windows ordinary-file prototype only; coherent multi-window/directory/namespace coverage, retrieval/extraction and further consumer/host/platform/storage remain open.

The [13 October structure follow-up](structure-review.md) keeps the existing ownership tree and records the supplied review dispositions against newer source-bound evidence. DE-W044 now has retained native qualification at `4d3dc0a3`, integrated into `main` and `dev` at `f8a3eb84`; continue the programme's remaining traversal/extraction and platform/storage work. This documentation maintenance does not accept the baseline, close the wider native work programme or narrow the full 0.1.0 scope.


DE-W066 reaches local implementing-agent review at exact clean source `e43f00fb`.
Its private supplied-byte upcase descriptor, streaming map and complete name
comparison pass 244 independent scenarios, 15 selected native groups, one header,
strict C90/import/context/source checks and 242 tooling tests with two skips.
[Retained evidence](../.aide/evidence/2026-10-14-exfat-upcase-qualified/README.md) separates this result from the prior complete native suite.
Continue bounded root/active-FAT/bitmap/upcase source coherence, then tree/content
and native integration. The original full platform/storage 0.1.0 and owner,
production writer/recovery, privilege and release gates remain unfinished.


DE-W067 reaches local implementing-agent review at exact `bba3d600`: 121 image
cases in nine methods, 19 selected native groups, one private header, imports,
context/input hashes and 242 tooling tests with two skips pass. The clean sparse
checkout contains every registered/build input and all current implementation,
tests, spec, docs, tools and external files; unused historical evidence is
excluded. This is not a fresh full native suite or complete archive checkout.
Repository evidence is `.aide/evidence/2026-10-14-exfat-capture-qualified/`.
Continue actual held source/worker and coherent namespace/tree/content integration;
owner, other-platform/storage, production and full original release remain.


DE-W068's available ordinary-file scope reaches local agent review at exact
`c73c6870`: 60 native cases/seven methods, 20 selected regression groups, one
header, normal/fault imports/context/source hashes and 242 tooling tests with
two skips pass. Actual file-symlink creation remains unverified without privilege;
leaf/ancestor junction and hardlink checks pass. The clean sparse checkout contains
every registered/build input and current source/tests/spec/docs/tools/external
files, excluding unused historical evidence. No fresh full native-suite or archive
checkout claim. Repository evidence: `.aide/evidence/2026-10-14-exfat-file-qualified/`.
Contained worker, coherent namespace/tree/content and original full0.1.0 remain.


DE-W069 reaches bounded local review at exact full clean `cce05d17`: all 139
current native groups, 69 reader cases/six methods, 63 file cases/eight methods,
46 standalone headers, imports/context/source hashes and
242 tooling tests with two skips pass. The complete native regression covers
the shared process-retirement change; previous working failures and their repairs
remain retained. See `.aide/evidence/2026-10-14-exfat-worker-qualified/REVIEW.md`. An unavailable file-symlink fixture
remains unverified. Next, bind the existing image.inspect exFAT view through the
shared services/frontends, including both upcase representations and explicit
ambiguity. Complete tree/content, other hosts, original full platform/storage0.1.0,
physical writer/recovery, owner acceptance and release qualification remain.
