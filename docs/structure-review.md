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

There are **325 source files** at `0b67e4c7`: 37 portable,143 runtime,68 provider,
63 platform and14 application files. The supplied NTFS table primitive stays in its portable owner; the native binding
adds no production file or directory. The
longest repository-relative source path remains62 characters. Case,Windows reserved
basename and trailing space/dot checks pass. These measurements do not qualify
every legacy filesystem,compiler or generated build path.
[Inventory](../.aide/evidence/2026-10-17-ntfs-upcase-native/source-inventory.json) and
[path checks](../.aide/evidence/2026-10-17-ntfs-upcase-native/path-audit.json) bind these facts.

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

Native held-file/owned-reader table source `0b67e4c7` passes all 173 registered
x64 groups,434 held-file/274 worker cases,67 headers/C90/14 imports and 249 tooling
tests(two skips). Its private Win32 supplement passes 15 groups/11 headers/9 imports.
[Agent review](../.aide/evidence/2026-10-17-ntfs-upcase-native/REVIEW.md) records exact
source/profile/replay/process scope and retained test corrections. No production
file or directory was added. Public table admission,namespace/lookup/content and
the original all-platform/storage 0.1.0 remain incomplete.

Retained NTFS table source `b613ccae` passes all171 registered x64 groups,158 new
capture cases,67 headers/C90/14 imports and 249 tooling tests(two skips). Its private
Win32 supplement passes nine groups/five headers/four imports. [Agent review](../.aide/evidence/2026-10-17-ntfs-upcase-capture/REVIEW.md)
records exact table/context/reference/reread scope. No native table source,worker,
frontend,namespace or lookup admission follows; original0.1.0 remains incomplete.

Private NTFS table source `ff74ccae` passes21/170 selected x64 groups,327680
mapping observations,2520 comparisons and78 guard cases, plus67 headers/C90/four
imports and 249 tooling tests(two skips). Both isolated Win32 groups/two C+C++
headers pass. [Agent review](../.aide/evidence/2026-10-17-ntfs-upcase/REVIEW.md)
records the complete scope. This adds no command or namespace/lookup admission.
The full current suite,other platforms and all original0.1.0 remain unqualified.

Common membership command `01feae81` passes all 53 selected x64 groups of
168 registered, 126 new command/frontend cases, 67 headers/C90/13 imports
and 249 tooling tests (two skips). [Review](../.aide/evidence/2026-10-16-ntfs-membership-command/REVIEW.md)
supports source integration after metadata closure. No production files or
directories were added; the ownership assessment remains. No fresh Win32 or
other-host qualification was run. Complete namespace/collation/lookup/content,
all original platforms/storage, owner acceptance and release gates remain.

The preceding private worker results below retain their exact earlier scope.

Owned membership reader `06b63a89` passes all 34 selected x64 groups of 167
registered, 310 new worker cases, 67 header checks/C90/13 executable imports
and 247 tooling tests (two skips). The private Win32 supplement passes twelve
groups/ten headers/seven executables. [Review](../.aide/evidence/2026-10-16-ntfs-membership-worker/REVIEW.md)
supports source integration after metadata closure; the programme owns actual
Git state. Public admission is qualified separately by DE-W098 above. Earlier unexplained
failures and native file-symlink limitations remain retained and unresolved.

Held-file correspondence at `c1511f80` passes the predefined 31/166 affected
x64 groups,496 new cases,67 headers/C90/13 imports and 247 tooling tests (two
skips), plus eleven private Win32 groups/ten headers/seven executables.
[Review](../.aide/evidence/2026-10-16-ntfs-membership-file/REVIEW.md) supports source integration after metadata
closure. At that source revision, worker/public membership admission and all original release requirements
remain; the older full-suite observations below retain their exact revisions.

Private membership source `a1271115` passes all 165 x64 native groups,193
membership/247 filename/298 stream cases,67 headers/C90/thirteen imports and 247
tooling tests (two skips). The selected Win32 supplement passes ten groups/ten
headers/seven executables. [Source/evidence synchronization](../.aide/evidence/2026-10-16-ntfs-membership-integration/repository.json)
records verified dev/main writes. [Review](../.aide/evidence/2026-10-16-ntfs-membership/REVIEW.md)
supports source integration after metadata closure; it does not grant owner
acceptance, native membership admission or release qualification. The original
fixture failure remains retained. The programme owns subsequent work state.

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

The [read-only Setup snapshot](../.aide/evidence/2026-10-17-ntfs-upcase-native/hosted-observations.json)
records draft/open/unmerged [PR237](https://github.com/Julesc013/universal-setup/pull/237)
at `2d6ebd6e`, observed `2026-10-16T18:15:05.145169+00:00`. Of the
7 reported checks,6 succeeded,0
were running and0 queued. Completed non-success conclusions remain
in the exact observation. Earlier failed candidates are retained. Both queried
release collections are empty. No upstream writes,installation or local Setup
lifecycle qualification were performed.

The original **all-platform/storage 0.1.0 remains unfinished**. Continue tested,
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
