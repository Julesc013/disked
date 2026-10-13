# DiskEd development checklist

Status: active all-platform/storage 0.1.0 development, with source-bound native and image-prototype evidence. Baseline/implementation owner acceptance and release qualification remain pending. This checklist summarizes [canonical work definitions](spec/work/units.json), [decisions](spec/catalog/decisions.json) and the [development plan](docs/development-plan.md); it does not grant execution or record acceptance.

## Specification preparation

- [x] Read and reconcile all 13 supplied design/audit files with their provenance and conflicts retained.
- [x] Update canonical architecture, safety, acquisition, composition, installation, target and delivery contracts.
- [x] Map proposed acceptance scenarios to work without representing them as executed tests.
- [x] Fetch AIDE dev at `5be37bd6510977e6cb2e960859c45b33b048dade` and pin source observations.
- [x] Run local specification/tooling tests and passive AIDE schema validation; retain actual results and skipped checks in the [validation report](spec/reports/validation.json).
- [ ] Review and accept the final DE-W000 amendment, including the proposed `source/` ownership map.

## Active 0.1.0 goal

Scope: every currently specified platform and storage operation at base `40ac8ec`.
Continue local implementation after tests and agent review; owner acceptance and
release/storage authority remain separate. The programme record is
`.aide/programmes/disked-0.1.0.json`. No partial milestone means 0.1.0 is finished.

## First implementation

- [x] DE-W010: implement the granted native fake-only bootstrap and run its bounded build/launch checks.
- [ ] Review and accept DE-W010 using its clean-build evidence and declared limitations.
- [x] DE-W011 local slice: native mode inspection, policy parity, stdio and inherited-console tests.
- [ ] Complete/review Explorer, terminal/remote and other Windows launch qualification before shipping invocation claims.
- [x] DE-W013 local development: immutable fake graph, shared service, identity selection and stale-revision refusals; owner acceptance pending.
- [x] DE-W014 native console slice: screen/linear views, typed command explorer, service parity and console restoration; owner acceptance pending.
- [ ] Qualify screen-reader, other terminal backends and remote/legacy environments at their applicable gates.
- [x] DE-W015 local development: native Win32 adapter, shared typed forms and actual window evidence; owner acceptance pending.
- [x] DE-W016 local development: same-file fake workers, reconnect, cancellation and uncertain outcomes; clean reproduction and agent review retained, owner acceptance pending.
- [x] DE-W019 local Windows slice: bounded shell, clean reproduction, synthetic console evidence and agent review; owner acceptance and usability qualification remain pending.
- [x] DE-W017 local slices: interactive/worker containment and bounded CLI/stdio requests and output; owner acceptance pending.
- [x] DE-W017 local store-failure slice: inject full/partial/flush boundaries, preserve unknown claim/cancellation receipts and prevent replay.
- [x] DE-W017 local observation slice: capture/worker epochs, bounded notices, retained updates and combined native provider failures across frontends.
- [x] DE-W012/017 local watch: typed fake events, negotiated live NDJSON, digest-bound reconnect, bounded observers and GUI/TUI/shell parity.
- [x] Bring DE-W012/017 to the local fake-provider review boundary with recorded native tests; clean reproduction and agent review govern continuation to DE-W018. Owner acceptance and real filesystem/persistence/other-host qualification remain separate.
- [ ] DE-W018 active: C90 arithmetic/byte/text control probes and exact installed-tool inventory; historical compiler/loader/terminal qualification remains open.
- [x] DE-W020 internal implementation: checked C90 values, bounded byte views, endian fields and named extents; clean reproduction and local review govern continuation.
- [ ] DE-W021-035: progress through image readers, explicit Windows observation/acquisition and optional native adapters using exact work prerequisites.
- [ ] DE-W040-043: review recovery and image-only mutation/formatting gates before any executor work.
- [x] DE-W034 private joined acquisition/verification report and two-source support export: clean native evidence and local review retained; full unit/owner gates remain open.
- [x] DE-W034 private joined-report producer/contained-worker contracts: clean native evidence and local review retained; full unit/owner gates remain open.
- [x] DE-W034 provisional joined common command/frontend slice: clean dev.36 evidence and implementing-agent review retained in `.aide/evidence/2026-10-10-joined-report-public/`; full unit/owner/platform/storage gates remain open.
- [x] DE-W034 private same-file verification worker, finite history cursor, cancellation and collections have clean native qualification; full work/owner/physical gates remain separate.

