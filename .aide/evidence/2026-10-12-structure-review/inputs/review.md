# DiskEd source structure and release review

Review date: **12 October 2026 (Melbourne)**.

## Decision

Keep the current source ownership tree. The TUI rename and dedicated CLI folder are already present. Prefer small dependency and responsibility improvements over a wholesale rewrite. Private source filenames are not the same compatibility surface as public command IDs, installed headers, protocols, plans or journals.

## Pinned repositories

- DiskEd main and dev: `af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f`.
- Universal Setup main: `c048f7f1ae2e5922c15a08ee572bdafc29027c63`; dev: `2b7a4d011a61992970601e8c174b5d9d0298a8cd`.
- Universal Setup main/dev content is identical; dev differs by one synchronization merge. No additional content promotion is currently waiting between those two branches.
- Universal Setup draft PR #237: `b6dff645a252f886e2b46ea142d361620b7e0a95`. Run `38221243094` completed with failure in native-windows. The PR records repair.apply deadline failures; subsequent recovery/consumer qualification is not established.
- Both public GitHub release collection queries returned empty lists. This is not a claim that no private artifacts or historical tags exist.

## Scope and limitations

Read-only review through the GitHub connector: source tree, source map, selected implementation files, build rules, work/release descriptions and hosted CI metadata. No repository writes. Native or complete tooling tests were not rerun. Container Git cloning failed because GitHub DNS resolution was unavailable. Retained project test counts are attributed project evidence, not new results from this review. The full 196-file implementation was not audited line-by-line.

## Naming and ownership rules

1. Directories identify ownership; filenames identify responsibilities. Keep `tui/tui_model.*`, `shell/shell_model.*`, and `gui/gui_model.*`.
2. Do not create a `cli_model` merely for visual symmetry. One-shot formatting does not require persistent session state.
3. Keep `main.cpp`, `CMakeLists.txt`, and other conventional names. Qualify sibling-facing headers without repeating every ancestor or adding a product prefix to every private file.
4. Use module-qualified includes and target-scoped include directories. A semantic filename alone does not prevent accidental header selection through transitive search paths.
5. Preserve public identifiers and historical evidence. Internal relocation may change a build digest without changing the product API.
6. Do not pre-create all possible future files. Record responsibility slots, interfaces and admission gates; introduce concrete files with their implementation and tests.

## Current roles

The [repository-owned complete source map](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/docs/source-map.md) is the canonical current inventory. The following is a selected explanatory map focused on the question, not a competing full inventory.

