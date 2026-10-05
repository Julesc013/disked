# Development readiness and delivery plan

The amended baseline is **proposed and awaiting review**. The specification tools and the bounded DE-W010 native bootstrap work locally; there is no admitted storage provider or qualified product target. See the [native build guide](native-bootstrap.md) for the exact implemented surface. The [amendment review](../spec/roadmap/amendment-review.md) records conflicts and deferred scope. [Root TODO](../TODO.MD) is the short checklist; [work definitions](../spec/work/units.json) own dependencies, deliverables and acceptance criteria.

## Start development in bounded slices

| Work | Concrete result | Boundary |
|---|---|---|
| DE-W000 | Review the amended baseline, source layout and scoped decisions | Final content remains unaccepted until recorded review; tool success is separate. |
| DE-W010 | One native executable with a fake provider, build identity, static command registry and actual build/launch evidence | No physical storage access; create only source directories needed by code. |
| DE-W011–016 | Common CLI/machine/TUI/Win32 semantics, graph, plans and local fake execution | Real frontend and process evidence, with unknown and denied results preserved. |
| DE-W017 | Fake hangs, bounded queues, cancellation races, stale results, frontend loss and worker exhaustion | Failure drills before expanding storage authority. |
| DE-W018 | Tiny compile/import/launch probes for selected legacy profiles | Early architectural feedback; no full product or broad compatibility certification. |
| DE-W020–034 | Read-only image/format readers, Windows observations and coherent acquisition contracts | Follow each unit's exact prerequisites and scoped storage grant. |
| DE-W035 | Thin read-only native host adapter prototype | Fixture hosts first; real registration requires separately authorized installation work. |
| DE-W040–043 | Recovery, offline preparation and independently verified disposable-image mutations/formatting | Journal/recovery decisions and image-only authority precede execution. |
| DE-W060/062/063 | Managed delivery, finite carrier/owner contract and independently staged artifact checks | Portable use remains viable; no signing, publishing or claimed upstream integration here. |
| DE-W080/090 | Broader target/operation qualification and a scoped release | License, provenance, exact target evidence and release authorization remain required. |

These are work groups, not new IDs or a second dependency graph. Run `python spec/tools/specctl.py next` for current dependency readiness. A dependency-ready result is not an execution grant. The current explicit user request authorizes scoped baseline review and DE-W010 fake-only development. The retained baseline review records that grant separately from the still-pending acceptance ledger; `next` therefore continues to show the unaccepted W000 dependency.

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

DE-W012 now includes flexible placement of complete option/value groups, contextual help, natural registered command forms and shared native parser conformance cases. DE-W019 adds editable syntax-error recovery and measured typing/completion usability. Catalog/schema checks and expected-result definitions are local preparation; native argv execution is still unrun. The [command experience](command-experience.md) and [canonical grammar](../spec/interaction/commands.md) explain the boundaries. Existing architecture and storage-admission stages remain intact.
