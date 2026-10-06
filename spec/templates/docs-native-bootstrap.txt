# Build and run the native development executable

The fake-only Windows executable supports human and JSON/NDJSON build information,
static command discovery, actual host/mode inspection and contextual help. `protocol serve` admits synchronous
build/command and fake-graph requests over stdin/stdout. The compiled fake graph
includes cloned labels, aliases, shared/cyclic layers and denied/stale/unknown
observations. A native console TUI provides screen and linear presentation.
There is no real storage access, GUI, shell or asynchronous operation runtime yet. The [command contract](../spec/interaction/commands.md)
and [protocol contract](../spec/interaction/protocol.md) define the current subset.

Use a Git checkout on Windows x64 with CMake 3.27+, Python 3.10+, Git, VS 2022
MSVC **14.44.35207** (compiler **19.44.35228.0**) and SDK **10.0.19041.0** installed.
The preset selects Release, C++14 and static CRT; the build downloads nothing.

```powershell
cmake --preset windows-bootstrap
cmake --build --preset windows-bootstrap
ctest --preset windows-bootstrap
& .\build\windows-bootstrap\Release\disked.exe --help
& .\build\windows-bootstrap\Release\disked.exe build inspect --json
& .\build\windows-bootstrap\Release\disked.exe commands
& .\build\windows-bootstrap\Release\disked.exe mode explain --json
& .\build\windows-bootstrap\Release\disked.exe help part --json
& .\build\windows-bootstrap\Release\disked.exe target list
& .\build\windows-bootstrap\Release\disked.exe target inspect fake:alpha@1 --json
& .\build\windows-bootstrap\Release\disked.exe topology show --json
& .\build\windows-bootstrap\Release\disked.exe capability explain fake:denied@1 partition.resize.plan --json
```

The product is `build/windows-bootstrap/Release/disked.exe`; other test executables
are internal probes. `generated/build-identity.json` records the source closure,
compiler hash and embedded revision/configuration. Dirty builds explicitly report
`source_state=dirty`; only a clean rebuild binds the artifact to the named commit.

Commands remain globally planned while discovery reports the actual composition's
implemented subset. `build.inspect`, `command.list`, `mode.explain` and the transport selector
`protocol.serve` are available. The fake-only service also implements
`target.list`, `target.inspect`, `topology.show` and `capability.explain`. Recognizing a storage command's syntax does not
admit its handler. Machine responses never mix human diagnostics with framed JSON.
Exit 0 means completed, 2 invalid input/revision or target refusal, 3 unavailable and 4 output/internal failure.
The reserved asynchronous outcomes cannot be produced by this synchronous subset.

To use transport, pass `protocol serve --format=json` and provide one UTF-8 request
to EOF, or choose `--format=ndjson` for a bounded sequence of lines. For example:

```json
{"schema":"org.disked.request/1","request_id":"example-1","command":"build.inspect","parameters":{},"required_features":[]}
```

Use a caller that writes UTF-8 bytes; shell text-pipeline encoding differs between
PowerShell versions. Normal CLI commands do not interpret redirected stdin as requests.
The protocol contract specifies limits, correlation and refusal behavior.
The four fake graph commands accept an optional envelope `expected_revision`
from a preceding result; stale revisions are refused without rebasing. Human
graph output uses ASCII JSON escaping; machine output preserves exact UTF-8
metadata. Aliases and row numbers do not select targets. Capacity unknown is
null rather than zero. Capability assessments never authorize execution.
See [the private service contract](../spec/interaction/presentation.md).

Native tests exercise the shared syntax corpus, option-placement permutations,
strict JSON limits, producer/reader compatibility, process output and a provider
initialization trap. Temporary working directories remain empty. These are
application-boundary checks, not a system-call trace or storage qualification.
Historical [DE-W010 evidence](../.aide/evidence/2026-10-06-native-bootstrap/) applies
only to its original human subset; subsequent work retains separate evidence.
Windows 10 x64 build 19045 is the current exercised host. Other platforms, clean
VMs, Explorer/Windows Terminal routing and all storage operations remain unverified.
DE-W011 tests cover direct/detached launches, cmd/PowerShell and an inherited child
in a hidden test-owned console. `mode explain` preserves unknown host facts and
reports why interactive modes are unavailable. Startup observation does not attach, detach, hide, resize or change the console
mode/code page. The interactive TUI temporarily owns input-mode bits and an
alternate screen buffer, with tested restoration on normal exit, Ctrl+C and
caught failure.

Run the terminal interface from a real Windows console:

```powershell
& .\build\windows-bootstrap\Release\disked.exe tui
& .\build\windows-bootstrap\Release\disked.exe --tui --terminal=linear
& .\build\windows-bootstrap\Release\disked.exe --tui target inspect fake:alpha@1
```

Arrows move focus; Enter selects/inspects. F2 opens commands, F3 inventory, F4
clears selection, F5 refreshes the view, F6 switches presentation. Forms use Tab,
Shift+Tab and Backspace; F9 opens review and a fresh F9 submits. Enter/pasted
newlines cannot submit forms. PageUp/PageDown scroll complete data. Escape goes
back; F10 or Ctrl+C exits. No persistent command shell or disk writes are admitted.
Small consoles automatically use linear output. Pipes cannot supply TUI input.
The linear view is available for accessibility workflows, but screen-reader
qualification remains unrun. See [terminal behavior](../spec/interaction/terminal-session.md).
