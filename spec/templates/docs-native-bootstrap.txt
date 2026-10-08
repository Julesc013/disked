# Build and run the native development executable

The Windows image/fake prototype executable supports human and JSON/NDJSON build information,
static command discovery, actual host/mode inspection and contextual help. `protocol serve` admits synchronous
build/command and fake-graph requests over stdin/stdout. The compiled fake graph
includes cloned labels, aliases, shared/cyclic layers and denied/stale/unknown
observations. A native console TUI provides screen and linear presentation.
The explicit Win32 GUI exposes the same fake service. DE-W016 adds a self-spawned, reconnectable fake operation. DE-W019 adds a bounded explicit command shell. Physical storage and mutation remain unavailable. The [command contract](../spec/interaction/commands.md)
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
`protocol.serve` are available. The fake observation service also implements
`target.list`, `target.inspect`, `topology.show` and `capability.explain`. The private fake operation profile implements `plan.simulate`, `operation.inspect` and `operation.cancel.request`. Recognizing a storage command's syntax does not
admit its handler. Machine responses never mix human diagnostics with framed JSON.
Exit 0 means a completed request, 2 invalid input/revision or target refusal, 3 unavailable, 4 output/internal or incomplete/changed-capture failure, 5 accepted asynchronous work and 6 an unknown request/operation outcome.
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
back; F10 or Ctrl+C exits. The separate `shell` entrypoint opens a persistent command session; physical storage and mutation remain unavailable. Simulation writes only its explicitly selected disposable evidence store.
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
cleanup or history migration is supplied. The bounded watch extension below
observes this same retained store without changing it.

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

## Resilience development (DE-W017, local review boundary)

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

Failed state-store writes also preserve uncertainty. Once an immutable claim
file exists, a write/flush failure returns unknown with its known operation ID;
the claim is never deleted or replayed. A cancellation flag may have been observed
even if its flush failed, so its receipt says `cancellation_request: unresolved`
until explicit inspection observes the worker's decision. Fault-build tests inject
full, partial and failed-flush writes without filling a host volume. Original
errors, residual bytes and no-replay checks are retained under
`.aide/evidence/2026-10-07-store-failures/`. A complete terminal record describes
observed synthetic truth, not a guarantee that its last flush succeeded.

Valid frontend invocations now join a 256 MiB per-process committed-memory job
before command dispatch. Bounded startup parsing and the Windows loader precede
assignment. System token/SID/DACL setup dynamically loads `advapi32.dll`, including
for essential commands; it does not initialize providers or GUI dependencies.
All cooperating frontends in the current user/Windows session share this memory
ancestor. Worker jobs retain their stricter quotas, and closing a frontend does
not terminate an admitted worker. Stricter host limits remain effective; job
hierarchy conflicts or mismatched named limits produce an explicit unavailable
refusal. No breakaway or host-policy reset is attempted.

Evidence in `.aide/evidence/2026-10-07-frontend-memory/` records actual commitment
denial, a stricter inherited budget, conflicting host hierarchies, initialization
contention, maximum bounded NDJSON requests and repeated GUI/TUI/shell workloads.
It measures this host and workload, not every possible allocation failure or an
aggregate host-memory guarantee. The injected store checks do not qualify a real
full filesystem, physical storage, power-loss persistence, older hosts or a
security sandbox.

The observation coordinator now retains independently validated source fragments,
marks failed refreshes stale and preserves healthy observations. Timeout leaves a
source outstanding; an exact late result can publish only in its own capture.
Superseded and duplicate completions cannot overwrite a newer capture. Eight
private change notices bound retention; an evicted cursor requires a complete
snapshot. Failed allocation cannot consume an update or alter retained snapshots.
The 1,024-identity budget persists even when a source removes its observations.

The separate `disked_capture_campaign` test executable runs four native producers
alongside the healthy fixture: synthetic denial, malformed JSON, a 1,800 ms delayed
result and exception 0xE000D17D. It measures cached input during the 400 ms timeout,
actual exits and process/job identities across stdio, Win32, TUI and shell. Its
per-campaign four-process/256 MiB observer budget is separate from the existing
worker quotas. Internal producer roles and diagnostic reports are absent from the
product. Evidence belongs to `.aide/evidence/2026-10-07-observation-capture/`.