## Delivery and maintenance

- [ ] Resolve original-code licensing before redistribution; review third-party rights independently.
- [ ] DE-W060/062: qualify deployment profiles, finite carriers and one servicing owner per installation.
- [x] DE-W060 local fixture slice: exact Setup schema/source mapping, independent native payload equality, occupied-root retention and interrupted-write checks; clean evidence and agent review retained. Live SDK/lifecycle and full unit/owner qualification remain open.
- [x] DE-W060 local native source consumer: clean source-bound ABI/ownership, bounded read-only ZIP observations and FacMan-format refusal retained with agent review. Installed SDK/CoreShared/live lifecycle and full unit/owner qualification remain open.
- [x] DE-W062 bounded local H/D/ZIP and generated-view servicing preview: clean source `d4102ab` passed native/source reproduction and implementing-agent review. Exact D bytes and independent H/S bindings are retained in `.aide/evidence/2026-10-10-carrier-fixtures/`; embedded/native carriers, live ownership/interlocks and full unit/owner/channel gates remain open.
- [x] DE-W063 local checker implementation: separate nonempty staging inventory, bounded ZIP verification and owned regression fixtures. Owner acceptance, release-candidate qualification and publication remain open.
- [ ] DE-W061: validate live AIDE import and worker boundaries in a separately authorized disposable environment.
- [ ] Review AIDE roughly weekly; next review **2026-10-19**. Update exact pins and evidence until a stable release is reviewed and qualified. No automatic schedule is configured.
- [ ] DE-W080/090: qualify exact target/operation compositions and satisfy scoped release gates.

The DE-W010 checks cover only the essential native human subset and provider-initialization boundary. Full runtime/provider behavior, recovery, hardware, installer and release qualification remain unverified. Exact results and limitations are retained under `.aide/evidence/2026-10-06-native-bootstrap/`.

## Corrective review at 08a8246

- [x] Reproduce the six reported tool/policy behaviours in disposable local fixtures.
- [x] Correct per-path impact, declared input closure, historical receipt applicability, protocol bounds/identities and CLI prompt permission.
- [x] Define terminal-session, explicit shell, output/progress and command-metadata contracts; retain icon-report claims without adopting unavailable assets.
- [ ] Review the corrective diff and its actual regression evidence at the DE-W000 boundary.
- [ ] Review/accept DE-W019 independently of its local implementation and synthetic console evidence.
- [ ] Before routine native contributions, activate and verify the owner-selected required PR/check gate on GitHub.
- [ ] At protocol/acquisition/writer gates, qualify typed resources, compatible readers, guarded epochs, immutable-plan receipts and composable recovery properties.

## CLI syntax refinement

- [x] Reconcile flexible option placement, natural aliases and contextual help with current catalogs and docs.
- [x] Define shared syntax equivalence/error cases, preserving unresolved typed storage parameters and unrun native parser status.
- [x] DE-W012 synchronous subset: execute the shared syntax corpus, option permutations, bounded protocol and provider-initialization trap on Windows.
- [x] Implement and test the admitted fake asynchronous protocol identities, negotiation and reconnect with DE-W016/017; production/other-host admission remains separate.
- [x] DE-W019 local tests: editable error recovery, completion/history and retained synthetic input timings.
- [ ] DE-W019: qualify human entry/correction/recall ergonomics on selected keyboards and terminal profiles.
- [ ] DE-W018/071: qualify actual tokenization/encoding and shared parser semantics for selected constrained targets.

- [x] DE-W021 internal MBR/EBR parser and synthetic corpus implemented; retained clean reproduction and local review govern continuation. Owner acceptance and image-provider admission remain separate.

- [x] DE-W022 internal GPT readers implemented; clean source-bound proof and local review govern continuation. Image-provider and writer admission remain separate.

- [x] DE-W023 corpus/adapters and bounded sanitizer campaign implemented; source-bound clean reproduction and local review govern continuation to W024. Owner acceptance remains separate.

