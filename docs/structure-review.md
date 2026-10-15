# Source structure and release assessment

Keep the current source ownership and naming. The 12 October advisory review
supports focused improvements, several of which are implemented. It does not
justify a wholesale rewrite. This assessment checks `dev` at `d473a63f` on
16 October 2026, Australia/Sydney; it is not a line-by-line audit or fresh native
qualification. The supplied reports are review inputs, not instructions, product
acceptance or execution grants.

Use the [complete source map](source-map.md) for every current source file and its
role, [code structure](code-structure.md) for design and style, and
[DE-011](../spec/architecture/repository.md) for canonical ownership rules.
The [programme](../.aide/programmes/disked-0.1.0.json) owns current work state;
this page explains the assessment without maintaining another work graph.

## Names, files and ownership

| Location under `source/` | Responsibility and reason for placement |
|---|---|
| `apps/disked/main.cpp` | Conventional native entrypoint; delegates startup. |
| `apps/disked/app.*` | Product composition, selected services and frontend routing. Its scope extends across all frontends. |
| `apps/disked/cli/cli.*` | Human formatting for one invocation. CLI has its own folder; its compact formatter has no persistent model to justify `cli_model`. |
| `apps/disked/shell/shell_model.*` | Persistent DiskEd command editing, history, completion and transcript. This is not an arbitrary OS shell executor. |
| `apps/disked/tui/tui_model.*` | Text navigation, forms and result state. The rename from `model.*` is already present and matches shell/GUI naming. |
| `apps/disked/gui/gui_model.*` | Graphical interaction state without Win32 window ownership. A toolkit-specific child is unnecessary until it owns actual toolkit-specific code. |
| `runtime/command/` | Shared grammar, descriptors, protocol and JSON interpretation. Every frontend consumes the same command meanings. |
| `runtime/invocation/`, `runtime/presentation/` | Host-neutral mode policy, shared actions/forms and request/view correlation. Individual frontends retain their navigation and rendering. |
| `platform/windows/console/terminal.*` | Native console input, rendering, event loops, handle ownership and mode restoration, shared by shell and TUI. |
| `platform/windows/ui/gui.*` | Concrete Win32 windows, controls, events and lifetime. The host consumes the product model. |
| `platform/windows/invocation.*`, `output.*` | Native launch observations and standard-channel writes; these differ from selection policy and human text formatting. |
| `portable/<format>/` | Bounded interpretation of supplied bytes, with no native I/O. NTFS boot, FILE, attribute and mapping code belongs together here. |
| `runtime/capture/` | Shared observation meaning and bounded orchestration through reader ports. It does not choose a concrete device or OS. |
| `providers/<backend>/` | Concrete byte acquisition, backend observations and effects behind those ports. A current Windows-specific provider does not establish cross-platform support. |

There are **294 current source files**: 30 portable, 127 runtime, 64 provider,
59 platform and 14 application files. The longest repository-relative source
path is 62 characters: `source/platform/windows/storage/fat_tree_extraction_worker.cpp`.
The path check finds no case collisions, Windows reserved basenames or trailing
space/dot components. These measurements do not qualify legacy path limits,
build-output paths, every compiler or every filesystem.
[Observation and exact inventory](../.aide/evidence/2026-10-16-structure-status/observation.json).

Directories name owners; filenames name responsibilities. Short descriptive
`snake_case` names, conventional `main.cpp`, subsystem namespaces and qualified
cross-module includes balance clarity with path length. Headers declare contracts;
implementation files supply behaviour. Header-only value types need no empty
implementation file. No generic `utils/` owner or universal frontend base class is
needed merely for visual symmetry.

Keep functions focused on named actions or observations, with explicit units,
lifetimes, budgets and distinguishable outcomes. Pass dependencies through ports;
validate before effects. Share demonstrated invariants. Split files when different
contracts or lifetimes make review clearer. Apply the existing formatting policy
to edited code without rewriting historical evidence or claiming the entire tree
is formatter-clean.

## Disposition of the supplied review

| Finding | Current disposition and limits |
|---|---|
| SR-01: TUI names and CLI owner | Resolved in the existing tree. No repeat rename or second CLI tree is required. |
| SR-02: misleading JSON target | Separate `disked_json`, `disked_command` and `disked_invocation` targets are implemented and tested. [Build-boundary review](../.aide/evidence/2026-10-12-build-boundaries/REVIEW.md). |
| SR-03: ambiguous includes | Qualified cross-module includes, target-owned headers and generated compile-usage checks are implemented. [Header review](../.aide/evidence/2026-10-13-qualified-headers/REVIEW.md). This is bounded enforcement, not complete preprocessing/ABI qualification; the advisory review reproduced no wrong-header runtime defect. |
| SR-04: repeated frontend invariants | Shared pending-request/view-epoch and command-view eligibility rules are implemented and tested. [Presentation review](../.aide/evidence/2026-10-12-shared-presentation/REVIEW.md). Other form/rendering duplication has not been declared eliminated. |
| SR-05: composition and test seams | Remains a targeted improvement. `app.cpp` still contains command-specific routing, limits and test hooks. Extract a named service binding or test seam with a concrete contract and consumer, preserving one command registry. |
| SR-06: inventory does not enforce dependencies | Independent CMake-derived build/header checks now accompany source-map coverage. They qualify their tested lane, not every target or public SDK. |
| SR-07: stale first-task routing | Root guidance routes through the programme. This pass also makes the canonical start page distinguish an active checkout from an initial archive. |
| SR-08: Setup qualification | The reviewed candidate failed Windows qualification. A newer candidate is still awaiting its Windows result; qualification remains open. See the exact observation below. |

