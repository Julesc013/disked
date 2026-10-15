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

There are **307 current source files**: 31 portable, 131 runtime, 68 provider,
63 platform and 14 application files. This includes the private DE-W084 list decoder; its selected exact-source qualification is recorded below. The longest repository-relative source
path is 62 characters: `source/platform/windows/storage/fat_tree_extraction_worker.cpp`.
The path check finds no case collisions, Windows reserved basenames or trailing
space/dot components. These measurements do not qualify legacy path limits,
build-output paths, every compiler or every filesystem.
[Current source inventory](../.aide/evidence/2026-10-16-ntfs-list/source-inventory.json); the earlier path audit remains retained in the 16 October structure evidence.

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
| SR-08: Setup qualification | The reviewed candidate failed Windows qualification. A newer candidate also fails Windows qualification; qualification remains open. See the exact observation below. |

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

The private list decoder at `65ca67d9` passes 561 protected-byte cases,
24 selected native groups, 59 standalone headers, strict C90 syntax and
244 tooling tests (two skipped). [Exact-source review](../.aide/evidence/2026-10-16-ntfs-list/REVIEW.md).
[Source/evidence integration](../.aide/evidence/2026-10-16-ntfs-list-integration/repository.json)
records the successful dev/main synchronization. This changes no owner or release gate.
It advances the existing portable owner without a tree restructure. It does not
yet join MFT extension records or change the bootstrap-only NTFS command scope.
This is a selected regression campaign; the previous complete campaign remains
bound to its own revision below.

The preceding product source `b985adf2` passes one complete clean-source campaign: 154 native
groups, 59 standalone headers, 244 tooling tests (2 skipped), source/header/
build boundaries, PE/import observations and complete input/context binding.
It adds the owned NTFS bootstrap through the common image-inspection service and
all five frontends. The [source-bound review](../.aide/evidence/2026-10-16-ntfs-command/REVIEW.md)
permits ordinary source integration after metadata/staged-byte closure; actual
repository synchronization is confirmed in the
[integration receipt](../.aide/evidence/2026-10-16-ntfs-command-integration/repository.json). This does not qualify the
complete NTFS filesystem, release or full original storage/platform scope.

The previous acquisition-routing source `813924fa` passed 153 native groups and
was integrated at `c7864fa8`; its [receipt](../.aide/evidence/2026-10-16-acquisition-integration/repository.json)
remains historical evidence. Older failed campaigns remain failures and their
spontaneous latency cause remains unknown.

The previous integrated product checkpoint had a complete 144-group native campaign
at `2cd2e2e1`, 51 standalone headers and 242 tooling tests with two skips.
[Exact-source evidence](../.aide/evidence/2026-10-15-exfat-tree/qualified-2cd2e2e1/summary.json).
The NTFS ordinary-file checkpoint at `777fd71f` passes 73 responses/nine
methods on x64 and isolated x86/WOW64, including actual native offsets above4GiB,
file/ancestor access refusals and release.18 selected x64 groups/five headers/
242 tooling tests(two skips), and two x86 groups/two headers pass. Four launch
samples retain actual process/source/profile evidence. Original NTFS primitives
and the154-case bootstrap also pass. That checkpoint leaves worker/public
transport and the remaining original filesystem/platform scope open.
[Exact source review](../.aide/evidence/2026-10-16-ntfs-file/REVIEW.md).

The owned NTFS reader at `e164f863` passes 106 cases/eight methods, 20 selected
x64 native groups, eight headers and 242 tooling tests/two skips. Four complete
launch samples retain source/frame/process evidence. Actual exited-child
publication, strict parent replay and retention after teardown pass. Public
NTFS frontend admission, complete filesystem interpretation, actual file-symlink
qualification and original platform/storage scope remain open. This campaign
does not qualify x86 or the complete native product suite.
[Owned-reader review](../.aide/evidence/2026-10-16-ntfs-worker/REVIEW.md).

At the retained 16 October observation, both GitHub branches report protection
disabled. The specified required
PR/check policy is still an outstanding governance task; this documentation pass
does not change repository settings or establish that gate.

Universal Setup `main` at `c048f7f1` and `dev` at `2b7a4d01` still have the
same file tree. The comparison reports one synchronization commit and zero
changed files; there is no pending content promotion between those branches.
[Dated branch comparison](../.aide/evidence/2026-10-16-ntfs-list/setup-branches.json).

The latest read-only Universal Setup observation finds
[draft PR #237](https://github.com/Julesc013/universal-setup/pull/237) at `1060e995`.
Six checks pass; `native-windows` fails in
[run 38784925435](https://github.com/Julesc013/universal-setup/actions/runs/38784925435).
Its failed log reports owned SYSTEM fixture failures in source-free interrupted
repair checks and receipt-count mismatches during evidence packaging. The
underlying runtime cause is not established. Both queried GitHub release
collections are empty. These are dated hosted observations, not local Setup
execution or live DiskEd lifecycle qualification.
[Retained observations](../.aide/evidence/2026-10-16-ntfs-list/hosted-observations.json)
and [failed job log](../.aide/evidence/2026-10-16-ntfs-list/setup-38784925435-failed.log).

The original **all-platform/storage 0.1.0 remains unfinished**. Native Windows
interfaces and bounded image work are real progress, but substantial original
storage/platform work, production journal/writer/recovery qualification, live
Setup integration, licensing/provenance and owner acceptance remain. Publication,
signing, installation and physical-storage authority stay separate from a tested
source merge. A smaller preview would need an explicitly agreed scope; it cannot
silently replace the selected 0.1.0 finish line. No evidence-based release date
or completion percentage is available.

Continue original NTFS attribute-list/MFT extension and remaining metadata integration
while retaining the historical preparation/acquisition latency investigation. The
architecture is suitable for continued development. Release readiness must be
earned by exact artifacts, applicable tests and the outstanding gates.