- [x] DE-W024 local raw-file prototype: shared image/table commands and actual CLI/stdio/GUI/TUI/shell parity; retain coverage/consistency limits. Owner acceptance, physical storage, containers and whole-image qualification remain separate.

- [ ] DE-W033 acquisition: Windows ordinary-file public prepare/execute/inspect/cancel/watch, native GUI/TUI/shell, structured input, bounded watch and copy/cancel/resume have clean source-bound fixture evidence. The requirement audit keeps physical backing, thin provisioning, real failing media, power loss and other-platform qualification open; W033 remains partial. See `.aide/evidence/2026-10-09-acquisition-public/`.
- [x] Bounded GUI screenshot-helper repair: owned-window redraw and measured client RGB guard are implemented with retained frame-only/alpha regressions and actual inventory/review/minimum-window checks. Retain exact clean source/host/capture evidence; complete visual, accessibility, DPI and platform qualification remain open.
- [ ] DE-W040 active: proposed binary framing codec and independent native byte/corruption/torn-tail/stream-budget tests implemented. Immutable fake-model definitions, separate data-bound receipts and composable recovery properties are proposed with an independent native fixture suite. Closed guarded fake-memory transitions, crash/fault recovery and epoch/dependency checks now have a native fixture suite. A private semantic binary reader now checks immutable payloads, receipt references, event/capture order and recovery declarations against independent native fixtures. A private native model-history producer now generates independently checked binary fixtures from recorded action proofs. Repeated-crash, checkpoint/cancellation, append/flush and resource-change audits now preserve exit proofs and attempt-local intentions. Review the exact format/durability proposal before live adapters. No production writer admission while DE-DEC-004 remains unresolved.

- [ ] Review DE-W063: local completeness tooling and regression checks implemented; retain clean source-bound native staging evidence at the review boundary. Owner acceptance, publication, authenticity and runtime remain separate.

- [ ] DE-W032 active: verify the provisional fake-only health.assess command through the shared CLI/stdio/GUI/TUI/shell service, retaining exact target/revision checks, explicit unknown/unavailable data and opt-in support disclosure. The bounded private collector is implemented. Native SMART/adapters, provider admission, containment and physical/platform qualification remain open.

- [ ] DE-W034 active: complete the broader case/custody programme and physical/platform qualification. Provisional acquisition-only evidence.export has retained native qualification; the joined public variant has clean dev.36 native qualification on the recorded host. Authenticated forensic/custody claims remain unqualified.

- [ ] DE-W034: admit native consent-selected report-file export through the bounded shared service; retain acquisition/custody and physical/platform qualification gates.

- [x] DE-W033 bounded shared-parent repair: retain the old destination/map rename defect, require readable/listable directory pins with no write/delete sharing, recheck every ancestor generation/path and bound source/code/output paths, and refuse weaker fallback. Generated-file regression evidence lives in `.aide/evidence/2026-10-09-parent-pins/`; W033, other-platform/physical qualification and owner acceptance remain open.

- [x] DE-W033/017 bounded worker-state directory repair: shared strong pins and all-generation/path checks, metadata-only refusal, exact opened-child paths, guarded executable-parent launch and retained post-CREATE_NEW failure facts. Generated-file evidence: `.aide/evidence/2026-10-09-worker-store/`. W033/017, full 0.1.0, physical/other-platform qualification and owner acceptance remain open.

- [ ] DE-W034 recorded acquisition cases: qualify immutable native metadata snapshots, exact revisions, all disclosure gates and typed report export on real generated-file acquisitions; public admission/containment and current-image/authenticated custody remain open.

- [ ] DE-W034: qualify joint acquisition-case/source/export admission, then bind the durable report worker/store and complete public service/frontend integration before availability.

- [ ] Qualify private report-worker execution evidence, then close public export
  prepare/execute contracts, bounded common service/watch and frontend journeys.
  Preserve uncertain attempts, created output and independent exit observations.

- [ ] Admit the defined export service only after bounded inspect/cancel/watch and actual frontend journeys; retain private parser/request/form evidence separately.