| File | Responsibility | Placement/naming assessment |
|---|---|---|
| [`source/apps/disked/main.cpp`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/apps/disked/main.cpp) | Native wmain entry; delegates to Windows startup. | Keep the conventional basename. |
| [`source/apps/disked/app.h`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/apps/disked/app.h) | Private application entry declaration. | Not a public SDK header. |
| [`source/apps/disked/app.cpp`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/apps/disked/app.cpp) | Composition, service/provider wiring, frontend routing, discovery, request dispatch and prototype test hooks. | Keep the owner; incrementally reduce command-specific policy and test scaffolding in this unit. |
| [`source/apps/disked/command_registry.h`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/apps/disked/command_registry.h) | Private declaration for the product command-registry instance. | Concrete product registry, not another canonical catalog. |
| [`source/apps/disked/command_registry.cpp`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/apps/disked/command_registry.cpp) | Loads generated command descriptors/parameter schemas into the shared registry. | Keep in product composition. |
| [`source/apps/disked/disked.manifest`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/apps/disked/disked.manifest) | Windows product activation/execution manifest. | Product resource, not runtime semantics. |
| [`source/apps/disked/cli/cli.h`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/apps/disked/cli/cli.h) | Declares the human CLI text result and formatting entry. | No artificial CLI model class required. |
| [`source/apps/disked/cli/cli.cpp`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/apps/disked/cli/cli.cpp) | Formats one invocation into an explicit output channel; no native handle writes. | Separate folder is appropriate; retain compact presentation-only ownership. |
| [`source/apps/disked/shell/shell_model.h`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/apps/disked/shell/shell_model.h) | Declares persistent shell editing/session state. | Keep shell_model. |
| [`source/apps/disked/shell/shell_model.cpp`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/apps/disked/shell/shell_model.cpp) | Persistent command editing, history, completion, transcript and result state. | Not an arbitrary OS shell executor; document that distinction. |
| [`source/apps/disked/tui/tui_model.h`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/apps/disked/tui/tui_model.h) | Declares text UI navigation/form/view state and methods. | Rename from model has already landed. |
| [`source/apps/disked/tui/tui_model.cpp`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/apps/disked/tui/tui_model.cpp) | Text navigation, forms, review, results and bounded rendering. | Share only actual common invariants with GUI; keep TUI interaction local. |
| [`source/apps/disked/gui/gui_model.h`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/apps/disked/gui/gui_model.h) | Declares toolkit-neutral GUI interaction state. | Keep directly in gui while it has no toolkit dependency. |
| [`source/apps/disked/gui/gui_model.cpp`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/apps/disked/gui/gui_model.cpp) | Rows, focus, forms, reviewed submission, deferred results and GUI state. | No Win32 window ownership; share demonstrated pending-request and form rules. |
| [`source/platform/windows/entry.cpp`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/platform/windows/entry.cpp) | Windows argument/startup handling and role dispatch. | Concrete host adapter, not a universal entrypoint. |
| [`source/platform/windows/invocation.h`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/platform/windows/invocation.h) | Windows launch-context observation interface. | Different from platform-neutral invocation policy. |
| [`source/platform/windows/invocation.cpp`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/platform/windows/invocation.cpp) | Observes handles, console and launch context. | Report facts; policy remains in runtime. |
| [`source/platform/windows/output.h`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/platform/windows/output.h) | Native standard-stream output interface. | Separate handle effects from human text formatting. |
| [`source/platform/windows/output.cpp`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/platform/windows/output.cpp) | Windows output writing and failed-channel sealing. | Do not move into a frontend just because that frontend calls it. |
| [`source/platform/windows/console/terminal.h`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/platform/windows/console/terminal.h) | Declares Windows text-interface host functions. | Shared by shell and TUI. |
| [`source/platform/windows/console/terminal.cpp`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/platform/windows/console/terminal.cpp) | Native console observation, input translation, event loops, rendering and restoration. | Distinguish reusable OS service from product-specific host loop in dependency policy. |
| [`source/platform/windows/ui/gui.h`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/platform/windows/ui/gui.h) | Declares the concrete Win32 GUI host. | May consume the product GUI factory under current architecture. |
| [`source/platform/windows/ui/gui.cpp`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/platform/windows/ui/gui.cpp) | Win32 controls, events, window lifetime and teardown. | Not the shared GUI model; toolkit-specific expansion only when another implementation exists. |
| [`source/runtime/presentation/text_input.h`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/runtime/presentation/text_input.h) | Shared key/text value types. | Header-only is correct; do not manufacture a .cpp. |
| [`source/runtime/presentation/session.h`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/runtime/presentation/session.h) | Shared frontend session and form/presentation contract declarations. | Runtime owner, not CLI or TUI. |
| [`source/runtime/presentation/session.cpp`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/runtime/presentation/session.cpp) | Shared action/view/selection, form and presentation semantics. | Extend existing abstractions rather than introducing a second interaction framework. |
| [`source/runtime/presentation/requests.h`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/runtime/presentation/requests.h) | Deferred request and completion-channel declarations. | Runtime contract independent of Windows worker handles. |
| [`source/runtime/presentation/requests.cpp`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/runtime/presentation/requests.cpp) | Bounded request/completion/timeout and unresolved-result handling. | Natural home for proven cross-frontend request invariants. |
| [`source/runtime/command/command.h`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/runtime/command/command.h) | Registry/parser/parameter/completion declarations. | Shared by frontends; not owned by one-shot CLI. |
| [`source/runtime/command/command.cpp`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/runtime/command/command.cpp) | Descriptor-owned parsing, registry, validation and completion implementation. | May split by responsibility after focused tests, not by arbitrary line count. |
| [`source/runtime/command/json.h`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/runtime/command/json.h) | Bounded JSON value/codec declarations. | Currently not a public serialization standard. |
| [`source/runtime/command/json.cpp`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/runtime/command/json.cpp) | JSON parser and serializer. | Build target should not misleadingly imply that all command/runtime code is JSON. |
| [`source/runtime/command/protocol.h`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/runtime/command/protocol.h) | Request/response/event and serving declarations. | Shared protocol semantics. |
| [`source/runtime/command/protocol.cpp`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/runtime/command/protocol.cpp) | Envelope validation, framing and stdio serving. | Separate from CLI human formatting and Windows handle mechanics. |
| [`source/runtime/command/shell_lexer.h`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/runtime/command/shell_lexer.h) | Shell-text lexer declaration. | Shared grammar owner; independent of shell UI state. |
| [`source/runtime/command/shell_lexer.cpp`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/runtime/command/shell_lexer.cpp) | Quoting/tokenization and incomplete-input handling. | Do not tokenize already-parsed OS argv a second time. |
| [`source/runtime/invocation/policy.h`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/runtime/invocation/policy.h) | Platform-neutral mode-selection contract. | Consumes observations rather than Windows handles. |
| [`source/runtime/invocation/policy.cpp`](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/source/runtime/invocation/policy.cpp) | CLI/TUI/GUI and output/interaction selection rules. | Private basename policy is sufficiently scoped. |

## Targeted changes

### SR-01 — Explicit TUI filenames and separate CLI owner already exist

Classification: **resolved**.

Do not repeat the rename or create another CLI tree.

### SR-02 — Narrow and accurately name build targets

Classification: **design_recommendation**.

