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

There are **324 current source files** at `a1346c4e`: 36 portable, 143 runtime, 68 provider,
63 platform and 14 application files. This includes the private membership collector; its working checks and pending full qualification are below. The longest repository-relative source
path is 62 characters: `source/platform/windows/storage/fat_tree_extraction_worker.cpp`.
The path check finds no case collisions, Windows reserved basenames or trailing
space/dot components. These measurements do not qualify legacy path limits,
build-output paths, every compiler or every filesystem.
[Current source inventory](../.aide/evidence/2026-10-16-ntfs-membership/source-inventory.json) and
[current path checks](../.aide/evidence/2026-10-16-ntfs-membership/path-audit.json) bind these observations;
the earlier assessment remains retained in the 16 October structure evidence.

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
| SR-08: Setup qualification | Earlier candidates failed Windows qualification; the latest observed candidate also failed native Windows qualification. Qualification remains open. See the exact snapshot below. |

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

Private membership source `a1346c4e` is pushed to dev and passes 193 independently
authored supplied-reader cases plus the existing three pure capture/closure/
directory groups. The new files use the existing capture owner and preserve old
native/public forms. The retained fixture error and repair are in the
[working record](../.aide/evidence/2026-10-16-ntfs-membership/working-review.json).
Clean full x64 qualification across 165 groups, 67 headers/imports/tooling and the selected
Win32 supplement are still pending. It has not been promoted to main or accepted
by the owner; the previous reviewed slice below remains integrated.

Filename source `18980169` passes all 164 registered x64 native groups, 247 new
filename/298 unchanged stream cases, 65 headers/C90/thirteen unique executable
import checks and 247 tooling tests (two skips). The private Win32 supplement
passes nine groups/eight headers. [Source/evidence synchronization](../.aide/evidence/2026-10-16-ntfs-names-integration/repository.json)
records verified dev/main writes. [Review](../.aide/evidence/2026-10-16-ntfs-names/REVIEW.md)
records the shared private selector, four actual new files (321 total), preflight
defects and unchanged public/storage authority. Native membership, collation,
namespace/content, full original 0.1.0 and release gates remain.

Directory-command source `6efc9a5b` passes all 163 registered x64 native groups,
100 new/58 bootstrap command checks, 63 headers, strict C90, eleven distinct
executable import closures and 247 tooling tests (two skips). Eight private
Win32 groups/six headers pass; the full Win32 product/new frontends remain
unqualified. [Source/evidence synchronization](../.aide/evidence/2026-10-16-ntfs-directory-command-integration/repository.json)
records verified dev/main writes. [Review](../.aide/evidence/2026-10-16-ntfs-directory-command/REVIEW.md)
retains failed GUI fixture runs and exact original evidence. Public bounded
directory-index inspection is implemented; namespace/membership/collation,
lookup/content and the complete original 0.1.0 remain required.

Owned-directory source `1001d463` passes 235 cases/12 methods on x64 and selected
Win32/WOW64 probes. All-target x64 build, 35 selected groups of 162, 63 C++ headers,
C90/import checks and 244 tooling tests (two skips) pass. Eight Win32 groups/six
headers pass. [Source/evidence synchronization](../.aide/evidence/2026-10-16-ntfs-directory-worker-integration/repository.json)
records verified dev/main writes. [Review](../.aide/evidence/2026-10-16-ntfs-directory-worker/REVIEW.md)
retains exact source, fixture failure and working-receipt limitations. This
qualifies private directory snapshots/workers; frontend, namespace/content and
full original 0.1.0 remain. This is not a full 162-group current-native campaign.

Native directory-file source `4156accf` passes 550 responses/12 methods, an all-target
x64 build, 31 selected groups of 161, 63 headers, strict C90/import checks and 244
tooling tests (two skips). Six private Win32 groups/four headers also pass.
[Source/evidence synchronization](../.aide/evidence/2026-10-16-ntfs-directory-file-integration/repository.json)
records verified dev/main writes. [Review](../.aide/evidence/2026-10-16-ntfs-directory-file/REVIEW.md) retains the
original fixture/selector failures and exact resume provenance. This qualifies
the private synchronous file binding, with worker/frontend admission outstanding.
It is not a full 161-group current-native or full original 0.1.0 qualification.