- [ ] Qualify report watch/reconnect evidence, then admit its exact service/composition through bounded product requests and actual frontend journeys.

- [ ] Qualify candidate recorded acquisition export/report backend in actual bounded CLI/stdio/GUI/TUI/shell journeys; retain exact bytes/imports and separate full case/custody and platform gates.

- [ ] DE-W034: the private current acquired-image verifier is locally verified; retain verified immutable observation/support evidence; qualify bounded historical collections/private retention and product reader/watch/frontend integration. Preserve source-preservation/actor/physical and owner/platform gates separately.

- [x] Shared provisional image.verify command/event slice has clean private native
  qualification: exact grants/replies, actual owned workers, public/private bounds
  and independent producer contracts. Evidence: `.aide/evidence/2026-10-10-verification-commands/`.
- [x] Product verification request containment and actual CLI/stdio/GUI/TUI/shell
  prepare/execute/watch have clean native qualification at dev.34. Evidence:
  `.aide/evidence/2026-10-10-product-verification/`.
- [x] Selected retained historical verification collection/case/report support export
  has native and frontend qualification at dev.36 (`2026-10-10-joined-report-public`). Keep full DE-W034, authenticated
  custody/current-image authority, all platforms/storage and owner/privilege/release
  gates open.

- [x] DE-W030 private volume namespace adapter: clean x64/x86 builds each passed
  49 native fixture executions and 258 assertions at `17129e6e`. Evidence:
  `.aide/evidence/2026-10-10-nt-volume-namespace/`. No live API dispatch or product admission.
- [x] DE-W030 contained injected namespace observer: clean x64/x86 late/cancel/
  hang/crash/retirement/disconnect and bound producer-refusal campaigns at `d3798a7`.
  Evidence: `.aide/evidence/2026-10-10-nt-contained/`. No live/product/provider admission.
- [ ] DE-W030: qualify actual new-profile interfaces/admission; continue native identity/
  raw layout and live/provider/service/platform admission. Full unit,
  physical/owner/release authority and the full 0.1.0 scope remain open.

- [x] DE-W030 private common capture publication/retirement boundary: clean dev.37
  product regression, 16 reducer tests and x64/x86 owned-reader lifecycle/worker
  campaigns at `2d753bae`. Evidence: `.aide/evidence/2026-10-10-capture-publication/`.
  Empty lifecycle graphs do not qualify namespace node projection or admission.

- [x] DE-W030 private namespace observation graph: clean dev.38 at `3463fb23`,
  77 product groups, 23 reducer tests and x64/x86 owned-reader graph campaigns.
  Evidence: `.aide/evidence/2026-10-10-namespace-graph/`. Observation IDs do not
  establish physical identity or live/frontend/product/provider admission.

- [x] DE-W030 private injected storage query/frame/graph slice: clean x64/x86
  70 native fixture executions and 1,987 assertions each at `e469d70f`.
  Evidence: `.aide/evidence/2026-10-10-storage-queries/`. The dev.38 product's
  401 inputs remain unchanged. Reader containment, real storage identity and
  live/frontend/provider/platform/owner/full-unit admission remain open.

- [x] DE-W030 shared owned namespace/metadata host and startup/retry reconciliation:
  clean x64/x86 new 43/35/671 campaigns plus all existing private regressions at
  `16259b7a`. Evidence: `.aide/evidence/2026-10-10-storage-worker/`.
  Product inputs remain unchanged; live/frontend/provider/platform/owner/full-unit
  and every broader 0.1.0 platform/storage qualification remain open.

- [x] DE-W030 compiled private cached frontend: clean dev.39 at `8f55d867`,
  77 product groups and x64/x86 15/26/1300 frontend campaigns,
  with all private regressions retained. Evidence: `.aide/evidence/2026-10-10-observation-frontend/`.
  Ordinary product stays Fake; physical/live/provider/protocol/platform/owner/full-unit gates stay open.
- [x] Source ownership clarification: CLI presentation under `cli/`, all-mode
  composition under `app.*`, explicit `tui_model.*` and toolkit-free GUI model
  under `gui/`. `docs/source-map.md` covers all 176 current files and future owners;
  no speculative empty tree or public identifier change.