The original 1,043-line follow-up mixed many dated checkpoints with current
guidance. Its [exact pre-consolidation contents](../.aide/evidence/2026-10-16-structure-status/structure-review-before.md)
remain historical evidence at `d473a63f`; none of its failures or receipts is
deleted or reclassified. New status belongs in the programme and linked evidence,
with this assessment revised when its conclusions change.

## Growth and compatibility

The [planned-growth table](source-map.md#planned-growth-without-a-second-source-tree)
routes the specified operations, storage/media families, platforms, GUI toolkits,
broker, journal, SDK, integrations and packaging to owners and admission gates.
It intentionally describes responsibilities instead of inventing every future
filename, helper or class. Create files when an implementation contract needs them.
An exhaustive guessed tree would make later corrections harder without proving
compatibility.

Stable command/schema/requirement IDs and admitted public or durable formats carry
compatibility obligations. Private source paths, classes and build targets can
change with updated references, tested consumers and revision-bound evidence.
C90 algorithms and the current C++14 Windows composition do not qualify DOS,
historical Windows or other hosts. No naming scheme can guarantee zero future
refactoring; useful boundaries keep changes local and preserve unrelated contracts.

## Development integration and release

Remote `dev` is `d473a63f`; remote `main` is `c03c2d5e` at this observation.
Development checkpoints are being pushed. Whole-branch integration is withheld
because DE-W075's exact `11e6f625` campaign passed 144 of 145 native groups and
failed joined-report preparation with `request_wait_expired`. Later test-only
phase traces retained an unjoined 12-second preparation timeout. The cause is
unproven. Do not raise deadlines or repeat an unchanged complete campaign solely
to obtain a pass. Retain the failures, diagnose or repair the cause, run applicable
qualification and perform agent review before promoting the branch.
[Failed campaign and diagnostics](../.aide/evidence/2026-10-15-native-delays/failed-11e6f625/observation-summary.json).

The last integrated product checkpoint has a complete 144-group native campaign
at `2cd2e2e1`, 51 standalone headers and 242 tooling tests with two skips.
[Exact-source evidence](../.aide/evidence/2026-10-15-exfat-tree/qualified-2cd2e2e1/summary.json).
Later NTFS primitives at `6daed9fd` pass 259 attribute, 632 mapping, 1,729 boot and
964 record cases, 14 selected portable groups, one header and 242 tooling tests
with two skips, plus C90/import/context checks. Those are narrower retained
results, not a new complete native campaign or NTFS provider admission.
[Exact NTFS evidence](../.aide/evidence/2026-10-15-ntfs-attributes/qualified-6daed9fd/summary.json).

Both GitHub branches currently report protection disabled. The specified required
PR/check policy is still an outstanding governance task; this documentation pass
does not change repository settings or establish that gate.

Universal Setup [draft PR #237](https://github.com/Julesc013/universal-setup/pull/237)
is at `67fa57c9`. Six checks have succeeded; `native-windows` is still running in
[run 38744081610](https://github.com/Julesc013/universal-setup/actions/runs/38744081610).
Its main/dev file trees are identical, with one synchronization commit difference.
Both projects' GitHub release collection queries return empty lists at the
observation time. This is hosted status, not local Setup execution, an independently
diagnosed fix or live DiskEd lifecycle qualification.
[Retained read-only observation](../.aide/evidence/2026-10-16-structure-status/observation.json).

The original **all-platform/storage 0.1.0 remains unfinished**. Native Windows
interfaces and bounded image work are real progress, but substantial original
storage/platform work, production journal/writer/recovery qualification, live
Setup integration, licensing/provenance and owner acceptance remain. Publication,
signing, installation and physical-storage authority stay separate from a tested
source merge. A smaller preview would need an explicitly agreed scope; it cannot
silently replace the selected 0.1.0 finish line. No evidence-based release date
or completion percentage is available.

Continue coherent NTFS collection through the existing supplied-reader boundary
while retaining the report-preparation issue as an integration blocker. The
architecture is suitable for continued development. Release readiness must be
earned by exact artifacts, applicable tests and the outstanding gates.