Source `7bb6153a` passes 227 guarded directory cases, all 160 registered x64 native
groups, 63 C++ headers, strict C90 sources/headers and 244 tooling tests (two skips).
The selected Win32 supplement passes four groups/four headers after a receipt-only
counter correction; the original failure remains.
[Implementing-agent review](../.aide/evidence/2026-10-16-ntfs-directory/REVIEW.md)
supports ordinary source integration. [Verified dev/main synchronization](../.aide/evidence/2026-10-16-ntfs-directory-integration/repository.json)
records the actual repository writes. This does not qualify native directory
file/worker/frontend admission or complete NTFS.

The preceding [INDX review](../.aide/evidence/2026-10-16-ntfs-block/REVIEW.md),
[closure review](../.aide/evidence/2026-10-16-ntfs-closure/REVIEW.md) and
[product-command review](../.aide/evidence/2026-10-16-ntfs-command/REVIEW.md)
remain revision-bound evidence. The [pre-update assessment](../.aide/evidence/2026-10-16-ntfs-directory/structure-review-before-w089.md)
preserves the dated detail; the programme owns current work state.

The read-only Universal Setup snapshot at `2026-10-16T06:51:49.341462+00:00` finds
[draft PR #237](https://github.com/Julesc013/universal-setup/pull/237) open at
`23cf102c`. All seven checks finished: six passed and native Windows failed.
The exact [hosted snapshot](../.aide/evidence/2026-10-16-ntfs-names/hosted-observations-23cf102c.json) and
[failed job](../.aide/evidence/2026-10-16-ntfs-names/setup-38858710758-116835894498-failed.log) retain that result; no local runtime cause or
repair/recovery qualification follows. Earlier `ac19f3ef`/`6869eb32` observations
and failed logs remain retained in DE-W094/DE-W092 evidence. Setup main/dev are
protected and share the same file tree `b836676c`. Both queried
GitHub release collections are empty. DiskEd's inspected source pin remains
`2e64f654`; no upstream branch, pin or settings were changed. These are hosted
observations, not local lifecycle qualification.

The original **all-platform/storage0.1.0 remains unfinished**. Continue tested,
agent-reviewed source integration from dev to main. Release requires the remaining
filesystem/storage/platform implementations and compatibility/safety evidence,
Setup qualification, licensing and actual owner/release authority. No defensible
release date follows from the current evidence. Keep those gates separate from
ordinary source merges; do not reduce0.1.0 to the current prototype.

The first clean `a1346c4e` campaign stopped after 38 passes at the existing
verification-worker admission assertion; 126 groups were not run. The original
assertion omitted actual values, so its failed predicate/cause remains unknown.
The [retained campaign](../.aide/evidence/2026-10-16-ntfs-membership/failed-a1346c4e/observation-summary.json)
and [diagnostic recheck](../.aide/evidence/2026-10-16-ntfs-membership/diagnostic-review.json)
are separate results. Added measurements retain the existing 3..4.5-second window
and expected unknown reply/operation identity. The focused unchanged-binary run
passes 236 checks with 3.134-second admission. Fresh full qualification is required;
no main promotion or complete product/release claim follows from this recheck.

The first `a1271115` campaign also remains failed: 51 groups passed, JSON FAT
extraction returned `request_wait_expired`, and 113 groups were not run. The
retained operation later completed; its bytes and map match the independent
fixture. Two new provider copies took1.24/1.09 seconds; new CLI/JSON admissions
took about0.24 seconds. The unchanged full frontend recheck passes615 checks
and verifies11 copies. These are separate diagnostic results, not full native
qualification or an explanation of the original slow interval. See the
[diagnostic review](../.aide/evidence/2026-10-16-ntfs-membership/extraction-diagnostic-review.json).
No deadline/assertion was relaxed or original destination retried. One bounded
fresh full campaign follows; further unexplained failure requires phase
measurements before another attempt. Main and release gates remain unchanged.
