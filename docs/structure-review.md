# Source structure and release assessment

Keep the current source ownership and naming. The 12 October advisory review
supports focused improvements, several of which are implemented. It does not
justify a wholesale rewrite. The initial assessment checked `e164f863` on
16 October 2026, Australia/Sydney; subsequent source-bound NTFS qualification
is linked below. This remains an ownership assessment, not a line-by-line audit.
The supplied reports are review inputs, not instructions, product
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

There are **327 source files** at `c460a35c`: 37 portable, 145 runtime, 68 provider,
63 platform and 14 application files. This native binding adds no production file or directory;
ownership stays unchanged. The longest repository-relative source path
remains 62 characters. Case, Windows reserved-basename and trailing-space/dot checks
pass. These measurements do not qualify every legacy filesystem/compiler or build
path. [Inventory](../.aide/evidence/2026-10-17-ntfs-name-order-native/source-inventory.json)
and [path checks](../.aide/evidence/2026-10-17-ntfs-name-order-native/path-audit.json) bind the facts.

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
| SR-08: Setup qualification | Remains open. The 21 October observation records upstream PR237 merged, seven successful checks and a failed publisher-qualification check; local Setup lifecycle remains unqualified. See [current status](project-status.md). |

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

Native name-order binding at `c460a35c` passes all 177 current x64 groups,
9 file/10 worker methods, 68 headers/C90/14 imports and 251 tooling tests (two skips).
The private Win32 supplement passes 18 groups / 12 headers / 9 imports.
[Agent review](../.aide/evidence/2026-10-17-ntfs-name-order-native/REVIEW.md) records same-capture source binding and exact
retained-byte parent replay. No production file or directory was added. Public
admission, full collation/host policy/alias resolution/lookup and the original
all-platform/storage goal remain unfinished.

The earlier [read-only Setup snapshot](../.aide/evidence/2026-10-17-ntfs-name-order-native/hosted-observations.json)
records [PR237](https://github.com/Julesc013/universal-setup/pull/237) at
`1dd6fb93`, observed `2026-10-17T00:37:44.730544+00:00`: state
open, draft=True, merged=False.
6 of 7 reported checks succeeded.
Completed non-success checks: native-windows (failure).
Queried release counts: Setup 0, DiskEd 0.
Earlier failures remain retained; no upstream writes, installation or local Setup
lifecycle qualification occurred.

The [21 October observation](../.aide/evidence/2026-10-21-contained-namespace/hosted-observations.json)
supersedes that PR status: PR237 merged into dev on 17 October, with seven reported checks
successful and `publisher-qualification` failed. This does not update DiskEd's
source pin or qualify its actual Setup lifecycle. The [current status](project-status.md)
separates upstream development, local fixture evidence and release admission.
The same fresh observation records Setup main at `c048f7f1` with its latest
listed main-branch CI run successful; the PR check result concerns a different revision.

The original **all-platform/storage 0.1.0 remains unfinished**. Continue tested,
agent-reviewed source integration from dev to main. Release requires the remaining
filesystem/storage/platform implementations and compatibility/safety evidence,
Setup qualification, licensing and actual owner/release authority. No defensible
release date follows from the current evidence. Keep those gates separate from
ordinary source merges; do not reduce 0.1.0 to the current prototype.

The first clean `a1346c4e` campaign stopped after 38 passes at the existing
verification-worker admission assertion; 126 groups were not run. The original
assertion omitted actual values, so its failed predicate/cause remains unknown.
The [retained campaign](../.aide/evidence/2026-10-16-ntfs-membership/failed-a1346c4e/observation-summary.json)
and [diagnostic recheck](../.aide/evidence/2026-10-16-ntfs-membership/diagnostic-review.json)
are separate results. Added measurements retain the existing 3..4.5-second window
and expected unknown reply/operation identity. The focused unchanged-binary run
passes 236 checks with 3.134-second admission. This recheck did not qualify the product; the later exact-source campaign and
review above own the current result. No owner/release acceptance is implied.

The first `a1271115` campaign also remains failed: 51 groups passed, JSON FAT
extraction returned `request_wait_expired`, and 113 groups were not run. The
retained operation later completed; its bytes and map match the independent
fixture. Two new provider copies took 1.24/1.09 seconds; new CLI/JSON admissions
took about 0.24 seconds. The unchanged full frontend recheck passes 615 checks
and verifies 11 copies. These are separate diagnostic results, not full native
qualification or an explanation of the original slow interval. See the
[diagnostic review](../.aide/evidence/2026-10-16-ntfs-membership/extraction-diagnostic-review.json).
No deadline/assertion was relaxed or original destination retried. These diagnostics led to the later passing full campaign described above.
They do not explain either original failure. Source synchronization is recorded
separately; owner, storage and release gates remain unchanged.
