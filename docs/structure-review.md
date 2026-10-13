# Source structure and release review follow-up

## Current checkpoint: 13 October 2026

Rechecked at `f8a3eb842b68fe0666d01711ce95b5dbc5a6a70f`. Remote `dev` and
`main` both name that revision. The assessment below is retained at its original
base; its references to unfinished DE-W044 and the then-latest native campaign
describe that earlier checkpoint.

GitHub still reports `main` as unprotected. Repository-side enforcement of the
intended protected-main/check policy remains governance work; this documentation
pass does not change repository settings.

The current source map covers **220 source files**. The frontend names and CLI
folder are already consistent. JSON, command and invocation have distinct build
targets; module-qualified includes, generated header visibility checks and shared
GUI/TUI request invariants are implemented. Remaining composition-policy/test-seam
work is SR-05 below. These facts support keeping the ownership tree and improving
individual responsibilities as needed; they do not establish an optimal design
for every future requirement or complete API/ABI portability.

DE-W044 now has retained, implementing-agent-reviewed results at source
`4d3dc0a3cb1597289926cb6e010c57f7156b285d`: **101 native test groups**, 18
standalone header compilations, 68 capture command/frontend cases and 91 store
checks; the tooling suite ran 226 tests, with 224 passes and two skips. See the
[exact-source evidence](../.aide/evidence/2026-10-13-fat-retention/README.md).
Those native results were audited here rather than rerun. The first full native
campaign failed five groups; retained serial diagnostics and a subsequent full
campaign passed with the same source and criteria. The initial failures remain
in the evidence; their underlying cause has not been established.

This adds bounded retrieval of retained FAT metadata in the current process.
It does not implement file-payload extraction, qualify physical writers or
production recovery, or complete the owner-selected all-platform/storage 0.1.0.
The programme's next work remains coherent larger traversal, extraction and
further platform/storage implementation.

