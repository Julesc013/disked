# Code structure, naming and evolution

Keep the existing ownership tree. The complete current file inventory and each
file's responsibility are in [source-map.md](source-map.md); the canonical rules
are [DE-011](../spec/architecture/repository.md) and
[DE-012](../spec/architecture/languages-and-build.md). A private file's existence
does not qualify a public capability, platform or recovery operation.

| Owner | Responsibility | Typical files |
|---|---|---|
| `source/portable/` | Bounded algorithms over supplied bytes, without native I/O | Checked arithmetic, MBR/EBR/GPT decoding, hashing |
| `source/runtime/` | Shared command, graph, plan, operation and recovery meaning | Command/protocol, session/requests, immutable plans and history inspection |
| `source/providers/` | Concrete backend observations and effects behind runtime ports | Ordinary image files, report files, Windows storage observations |
| `source/platform/` | Native handles, processes, input/output and concrete product hosts | Windows entry, console terminal, Win32 windows, contained workers |
| `source/apps/disked/` | Product composition and frontend interaction | `app.*`, `cli/cli.*`, `shell/shell_model.*`, `tui/tui_model.*`, `gui/gui_model.*` |

`app.*` connects the implementations and selects a frontend. CLI formats one
invocation; shell owns an editable command session; TUI owns text navigation;
GUI owns graphical interaction state. These frontends share the command/action
system. CLI therefore has a folder but does not need an artificial `cli_model`
class. The TUI filename correction has already landed; do not repeat it.

The terminal owns native console input, rendering mechanics, handle lifetime and
mode restoration. Both TUI and shell consume it. Putting it under either frontend
would give a shared mechanism to one consumer. The GUI model similarly stays apart
from actual Win32 controls. Current platform entry/UI hosts intentionally consume
product factories/models; the whole platform tree is not a product-independent
SDK. Shared runtime and portable modules must not import those concrete hosts.

Choose lowercase ownership directories and short descriptive `snake_case` private
filenames. Use `tui_model`, `shell_model` and `gui_model` when the basename needs
context in an editor, include or diagnostic. Keep conventional `main.cpp`, clear
`extent`/`snapshot` concepts and existing `.c`/`.cpp`/`.h` extensions. Do not repeat
every ancestor or add a product prefix to every private file.

Functions should name the action or observation within their scope. A member
`inspect()` is clear inside `GptFixtureRestoration`; a public C entrypoint needs
its admitted project prefix and ABI contract. Keep subsystem namespaces, explicit
units, bounded quantities, ownership/lifetime and distinguishable outcomes. A
boolean must not conflate dispatch, completion, verification and effect certainty.
Do not export STL, exceptions or toolkit/private types as the public C ABI.

Use [.editorconfig](../.editorconfig) for text conventions and
[.clang-format](../.clang-format) for C/C++ formatting on a modern coordinator.
The format was checked with clang-format 19.1.5. Prefer one meaningful statement
per line, explicit branches around state changes, named limits with units and
comments explaining invariants. This establishes policy for new/edited code;
the existing tree has not been declared fully formatter-clean. Keep formatting
changes separate from behavioural changes. Never format historical evidence,
generated material or upstream dependencies to make them look current.

The current source map covers filenames, not dependency correctness or accurate
behaviour descriptions. Build targets should name their actual responsibilities;
JSON-only consumers should not inherit command/protocol/invocation implementations.
Cross-module includes should identify their module, with deliberate usage
requirements. The supplied review reproduced no wrong-header binding, so record
this as enforcement work rather than an existing runtime corruption defect.

Cross-module private headers now use the source namespace, for example
`runtime/command/json.h`, `portable/hash/sha256.h` and
`apps/disked/gui/gui_model.h`. Same-folder sibling includes stay short. CMake
`disked_internal` header file sets follow actual implementation targets, with
explicit owners for header-only ports. Paired headers follow their implementation
sources; no competing header inventory or copied source tree is maintained.
The shared inline Windows file mechanism keeps its per-executable test macros.

`private-header-usage.json` is generated from CMake's owned/exported headers and
direct/interface link properties. The checker requires a source header to be
visible through those compile-usage edges, independently of the build graph.
Private `LINK_ONLY` edges do not export headers. The shared `source/` search root
provides namespace resolution; it is not filesystem or C++ access control.
Only declared compile-only fixture guards use configured definitions; unknown
expressions remain conservative. These are private build checks, not installed
SDK exports or complete preprocessing/ABI/platform qualification.

The private native build now has three small core targets: `disked_json` compiles
the JSON codec, `disked_command` compiles command parsing, protocol handling and
the shell lexer, and `disked_invocation` compiles frontend selection policy.
The latter two depend on JSON independently. Presentation and typed command
adapters declare the command dependency; the product composition declares
invocation. This changes internal linkage, not command IDs or public semantics.

In the pinned Windows Release test lane, `build.boundaries` reads CMake's generated
codemodel and actual quoted headers. It checks forbidden layer crossings, ambiguous
or wrongly cased includes, core source/flag expectations and consumer isolation.
Five generated translation units compile `json.h`, `command.h`, `protocol.h`,
`shell_lexer.h` and `policy.h` individually. Run the normal configure/build/test
presets; retain `build/windows-bootstrap/build-boundaries.json` with evidence.
This checks generated build closure, including transitive/order dependencies;
it is not a direct-link audit or a complete C++ preprocessor. Cross-module include
qualification and the remaining headers still need further work. The checker
derives sources from CMake rather than duplicating the source map.

The GUI/TUI completion identity and view-epoch rule lives in `PendingRequestView`
under existing `presentation/requests.*`; their command-view eligibility rule
lives in `view_command_available` under `presentation/session.*`. Matching
delivery releases UI correlation, not worker/storage state. Keep navigation,
editing and rendering local. Native evidence governs qualification of these
changes. The seven standalone header checks now include `requests.h` and `session.h`.
Likewise, move named command policy out of `app.cpp` when it has its own contract
and consumer. Do not introduce a universal frontend class, another registry, or
arbitrary splits based on line count.

The [planned-growth table](source-map.md#planned-growth-without-a-second-source-tree)
routes all specified storage, platform, frontend, integration and delivery families.
It identifies future owners and gates, not every future class, function or file.
Add concrete files with their implementations and tests. No architecture can
truthfully guarantee that future requirements will never require refactoring.
Good boundaries make a change local and preserve unrelated contracts.

Compatibility is anchored in admitted commands, schemas, SDK interfaces, wire and
durable formats. Private paths and build targets can evolve with source-bound
evidence and updated includes, inputs and ownership maps. Preserve stable IDs and
old evidence at its exact revision; an internal move does not grant compatibility
to an untested target or historical journal reader.

Current work routes through the [programme record](../.aide/programmes/disked-0.1.0.json)
and canonical work definitions. Merge qualification, owner acceptance and release
publication remain separate. The full all-platform/storage 0.1.0 objective is
unchanged; this guide does not redefine it as the current Windows prototype.