- [x] DE-W030 private device ID/alignment/OS-layout query fixtures at `b853621b`:
  both x64/x86 57 cases/197 assertions, affected private regressions and exact
  source/build/import evidence. `.aide/evidence/2026-10-10-identity-queries/`.
  Product inputs unchanged; owned-frame integration, independent raw comparison,
  composite identity and live/provider/platform/owner/full-unit gates stay open.

- [x] DE-W030 private /2 owned identity/layout frame and graph at `6b883c01`:
  both x64/x86 54 controllers/41 reader launches/6980 assertions, all existing
  private regressions, pure replay/refusal and maximum bounded cache checks.
  `.aide/evidence/2026-10-10-identity-frame/`. Product inputs unchanged;
  /2 interfaces, raw comparison, physical identity and all admission gates remain.

- [x] Shared text-input ownership and detailed source guide at `67f3cfb0`:
  `TextKey`/`TextInput` under runtime presentation; shell no longer imports TUI.
  Clean dev.40 product/77 groups at `3f648127`; x64/x86 cached
  frontend campaigns at `67f3cfb0`, with all 404 product inputs unchanged.
  Evidence: `.aide/evidence/2026-10-10-source-layout/`; future owners documented,
  without freezing speculative filenames or claiming zero later refactoring.

- [x] Private generated-image raw-layout comparison at `4400cb71`: 218 raw
  processes/2684 assertions across x64/x86; two existing injected query
  campaigns bring this run to 472 processes/7052 assertions. 215 tooling
  tests, two skipped; 1057 structural checks; exact 461-input closure.
  All 404 shipped-product inputs unchanged. Evidence:
  `.aide/evidence/2026-10-10-raw-layout/`. /2 cached interfaces, owned raw
  provenance, physical identity and live/provider/public/platform/owner/
  full-unit/all-platform-storage gates remain separate.

- [x] Private /2 cached frontend/actual CLI slice at `829de03c`:
  564 processes/32350 assertions across x64/x86 plus a new dev.41
  product build/launch and all 77 native groups. 215 tooling tests,
  2 skipped; 1059 structural checks; exact 467-input closure.
  Evidence: `.aide/evidence/2026-10-10-identity-frontend/`. Owned raw
  provenance, composite identity and live/provider/public/platform/owner/
  full-unit/all-platform-storage gates remain separate. Development uses
  owner-authorized `dev` pushes and tested integration into `main`.

- [x] DE-W030 private owned ordinary-image/layout provenance slice `c30b6834`:
  1362 native processes/40412 assertions, 213 tooling
  passes/2 skips, 1061 structural checks; exact-source,
  build/import/hash evidence and implementing-agent review retained at
  `.aide/evidence/2026-10-12-owned-layout/`. Product dev41 evidence is reused
  through 404 unchanged inputs, not freshly rerun. Full DE-W030 remains partial.
- [x] DE-W030 private composite reported identity/epoch slice `8ca6053d`:
  1754 processes/46926 assertions across x64/x86, a fresh dev.41
  build/launch and all 77 product groups; 213 tooling passes/
  2 skips and 1063 structural checks. Exact-source/build/
  import/hash evidence and implementing-agent review are retained under
  `.aide/evidence/2026-10-12-composite-identity/`. Physical identity/freshness
  remain unknown; full DE-W030 remains partial.
- [x] DE-W030 sealed coordinator-domain guard slice `f1edd134`:
  1794 processes/47550 assertions across 22 x64/x86 campaigns;
  actual counter-exhaustion refusal, foreign key/graph/owned-join rejection,
  fresh dev.41 build/launch and 77 product groups including 25 reducer tests.
  213 tooling passes/2 skips, 1065 structural
  checks, exact source/build/import/hash evidence and implementing-agent review
  under `.aide/evidence/2026-10-12-capture-domain/`. Full DE-W030 remains partial.
- [x] DE-W030 private compact identity projection `d3c23fc0`: original
  detail IDs, quality/collision/comparison summaries, complete native reference
  resolution, bounded current/last-complete cached model coverage; 1980
  processes/61730 assertions across 24 x64/x86 campaigns, fresh dev.41
  build/launch and 77 product groups. 213 tooling passes/
  2 skips and 1067 structural checks. Full DE-W030 partial;
  implementing-agent review in `.aide/evidence/2026-10-12-identity-projection/`.