Fresh read-only GitHub checks still find Universal Setup main at `c048f7f1` and
dev at `2b7a4d01`. [Draft PR #237](https://github.com/Julesc013/universal-setup/pull/237)
remains open at `0fc1f90d`, with `native-windows` failing and six checks passing
in [run 38252891691](https://github.com/Julesc013/universal-setup/actions/runs/38252891691).
Both repositories' GitHub release collections are empty. Setup runtime/installation
was not tested in this follow-up.

The authorized `dev` to `main` workflow has already integrated the qualified
checkpoint. A release has a separate finish line: exact candidate composition,
applicable platform/operation evidence, packaging and content-inventory checks,
licensing/provenance, required acceptance and publication authority. There is no
evidence-based date for the complete 0.1.0 scope. A smaller preview requires an
explicitly selected scope and version; branch synchronization does not select it.

## Earlier assessment at 607d68a7

Assessment: 13 October 2026, against local `dev` at
`607d68a7c6edefeea93bf17218c2685e787683e2`. Keep the five source owners and make
changes at demonstrated responsibility boundaries. The supplied 12 October review
describes an earlier revision; its embedded recommendations are advisory material,
not execution authority, acceptance or current test results.

The [complete source map](source-map.md) explains and links every current source
file. The [growth table](source-map.md#planned-growth-without-a-second-source-tree)
assigns the specified future capability families to owners and work gates. The
[coding guide](code-structure.md) explains implementation conventions. These serve
different purposes; this dated assessment does not replace any of them.

## Why these names and directories

| Location | What it owns | Why it belongs there |
|---|---|---|
| `apps/disked/main.cpp` | The native product entry function | `main` is the conventional entry name. It delegates startup; it does not own every command. |
| `apps/disked/app.*` | Composition, selected services and frontend routing | All interfaces enter the application. Calling this unit `cli` would misdescribe its scope. |
| `apps/disked/cli/cli.*` | Human formatting for one invocation | CLI is an interface with its own owner. It presently needs no persistent `cli_model` class. |
| `apps/disked/shell/shell_model.*` | Editing, history, completion and a persistent DiskEd command session | A shell model owns session state. This shell parses DiskEd commands; it is not a general OS command executor. |
| `apps/disked/tui/tui_model.*` | Text navigation, forms and result-view state | The explicit basename matches the shell/GUI models. The old `tui/model.*` names have already been replaced. |
| `apps/disked/gui/gui_model.*` | Host-neutral graphical interaction state | The model contains no Win32 window ownership. There is currently no reason to put it under a `win32` child. |
| `runtime/presentation/` | Shared actions, forms, request correlation and presentation rules | Multiple interfaces need the same meaning; none should own that shared meaning for the others. |
| `runtime/command/` | Descriptor parsing, protocol handling, shell grammar and bounded JSON | Parsing a product command is a runtime contract, independent of a CLI, console or particular storage backend. |
| `runtime/invocation/policy.*` | Frontend/output/interaction selection | Policy consumes host observations. It does not open native handles to infer them. |
| `platform/windows/console/terminal.*` | Console keys, rendering mechanics, event loops and owned mode restoration | Shell and TUI both need this concrete Windows host. Neither frontend owns the console mechanism. |
| `platform/windows/ui/gui.*` | Win32 windows, controls, events and lifetime | Native window APIs differ from the shared GUI model's semantics. |
| `platform/windows/invocation.*`, `output.*` | Native launch observations and standard-stream writes | Handle operations belong to the host. Human text formatting belongs to the CLI. |
| `portable/<format>/` | Checked storage-format algorithms over supplied bytes | Decoding MBR/GPT/FAT does not acquire a file, enumerate a disk or select an OS. |
| `providers/<backend>/` | Concrete byte acquisition, observations and effects behind ports | Backend responsibilities differ from format algorithms and process lifetime. Current image-provider code can be Windows-specific; placement does not assert portability. |

Directories name owners; basenames name responsibilities. Use short, descriptive
names and module-qualified cross-module includes such as
`apps/disked/tui/tui_model.h`. `main.cpp`, `policy.cpp` and `snapshot.cpp` are
reasonable within a clear owner. A repeated basename in different modules is not
ambiguous when its include path and target ownership are explicit.

The current tracked source inventory has 218 files; its longest repository-relative
source path is 57 characters. The follow-up checks case collisions and Windows
reserved path components. These observations do not qualify every legacy
filesystem, build-output path or compiler.

A header declares types, ports or functions; its implementation file supplies
behaviour. Header-only value declarations such as `text_input.h` need no empty
`.cpp`. Private headers are not automatically SDK exports. Functions name actions
or observations within their namespace/type; public C symbols follow their
admitted ABI prefix. Keep byte/sector/epoch units, lifetimes, limits and outcomes
explicit. Avoid broad `common`, `utils` or generic frontend base classes without a
real shared responsibility.

## Disposition of the supplied review

| Finding | Current disposition | Evidence and remaining scope |
|---|---|---|
| SR-01: TUI names and CLI owner | Already resolved | `tui_model.*`, `shell_model.*`, `gui_model.*` and `cli/cli.*` exist. No further rename needed. |
| SR-02: misleading JSON target | Implemented and tested | JSON, command/protocol/lexer and invocation have distinct private targets. [Build-boundary review](../.aide/evidence/2026-10-12-build-boundaries/REVIEW.md). |
| SR-03: include ambiguity | Bounded enforcement implemented and tested | Qualified cross-module includes, target-owned headers and generated compile-usage visibility. [Header review](../.aide/evidence/2026-10-13-qualified-headers/REVIEW.md). No wrong-header runtime defect was demonstrated by the supplied review. |
| SR-04: repeated frontend invariants | Shared request/view rules implemented and tested | Pending identity/view epochs and command-view eligibility now have shared owners. [Presentation review](../.aide/evidence/2026-10-12-shared-presentation/REVIEW.md). This does not assert that all form/rendering duplication has disappeared. |
| SR-05: application composition policy | Follow-up remains | `app.cpp` still contains command-specific routing/limits and test hooks. Extract a named service binding or test seam when its contract and consumers justify it; do not create a second command registry. |
| SR-06: map does not enforce dependencies | Separate checks implemented | Source-map coverage remains inventory-only. CMake-derived build/header checks and negative fixtures independently check the selected native lane. They do not establish complete preprocessing, SDK/ABI or every-platform conformance. |
| SR-07: stale first-task pointer | Resolved | Root `AGENTS.md` routes current work through the programme and owning work record. Historical bootstrap and acceptance records remain historical. |
| SR-08: Setup maintenance qualification | Still an upstream blocker | Fresh read-only GitHub observation is below. No Universal Setup repairs or promotion were performed by this follow-up. |

Historical reports keep their original counts and limitations. This follow-up
corrects stale current-guide counts and the overbroad phrase “a parser belongs in
portable”: storage-byte decoding and command/protocol parsing have different
owners. It does not rewrite old evidence to describe newer tests.

## Growth and compatibility

Plan owners and interfaces now; choose new concrete files when their behaviour is
specified. Before adding a file, identify its responsibility, input/output contract,
resource/lifetime owner, allowed dependencies, target and applicable tests. Add its
source-map explanation, build/context inputs and tests together. Split an existing
unit when distinct contracts, effect ownership, consumers or target requirements
make that useful. Line count or visual symmetry alone is insufficient.

The growth table covers filesystems, journals/recovery, operation planning,
privileged execution, acquisition/evidence, specialized media, pools/shared storage,
historical/current hosts, GUI toolkits, integrations, SDKs and delivery. It is not a
claim that those implementations exist. Listing every future function or creating
all possible folders would freeze guesses without proving compatibility.

Stable commands, schema/requirement/target IDs and admitted public/durable formats
carry compatibility obligations. Private paths, classes and build targets can
evolve with updated references, tested consumers and retained revision-bound
evidence. The current C++14/Win32 composition does not qualify DOS, legacy Windows
or other platforms merely because some algorithms use C90. No truthful design can
promise zero future refactoring or universally optimal filenames.

## Development, branches and releases

The latest retained native campaign is source `543826fe`: **99 native groups**, 17
standalone headers, 34 FAT allocation-window cases and 44 window command cases;
tooling recorded **222 passes and two skips**. Those are
[retained exact-source results](../.aide/evidence/2026-10-13-fat-window/summary.json),
not a fresh native campaign for this documentation follow-up. The executable has
real Windows interfaces and bounded ordinary-file capabilities. Product physical
writers, production recovery and full all-platform/storage **0.1.0 remain unfinished**.

At the initial read-only branch check, remote `dev` was `607d68a7` and `main` was
`f9f85dac`. The difference defines DE-W044 retention/retrieval; its implementation
is unfinished and unqualified. The authorized workflow is to push checkpoints to
`dev` and promote tested, reviewed checkpoints to `main`, without force pushes.
Repository synchronization does not itself accept an implementation or publish a
release. Follow the programme for subsequent branch/work state.

On 13 October, Universal Setup main was `c048f7f1` and dev was `2b7a4d01`.
[Draft PR #237](https://github.com/Julesc013/universal-setup/pull/237) had advanced
to `0fc1f90d`; its [exact-head CI run](https://github.com/Julesc013/universal-setup/actions/runs/38252891691)
still failed `native-windows` while six other jobs succeeded. The failed-job log
reports failure of the owned SYSTEM standard fixture and later receipt-count
errors. These are observed diagnostics; this follow-up did not independently
diagnose the underlying cause or run Setup.
DiskEd's fixture/source-consumer work is not live lifecycle qualification. Both
GitHub release collection queries returned empty lists.

There is no evidence-based release date yet. The full 0.1.0 scope selected by the
owner remains unchanged. A smaller preview would need its own explicit scope.
Release requires exact candidate artifacts, applicable target/operation tests,
packaged consumer and content-inventory checks, honest capability limits, licensing
and provenance, required acceptance and publication authority. A naming change
does not supply these results.

Continue DE-W044 and the existing programme. Preserve the current source owners;
address the remaining composition/test seams during implementation and qualify
each capability against its actual contract.
