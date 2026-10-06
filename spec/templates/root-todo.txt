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
- [ ] DE-W015–016: implement Win32 adapter and bounded local fake planning/execution.
- [ ] DE-W017: exercise fake hangs, cancellation, stale observations and resource limits.
- [ ] DE-W018: run selected legacy ABI/import/startup probes early and retain failures.
- [ ] DE-W020–035: progress through image readers, explicit Windows observation/acquisition and optional native adapters using exact work prerequisites.
- [ ] DE-W040–043: review recovery and image-only mutation/formatting gates before any executor work.

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
- [ ] DE-W019: implement the bounded persistent command shell after shared command/TUI foundations.
- [ ] Before routine native contributions, activate and verify the owner-selected required PR/check gate on GitHub.
- [ ] At protocol/acquisition/writer gates, qualify typed resources, compatible readers, guarded epochs, immutable-plan receipts and composable recovery properties.

## CLI syntax refinement

- [x] Reconcile flexible option placement, natural aliases and contextual help with current catalogs and docs.
- [x] Define shared syntax equivalence/error cases, preserving unresolved typed storage parameters and unrun native parser status.
- [x] DE-W012 synchronous subset: execute the shared syntax corpus, option permutations, bounded protocol and provider-initialization trap on Windows.
- [ ] Complete/review asynchronous protocol identities and remaining DE-W012 admission gates with DE-W016/017.
- [ ] DE-W019: verify editable error recovery and measure shortcut/completion ergonomics on selected keyboards and terminals.
- [ ] DE-W018/071: qualify actual tokenization/encoding and shared parser semantics for selected constrained targets.