- [x] DE-W030 private owned identity adapter `4666c6f7`: accepted graph and
  matching immutable current/last-complete native evidence, explicit prior-digest/
  subject comparisons, pure references, repeated partial/rejected/late/allocation/
  outstanding-reader coverage. 2168 processes/70406 assertions across
  26 x64/x86 campaigns; fresh dev.41 build/launch and 77 product groups;
  213 tooling passes/2 skips, 1069 structural checks.
  Full DE-W030 partial; implementing-agent review in
  `.aide/evidence/2026-10-12-identity-adapter/`.
- [x] DE-W030 private mixed native inventory port `2e2f1fb8`: sealed
  current/last-complete publications, pure cached aliased graph delivery, exact
  frame/reference ownership through retained snapshots and teardown, selected
  allocation retry and actual separate reader retirement. 2390 processes/
  85412 assertions across 28 x64/x86 campaigns; fresh dev.41 build/launch and
  77 product groups; 213 tooling passes/2 skips,
  1071 structural checks. DE-W030 remains partial; implementing-worker review
  in `.aide/evidence/2026-10-12-inventory-port/`.
- [x] DE-W030 private actual cached native GUI/TUI/linear shell `a72454e9`:
  frozen mixed native inventory, exact complete backing through source-session/
  renderer teardown, inert original names, focus/refresh, authority refusals,
  bounded launcher/no-clobber checks and restored owned-console state. New
  59/36/916 per architecture; six clean x64/Win32 campaigns, 546 processes/
  31208 assertions, fresh dev.41 x64 launch and 77 product groups,
  213 tooling passes/2 skips, 1073 structural checks.
  DE-W030 remains partial; implementer review in
  `.aide/evidence/2026-10-12-inventory-frontend/`.
- [x] DE-W030 private active native observation delivery `6e4c2059`:
  actual GUI/TUI/linear-shell refresh, preserved exact focus/editor/reviews,
  source deadlines/cancel/late/startup failure/retirement, held old backing and
  GUI/TUI pending completion regressions. Eight x64/Win32 campaigns:
  808 processes/37960 assertions, fresh dev.41 x64 launch and
  77 product groups, 213 tooling passes/2 skips,
  1075 structural checks. Private port fixture corrected/tested at `8cf67f0d`;
  all 404 production inputs unchanged, per-artifact source identities retained.
  Partial; implementer review in
  `.aide/evidence/2026-10-12-inventory-advance/`.
- [ ] Investigate the retained joined-report worker exit wait failure; preserve
  the original3000-ms wait and distinguish finished receipts from actual exit.
- [x] DE-W030 private screen TUI delivery and escaping callback teardown `b42c23fd`:
  62 controllers/113 readers per architecture; 350 total processes,
  9190 assertions, fresh dev.41 x64 launch/imports, 77 serial product groups,
  213 tooling passes/2 skips and 1075 structural checks.
  Exact old reviews, unavailable failure sample, original console restoration and
  independent actual retirement; partial implementer review in
  `.aide/evidence/2026-10-12-inventory-host/`. Normal screen-shell updates and actual
  asynchronous storage-operation completion remain unqualified.
- [x] DE-W030 private deferred read-only delivery `f7b4376f`: GUI, linear/screen
  TUI and linear shell, exact old request/revision/result/opnull and close-before-
  completion ownership. Two x64/Win32 campaigns: 446 processes/11802
  assertions; fresh dev.41 launch/imports, 77 serial product groups, 213
  tooling passes/2 skips, 1075 structural checks. Evidence in
  `.aide/evidence/2026-10-12-inventory-completion/`; DE-W030 partial. This privately
  withholds a synchronous result; production asynchronous storage execution/durable
  reconnect and screen-shell deferred delivery remain unqualified.
- [ ] Diagnose the retained parallel frontend.joined_report reader-exit delay;
  retain the exact 3000-ms wait and require actual process exit independently of
  receipts. Keep full 0.1.0 scope and all owner/storage/platform/release gates.

