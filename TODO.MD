# DiskEd development checklist

Status: proposed baseline with scoped DE-W000 review and a native DE-W010 bootstrap; owner acceptance remains pending. This checklist summarizes [canonical work definitions](spec/work/units.json), [decisions](spec/catalog/decisions.json) and the [development plan](docs/development-plan.md); it does not grant execution or record acceptance.

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

## Delivery and maintenance

- [ ] Resolve original-code licensing before redistribution; review third-party rights independently.
- [ ] DE-W060/062: qualify deployment profiles, finite carriers and one servicing owner per installation.
- [ ] DE-W063: implement independently staged nonempty artifact verification before a release candidate.
- [ ] DE-W061: validate live AIDE import and worker boundaries in a separately authorized disposable environment.
- [ ] Review AIDE roughly weekly; next review **2026-10-11**. Update exact pins and evidence until a stable release is reviewed and qualified. No automatic schedule is configured.
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
- [ ] Strengthen the shared GUI screenshot helper to reject frame-only captures; the separate redraw-verified execution review and original failed frame are retained.
- [ ] DE-W040 active: proposed binary framing codec and independent native byte/corruption/torn-tail/stream-budget tests implemented. Immutable fake-model definitions, separate data-bound receipts and composable recovery properties are proposed with an independent native fixture suite. Closed guarded fake-memory transitions, crash/fault recovery and epoch/dependency checks now have a native fixture suite. A private semantic binary reader now checks immutable payloads, receipt references, event/capture order and recovery declarations against independent native fixtures. Integrate the guarded model event producer and review format/durability assumptions. No production writer admission while DE-DEC-004 remains unresolved.