The disked_json target currently compiles json, command, protocol, shell_lexer and invocation policy. Extract target responsibilities incrementally or use an honest encompassing name. Keep exact target qualification.

### SR-03 — Make cross-module includes unambiguous

Classification: **design_recommendation**.

Prefer module-qualified includes and narrow usage requirements. No actual wrong-header binding was reproduced in this review.

### SR-04 — Consolidate shared frontend invariants, not all frontend code

Classification: **observed_duplication**.

tick, availability and portions of form staging repeat across TUI/GUI. Extend existing presentation helpers with regression coverage; retain different navigation/renderers.

### SR-05 — Keep composition distinct from repeated command-specific policy

Classification: **design_recommendation**.

Incrementally derive routing/limits from one reviewed service binding, and move test-only synchronization into test support when warranted. Preserve separation of metadata and execution grants.

### SR-06 — Source-map coverage does not enforce dependencies

Classification: **observed_tool_limit**.

Current checker detects missing, obsolete and repeated links. Add independent header/dependency boundary checks without creating a second manually maintained source inventory.

### SR-07 — Root first-task text is stale

Classification: **observed_documentation_drift**.

Route current work through one live work-state summary; retain historical decisions and pending acceptance independently.

### SR-08 — USK pending maintenance candidate fails hosted qualification

Classification: **release_blocker**.

Fix and qualify actual repair.apply completion, source-free recovery and required consumers before promotion. Do not solve by raising a deadline without cause analysis.

## Structural boundary

```text
CLI / shell / TUI / GUI interaction
             |
    shared application/session actions
             |
 command, graph, planner and operation semantics
             |
     provider-defined ports
             |
 concrete provider + OS host services
```

The composition root may name concrete implementations. Portable/runtime modules should not import concrete product GUI or storage implementations. Current platform/windows contains both reusable host mechanisms and concrete product hosts; classify those explicitly rather than claiming it is one entirely reusable platform library.

## Planned growth

| Future responsibility | Owner rule |
|---|---|
| Additional binary formats | `source/portable/<format>/` decodes supplied data; providers acquire bytes. |
| Plans, admission, recovery, operation state | `source/runtime/<responsibility>/`, behind effect ports. |
| Filesystems, pools, RAID, images, tape, optical and flux backends | `source/providers/<backend>/`; do not flatten different media semantics into ordinary disks. |
| OS handles, process, security, console, native UI APIs | `source/platform/<host>/`; distinguish product hosts from reusable services. |
| Product interactions | `source/apps/disked/<frontend>/`; shared meaning remains in runtime. |
| Optional SDK, plugin and integration surfaces | Only admitted public headers/bindings; no export of every private source header. |
| Setup and release carriers | Product binding under release/tools; pinned Universal Setup remains a separate lifecycle authority. |

## Release assessment

DiskEd has real native interfaces, ordinary-file inspection/acquisition and private restoration work. The latest retained report states 138 restoration cases, 190 original-execution regressions, 81 native groups and 213 tooling passes with two skips, but expressly excludes product writer/recovery admission, physical power-loss qualification and full 0.1.0 completion. The original-code license is still described as pending in README.

Universal Setup has a substantive runtime and CMake SDK candidate. Its integrated main/dev checkpoint does not establish that the pending maintenance changes are correct. PR #237 remains draft following a failing current-head Windows run. Resolve the real lifecycle completion problem and rerun its finite acceptance set before integration and release.

Merge, release qualification and publication are separate acts. A branch being synchronized or a large number of local tests passing does not alone establish release readiness.

## Suggested implementation order

1. Keep the already-landed names and folder ownership; update the stale root work pointer.
2. Add focused include/header and module-dependency checks; improve build target naming/boundaries without changing runtime semantics.
3. Extract only duplicated frontend invariants with before/after native regression evidence.
4. Preserve product/probe separation and finish the current bounded runtime work.
5. Fix Universal Setup maintenance failure before advertising the affected lifecycle as supported.
6. Qualify one finite release composition on exact targets; retain broader product ambitions in later profiles.

## Primary references

- [DiskEd repository policy](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/spec/architecture/repository.md)
- [DiskEd CMake](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/CMakeLists.txt)
- [DiskEd retained restoration evidence](https://github.com/Julesc013/disked/blob/af9f4fe85dfbb818fbe7f65eab8d5bb8a216427f/.aide/evidence/2026-10-12-gpt-restoration/README.md)
- [Universal Setup README](https://github.com/Julesc013/universal-setup/blob/2b7a4d011a61992970601e8c174b5d9d0298a8cd/README.md)
- [Universal Setup PR #237](https://github.com/Julesc013/universal-setup/pull/237)
- [Exact pending-head hosted run](https://github.com/Julesc013/universal-setup/actions/runs/38221243094)
- [CMake usage requirements](https://cmake.org/cmake/help/latest/manual/cmake-buildsystem.7.html)

This report is advisory; it does not amend a repository specification or grant execution, acceptance, signing or publication authority.