- [x] Private report exit-wait diagnostics `b5d6ddfc`:18 owned-process and286 joined-export checks,213toolpasses/twoskips/1075structure. Exact unchanged3000ms/raw result/timing/identity guards; native producer remains `f7b4376f`. Original parallel cause remains unknown; partial evidence in `.aide/evidence/2026-10-12-report-exit-diagnostics/`.

- [x] DE-W041 private supplied-capture GPT repair planning `6b025fdc`:16tests/107native runs, exact immutable before/after patches and independent byte/CRC oracles;78parallel product groups,213toolpasses/twoskips/1077structure. Public command/writer/recovery/other-host/owner/full-unit gates remain open.
- [x] Independent compatible caller memory jobs `98a5b593`:12native cases, actual256MiB fresh child/inherited64MiB denial, real protocol/discovery coexistence, all guards/host policies and shared4-worker quotas retained;78product/213tools/twoskips/1079structure. Exact scoped evidence in `.aide/evidence/2026-10-12-job-coexistence/`; arbitrary/legacy/worker/storage admission remains separate.

- [x] Weekly AIDE source review2026-10-12: exactdev `6f2abc4c`, unchanged queue schema and36passive WorkUnit validations; Lite1.0.0 publication/scope recorded separately. No upstream execution/install/import/stable-consumer qualification.

- [x] DE-W041 read-only ordinary-image GPT repair preview: explicit source/selection binding, bounded capture/rereads, immutable patch digests, native CLI/stdio/GUI/linear TUI/shell and timeout-slot evidence at `3ff136f1`. Clean79product groups and59focused cases; [evidence](.aide/evidence/2026-10-12-gpt-repair-command/README.md). Mutation/recovery, owner acceptance and full0.1.0 remain open.

- [x] DE-W041 private create-only GPT effects: actual owned-image write/flush/backup/intention/completion and read-only interrupted-state evidence at `b890f9d3`.190cases/70process exits/80native groups; [evidence](.aide/evidence/2026-10-12-gpt-owned-effects/README.md). Existing-target/product writer, production journal, power-loss/recovery, owner and full0.1.0 remain open.

- [x] DE-W042 private owned-image restoration: exact reverse patches, fresh review/grant and attempt journal, original-artifact preservation and interrupted multi-chunk recovery at `b2c6a4e3`.138 restoration/190 execution cases and 81 native groups; [evidence](.aide/evidence/2026-10-12-gpt-restoration/README.md). Product/production recovery, power-loss, independent protection, owner and full0.1.0 qualification remain open.

- [x] DE-W042 private read-only restoration history:121 semantic/framing/current-state cases and124 existing-store inspections, with138 restoration/190 execution cases and82 native groups at `6c4393b9`; [evidence](.aide/evidence/2026-10-12-gpt-restoration-inspection/README.md). Broader recovery, historical generations, product/production, hardware/owner and full0.1.0 remain open.

- [ ] 2026-10-12 source maintenance: current-work/formatter clarity and core target separation/bounded generated header/dependency checks now have evidence. Module-qualified includes, compile-header visibility and shared frontend invariants now have bounded source evidence. Continue broader header/host coverage, composition policy and formatting work; preserve current tree/public contracts/historical evidence. See `spec/catalog/source-maintenance-prototype.json` and `.aide/evidence/2026-10-12-build-boundaries/README.md`.
- [x] Core build boundaries `7f86f6bf`: clean build/launch/imports,84native groups,16checker fixtures,5standalone core headers,120generated targets/3435quoted include edges and213tooling passes/2skips. Bounded lexical/build-closure checks; full units/owner/release/all-platform-storage0.1.0 remain open.

- [x] Shared presentation055bd850: GUI/TUI request/view correlation and discovery eligibility consolidated in existing owners;34native rule cases/8cross-model tests,85native groups,7standalone headers,213tooling passes/2skips. SR-03/module-qualified headers, broader platform/storage and owner/release remain open; `.aide/evidence/2026-10-12-shared-presentation/README.md`.

