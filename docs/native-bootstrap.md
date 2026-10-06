# Build and run the native development executable

The fake-only Windows executable supports human and JSON/NDJSON build information,
static command discovery, actual host/mode inspection and contextual help. `protocol serve` admits synchronous
build/command and fake-graph requests over stdin/stdout. The compiled fake graph
includes cloned labels, aliases, shared/cyclic layers and denied/stale/unknown
observations. A native console TUI provides screen and linear presentation.
The explicit Win32 GUI exposes the same fake service. DE-W016 adds a self-spawned, reconnectable fake operation. DE-W019 adds a bounded explicit command shell. Real storage remains unavailable. The [command contract](../spec/interaction/commands.md)
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
The fake operation commands may return asynchronous or unknown outcomes; ordinary completed reads remain synchronous.

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
back; F10 or Ctrl+C exits. The separate `shell` entrypoint opens a persistent command session; real storage operations remain unavailable. Simulation writes only its explicitly selected disposable evidence store.
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


## Interactive command shell

From a real Windows console, run `disked shell`. Add `--history=session` for
memory-only history (default off), or `--terminal=linear` for streamed records
and one editable prompt row. Pipes and conflicting machine/frontend controls
are refused. Nothing is written for shell history or transcripts.

Type `show fake:alpha@1`, press F9 to review its canonical request, then a fresh
F9 to submit. Enter is deliberately inert. After an error, correct the retained
line at the reported byte/token location. Quotes group literal text; doubled
matching quotes encode a quote. Windows backslashes remain literal. There is no
variable expansion, command chaining, redirection or operating-system shell escape.

Left/Right/Home/End and Backspace/Delete edit Unicode characters. Tab lists
static/cached candidates; arrows choose and a fresh Tab inserts. Up/Down recalls
opted-in history. F2 lists commands, F3 cached targets, F4 clears selection,
F5 refreshes the cached view and F6 switches layout. Selection never supplies an
implicit command operand. `exit`/`quit` follows the same two-F9 review flow;
F10 or Ctrl+C closes immediately without cancelling an admitted fake worker.

The 4 KiB editor, 32-entry/64 KiB history and 64-record/256 KiB transcript have
explicit limits. Secrets annotated in parameter schemas are masked and excluded
from history. Large presentation values show an explicit unavailable marker
without retrying a command. See [the shell contract](../spec/interaction/interactive-shell.md)
for exact grammar, bounds and presentation limits. Console tests use synthetic
input on this Windows host; they do not qualify human usability, screen readers,
other keyboards, remote sessions or historical systems. File-API waiting in fake
operation admission follows the resilience policy below.

## Resilience development (DE-W017, in progress)

GUI, TUI and shell fake-operation calls now use one owned background request
channel. Cached navigation stays available during delayed admission; edited
input, review and newer views survive late replies. A busy channel refuses a
second operation request. Pending is not proof of admission or permission to retry.
Closing a frontend leaves admitted workers independent; incomplete admission may
remain unknown. The most recent earlier GUI/TUI completion is displayed separately.

Cooperating fake workers have an enforced four-process limit in the current
user/Windows session, 128 MiB committed memory per worker and 512 MiB aggregate
job memory. Workers start detached from consoles, with both jobs assigned during
creation. Existing immutable claims never restart automatically when a slot frees.
The actual Windows campaign includes delayed admission, disconnected clients,
a fifth start, memory denial, malformed completion and retained views. Exact
source-bound results belong under `.aide/evidence/2026-10-07-resilience/`.

CLI/stdio fake-operation calls now wait at most four seconds for their owned
callback. Expiry returns `unknown` / `request_wait_expired`; it retains the known
operation ID or the explicit state directory for reconciliation. It never retries
the operation. NDJSON cached reads continue while another file call is refused
until the original callback actually completes. A late completion is not a second
wire response. Standard-output writes wait at most three seconds; a failed channel
ends with exit 4 and does not dispatch queued requests or cancel admitted workers.
Delivered bytes may contain a partial record. Evidence for the injected file wait
and actual pipe backpressure belongs under
`.aide/evidence/2026-10-07-transport-containment/`.

DE-W017 remains active: whole-frontend memory, public event-stream gaps/resnapshots,
full destinations and the combined provider-failure campaign still need evidence.
This slice does not qualify physical storage, older hosts or a security sandbox.