These private source notices remain separate from public operation events.
Other hosts and production observers remain unqualified.

## Bounded fake-operation watch

`disked operation watch <operation_id> --state-dir <directory> --follow-ms 2000`
observes an existing fake operation for at most two seconds of following. It never
starts, cancels or retries that operation. JSON/human and interactive views receive
a bounded result; explicit `--format=ndjson` emits live events and a final response.
A still-running operation returns exit 5, unknown observation exit 6, and a
completed read of terminal state exit 0. Read success does not change an operation's
verification-failed or cancelled outcome.

NDJSON `protocol serve` clients opt in only on `operation.watch` by declaring
`required_features: ["org.disked.fake-operation-events/1"]`. Other requests keep one
response per exchange. Unknown features and that feature on JSON transport or
another command are refused. Reconnect supplies `--after-sequence`, `--after-digest`
and `--worker-epoch` from the last fully validated record; `--snapshot` explicitly
establishes a fresh cursor. Wrong epochs, future cursors and conflicting history
are refused without repairing the store or restarting its worker.

Events preserve exact operation/attempt/worker identities and carry a separate
observer identity. The callback has a finite 64-event/1 MiB queue and never waits
for the client. Frontend-owned output retains its 3 s bound. Callback expiry
retains its occupied slot and seals the old observer queue, so no late frame can
become part of the next request. Disconnect and output failure do not cancel the
worker. Record hashes are integrity checks, not signatures or production recovery
qualification.

The Win32 form pages through up to 16 fields using Previous/Next fields, with two
visible native editors. TUI Tab/BackTab reaches the same fields. Empty optional
fields are omitted; boolean fields accept exact `true` or `false`. Review shows
typed parameters before submission. Watch results cannot overwrite newer cached
views or inert shell input. Detailed contract and bounds are in DE-022; native
process/reader/frontend evidence belongs under
`.aide/evidence/2026-10-07-operation-watch/`.


## Initial raw-file image commands (DE-W024)

The 0.1.0-dev.18 Windows prototype exposes two read-only commands through CLI,
stdio, native GUI, TUI and shell:

```text
disked image inspect generated.img --json
disked table verify generated.img --logical-block-bytes 4096 --json
```

Both require an explicitly named ordinary local raw file. The logical block unit
defaults to 512; 4096 is an explicit interpretation choice, not physical geometry
detection. Relative/drive-absolute paths must satisfy the restricted local profile:
fixed drive, at most 240 UTF-16 units after resolution, no device/network/alternate
stream/reparse/multiple-hardlink source or ambiguous path aliases. A refused
profile is not evidence that the partition map is corrupt. No source modification,
image mounting or output file creation occurs. See the owning [DE-102 contract](../spec/operations/map-verify.md).

The result retains independent map findings and capture identity, coverage and
stability. Complete requested-region observation is exit 0 even for corrupt or
disagreeing maps; this does not certify a healthy image. Missing required bytes or
read failures retain a partial result with exit 4; source admission refusals use
exit 3. Equal sequential reads are not an atomic snapshot or whole-image hash.
The receipt binds the internal full region manifest but exports at most eight
region details and omitted counts. Retained capture retrieval/export is separate.

CLI/stdio wait at most four seconds. Exit 6 means the read outcome is unresolved,
with no durable operation ID or cancellation claim. An executing slot remains
occupied until actual completion, and a late result never adds another stdio
response. GUI/TUI/shell use explicit review and separate submission, preserve
responsive cached views, and keep late results separate. Stdio expected_revision
is refused for these initial commands; fake graph revisions are not file epochs.

Build/test commands above exercise the shared image profile. Native source-bound
evidence and implementing-agent review live under
[the W024 checkpoint](../.aide/evidence/2026-10-08-image-commands/README.md).
Owner acceptance, physical media, image containers, atomic/whole-image acquisition,
other hosts/platforms and storage mutation remain separate work.