- [x] Qualified private headers at 3598ac40: layer/module include names and CMake owned/exported header visibility;85 native groups,29 checker fixtures,7 header compiles,20 Windows adapter compiles,213 tools/2 skips.196 source files retained; no physical execution/ABI/SDK/full-unit/owner/release qualification. `.aide/evidence/2026-10-13-qualified-headers/README.md`.

- [x] Supplied-byte FAT allocation metadata at 97a377d7: C90 layout/entry/bounded-chain reader; 1,335 independent cases, protected bounds, 87 native groups, eight headers and strict GCC 15.2 syntax. No public FAT/provider/directory/extraction/mount/writer or owner/full-release qualification.

- [x] FAT directory/name metadata at 205e6cd8: exact OEM/UTF-16 representations and checksum/order correlation with reversible display; 6,790 cases, protected records and 89 native groups. Traversal, lookup, extraction, provider/frontend, host, owner and full 0.1.0 remain open.

- [x] Bounded FAT volume/tree/file-extent capture at f98712a4: streaming cells, exact record/name provenance, partial/cycle/copy/cross-link outcomes and ordinary read-only Windows image verification. 149 cases/91 native groups. Global allocation, extraction, frontend, host, owner and full 0.1.0 remain open.

- [x] Global FAT allocation at 0e414ccd: paged data-cluster counts, copy/raw variants, graph/cycle/merge findings and ownership applicability; 86 cases/92 native groups, default 149 capture cases retained. Auxiliary metadata, namespace, extraction, frontend, owner and full 0.1.0 remain open.

- [x] FAT auxiliary metadata at 87e7e246: C90 header/FSInfo, explicit backup/copy/raw agreement and count/hint applicability; 257 cases/94 native groups, 206 source files. Namespace, extraction, worker/frontend, consumer/host, owner and full release remain open.

- [x] DE-W036 bounded FAT namespace/API model at `330c223c`: preserved OEM/UTF-16 aliases, scoped collisions/lookup, explicit Windows code pages and late recapture denial; 171 cases/95 native groups/12 headers. [Evidence](.aide/evidence/2026-10-13-fat-namespace/README.md). Actual consumers, larger coverage, extraction, worker/frontend and full 0.1.0 remain open.

- [x] DE-W037 contained FAT reader at `56effc8f`: owned expected-file capture, independently reconstructed regions/receipts and actual process/domain snapshots; 109 cases/96 native groups/15 headers. [Evidence](.aide/evidence/2026-10-13-fat-worker/README.md). Shared command/frontend, larger coverage, extraction and full 0.1.0 remain open.

- [x] DE-W038 bounded FAT image command slice at `57cfd113`: explicit windows/model controls through CLI/stdio/GUI/TUI/shell; 62 cases/97 native groups/17 headers. [Evidence](.aide/evidence/2026-10-13-fat-command/README.md). Larger coverage, retrieval/extraction and full 0.1.0 remain open.

- [x] DE-W039 bounded FAT allocation-window slice at `543826fe`: 34 interval / 44 command cases, 99 native groups / 17 headers; partial windows cannot qualify global allocation or FSInfo counts. [Evidence](.aide/evidence/2026-10-13-fat-window/README.md). Larger coherent traversal, retrieval/extraction and full 0.1.0 remain open.

- [x] 2026-10-13 structure review follow-up: retain existing owners and implemented CLI/TUI/shell names; reconcile review dispositions and correct stale header-count/parser-placement wording. [Assessment](docs/structure-review.md) links exact native evidence and fresh tooling/upstream observations. Composition/test seams, Setup Windows qualification and full product/release remain open.

- [x] DE-W044 bounded retained FAT metadata at `4d3dc0a3`: source-independent exact-byte retrieval,68 command/frontend cases,91 store checks,101 native groups/18 headers and224 tooling passes/two skips. [Evidence](.aide/evidence/2026-10-13-fat-retention/README.md). Current-process only; coherent larger traversal/extraction and full0.1.0 remain open.

- [x] Recheck the structure/release assessment at `f8a3eb84`: 220-file map, existing frontend/core-target/header improvements, synchronized main/dev and current Setup CI limitations. [Current assessment](docs/structure-review.md#current-checkpoint-13-october-2026). Preserve earlier evidence and full 0.1.0 gates; no wholesale source rewrite is justified by the supplied review.
