# Build and run the native development executable

The fake-only Windows executable supports human and JSON/NDJSON build information,
static command discovery, actual host/mode inspection and contextual help. `protocol serve` admits synchronous
build/command and fake-graph requests over stdin/stdout. The compiled fake graph
includes cloned labels, aliases, shared/cyclic layers and denied/stale/unknown
observations. A native console TUI provides screen and linear presentation.
The explicit Win32 GUI exposes the same fake service. DE-W016 adds a self-spawned, reconnectable fake operation. Real storage access and the command shell remain unavailable. The [command contract](../spec/interaction/commands.md)
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
`target.list`, `target.inspect`, `topology.show` and `capability.explain`. The private fake operation profile implements `plan.simulate`, `operation.inspect` and `operation.cancel.request`. Recognizing a storage command's syntax does not
admit its handler. Machine responses never mix human diagnostics with framed JSON.
Exit 0 means a completed request, 2 invalid input/revision or target refusal, 3 unavailable, 4 output/internal failure, 5 accepted asynchronous work and 6 an unknown operation outcome.
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
initialization trap. Essential help/build/discovery and invalid argument tests keep working directories empty. Fake operation tests use an explicitly supplied disposable state directory. These are
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
back; F10 or Ctrl+C exits. No persistent command shell or real storage operations are admitted. Simulation writes only its explicitly selected disposable evidence store.
Small consoles automatically use linear output. Pipes cannot supply TUI input.
The linear view is available for accessibility workflows, but screen-reader
qualification remains unrun. See [terminal behavior](../spec/interaction/terminal-session.md).

Run the native window with `disked gui` or `disked --gui`. An explicit command,
for example `disked --gui target inspect fake:alpha@1`, opens a typed form.
Targets and Commands switch the navigator; Inspect / Open acts on its focused
identity. Review request displays exact escaped parameters and revision. Submit
reviewed is a separate action; editing consumes review. Tab and native button
mnemonics navigate controls. Read-only results remain selectable and scrollable.
The current/proposed area reports no proposed changes until planning exists.

GUI dependencies are loaded only on the explicit GUI application path. Headless
imports still exclude user32/gdi32; host-injected modules may appear in process
observations separately. Tests exercise windows on an inactive private desktop
without switching the user's display. Current-host keyboard, controls, font,
colors and contrast observations are evidence; high-contrast-on, screen-reader,
per-monitor DPI, old Windows and clean-VM qualification remain unrun. No custom
extracted icon is distributed. See [the GUI contract](../spec/interaction/tui-and-gui.md).


## Reconnectable fake operations

Create an empty ordinary local directory for one operation, then run:

```powershell
$state = Join-Path $env:TEMP ('disked-fake-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $state | Out-Null
$receipt = & .\build\windows-bootstrap\Release\disked.exe plan simulate fake:complete --state-dir $state --json | ConvertFrom-Json
& .\build\windows-bootstrap\Release\disked.exe operation inspect $receipt.operation_id --state-dir $state --json
```

Admission returns exit 5 with the operation ID. A later inspect is a separate
completed read; examine its state/outcome/recovery fields. The worker survives
client exit. Repeating the same admission in that directory returns its existing
identity; a changed fixture/build conflicts. Missing or uncertain workers are
never automatically restarted. Keep the three evidence files together; no repair,
cleanup, history migration or event-watch command is supplied.

The compiled fixtures are `fake:complete`, `fake:verification-failure`,
`fake:cancel-checkpoint` and `fake:unknown`. Use `operation cancel <operation_id>
--state-dir <directory>` to request cancellation. The checkpoint fixture gives a
two-second pre-effect window. A request after dispatch may accompany normal
completion; only a worker checkpoint can acknowledge cancellation. The sole
fixture effect is an in-memory counter, separate from ordinary evidence-file
writes. Unknown/corrupt histories return exit 6 and never certify success.

The current implementation rejects network/device/relative paths, reparse
components and nonempty first-admission directories. It uses one worker process,
a 128 MiB process memory budget and a three-second admission wait. Its same-user
file permissions and hash chain are not a sandbox, signature or production
storage journal. See [the bounded contract](../spec/architecture/execution-topology.md).
