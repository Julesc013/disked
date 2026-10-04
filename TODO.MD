# DiskEd development checklist

Status: proposed amended baseline, awaiting DE-W000 review. This checklist summarizes [canonical work definitions](spec/work/units.json), [decisions](spec/catalog/decisions.json) and the [development plan](docs/development-plan.md); it does not grant execution or record acceptance.

## Specification preparation

- [x] Read and reconcile all 13 supplied design/audit files with their provenance and conflicts retained.
- [x] Update canonical architecture, safety, acquisition, composition, installation, target and delivery contracts.
- [x] Map proposed acceptance scenarios to work without representing them as executed tests.
- [x] Fetch AIDE dev at `5be37bd6510977e6cb2e960859c45b33b048dade` and pin source observations.
- [x] Run local specification/tooling tests and passive AIDE schema validation; retain actual results and skipped checks in the [validation report](spec/reports/validation.json).
- [ ] Review and accept the final DE-W000 amendment, including the proposed `source/` ownership map.

## First implementation

- [ ] DE-W010: authorize and build the native fake-provider executable, with actual build/launch evidence.
- [ ] DE-W011–016: implement shared interface semantics and bounded local fake planning/execution.
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

No DiskEd runtime, provider, recovery, hardware, installer or release test is marked passed by this list. Current local validation evidence is retained with the DE-W000 handoff under `.aide/`.
