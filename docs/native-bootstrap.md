# Build and run the native development executable

The Windows image/fake prototype executable supports human and JSON/NDJSON build information,
static command discovery, actual host/mode inspection and contextual help. `protocol serve` admits synchronous
build/command and fake-graph requests over stdin/stdout. The compiled fake graph
includes cloned labels, aliases, shared/cyclic layers and denied/stale/unknown
observations. A native console TUI provides screen and linear presentation.
The current dev.33 prototype selects 19 command identities, including recorded
acquisition support export. Earlier versioned development notes below describe
their original scope; current report semantics are in [acquisition-cases.md](acquisition-cases.md).

The explicit Win32 GUI exposes the same fake service. DE-W016 adds a self-spawned, reconnectable fake operation. DE-W019 adds a bounded explicit command shell. Physical storage and table mutation remain unavailable. The [command contract](../spec/interaction/commands.md)
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
The [local artifact checker](artifact-checker.md) compares an independently
inventoried staging payload with its ZIP without extracting or executing entries.
Its completeness result does not qualify or publish a release.

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
back; F10 or Ctrl+C exits. The separate `shell` entrypoint opens a persistent command session; physical storage and table mutation remain unavailable. Simulation writes only its explicitly selected disposable evidence store.
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

DE-W033's private acquisition core and Windows ordinary-file adapter can be built
with the same preset. They are exercised separately from the product command
registry. The dev.21 development product now admits the same ordinary-file adapter through its shared asynchronous paths; the core probe alone does not qualify public execution.
Run the generated-file tests with:

```powershell
python tests/images/test_file_acquisition.py --probe build/windows-bootstrap/Release/file_acquisition_probe.exe --fault build/windows-bootstrap/Release/file_acquisition_fault.exe --root .
```

Only the separately compiled fault probe has interruption controls. Its default
grants are test-driver authority for generated fixtures, not owner acceptance or
product authorization. Map identities, exact code generation, normal sharing,
CREATE_NEW and checkpoint coverage are verified on the tested Windows host.
Flush calls and killed-child recovery do not qualify power-loss survival,
physical backing aliases, real failing media, restore readiness or other OSes.

The private acquisition worker adds actual detached file transfer, exact-definition
grant admission and persistent observation through separate probe processes. It
is not linked into `disked.exe` yet. Its generated-file lifecycle tests are:

```powershell
python tests/images/test_acquisition_worker.py --probe build/windows-bootstrap/Release/acquisition_worker_probe.exe --fault build/windows-bootstrap/Release/acquisition_worker_fault.exe --root .
```

The separately compiled worker fault probe exercises late startup, checkpoint
observer failure and incomplete operation-record writes. Ordinary probes ignore
those controls. The three-second admission wait may expire on an ordinary
worker too; an exact unresolved admission retains its operation ID and requires
reconnect. Tests must verify eventual terminal bytes/map and actual process exit,
without relaunching or counting the timeout as success. Repeated admission never
launches a replacement writer; resume
requires a new empty operation-state directory and a separate exact-definition
grant. Prototype record v2 retains original capture evidence across same-code
resume. Keep v1's original binary/evidence; cross-generation resume is not admitted.
Local component evidence is retained under
[the W033 worker checkpoint](../.aide/evidence/2026-10-09-acquisition-worker/README.md).

A second private probe now carries the canonical `image.acquire` prepare/execute
parameters through the common CLI parser, stdio request dispatcher and frontend
form decoder. Preparation reads metadata; execution separately requires the
exact complete definition digest and four explicit effect grants. Structured
JSON remains bounded data. Run its independent contract/file checks with:

```powershell
python tests/images/test_acquisition_commands.py --probe build/windows-bootstrap/Release/acquisition_command_probe.exe --root .
```

The probe's controlled callbacks verify pre-effect refusal and conservative
post-invocation uncertainty. Its ordinary-file tests check completed bytes/maps,
checkpoint cancellation, new-attempt resume, late admission and a separate
code/state-directory layout. Shared parser/form decoding is not actual GUI/TUI/
shell integration; public admission is qualified separately below. The command
parameter schema is provisional and does not settle a stable public API.

The dev.19 product adds acquisition observation to the existing operation
commands. Explicit `image-op:` identities select the acquisition store;
`fake-op:` selects the fake store. Inspection and checkpoint cancellation use
the same command dispatch as the interactive frontends. CLI/stdio watch exposes
actual verified byte checkpoints, exact cursor replay and explicit snapshots.
NDJSON streaming requires `org.disked.acquisition-operation-events/1`; a reader
first obtains the full definition through inspection to bind the event records.
Run the public observation and independent reader checks with:

```powershell
python tests/images/test_acquisition_operations.py --probe build/windows-bootstrap/Release/acquisition_command_probe.exe --disked build/windows-bootstrap/Release/disked.exe --reader build/windows-bootstrap/Release/watch_probe.exe --root .
```

Acquisition watch batches have a finite one MiB CLI/stdio response bound. The
interactive acquisition-watch request slot selects that same finite response
bound; other handlers retain 64 KiB. The dev.21 product implements ordinary-file
image acquisition with separately reviewed definition and effect grants. These
observers cannot start or restart a copy,
and corrupt or incomplete evidence remains unknown without repair.

The dev.20 checkpoint added schema-owned GUI/TUI phase forms and bounded
structured definitions. At that checkpoint, the private `disked_acquisition_ui_test.exe` composition
connected those forms to the same Windows acquisition adapter used by the command
probe. Its build information labels this test composition explicitly. The dev.21 product integrates the same adapter and
supersedes that separate test composition. Run the model and actual native
review/submission journeys with:

```powershell
python tests/frontend/test_acquisition_forms.py --exe build/windows-bootstrap/Release/disked.exe --product build/windows-bootstrap/Release/disked.exe --gui build/windows-bootstrap/Release/gui_model_probe.exe --tui build/windows-bootstrap/Release/tui_model_probe.exe --root .
```

Those tests create ordinary files, verify metadata preparation has no output
effects, and check separately reviewed GUI/TUI copies against independent byte
and map expectations. Native GUI tests own an inactive desktop; terminal tests
own a hidden console. They do not inspect other applications or change user
desktop settings. The dev.21 integration adds full structured shell definitions
and qualified larger interactive acquisition-watch results. Public ordinary-file
admission uses these shared paths; physical storage and production mutation
remain separate gates.

The dev.21 composition contains a separate ordinary-file acquisition provider
(`provider.image.acquire.raw.prototype/1`) and reports 17 implemented command
identities. Prepare observes metadata and returns the complete definition/digest;
execute requires that exact definition plus four explicit effect grants. It uses
the same executable's detached capability-only worker, reports live-uncoordinated
source consistency and retains original capture identity across verified resume.
No physical devices, elevation, mounts, installation or production journal are
admitted. Schemas/maps/records remain explicitly provisional.

The shell accepts at most 64 KiB/128 tokens for literal structured definitions;
history remains opt-in and capped at 32 entries/64 KiB. Acquisition watch alone
selects a one-MiB response, 4 MiB escaped individual display and 8 MiB GUI composite/
qualified shell transcript. Other response limits remain unchanged. Whole-record
eviction and display failures are visible and never trigger another dispatch.

```powershell
python tests/frontend/test_acquisition_interactive.py --exe build/windows-bootstrap/Release/disked.exe --product build/windows-bootstrap/Release/disked.exe --shell build/windows-bootstrap/Release/shell_model_probe.exe --reader build/windows-bootstrap/Release/watch_probe.exe --root .
```

These tests exercise actual public shell/stdio copies, exact resubmission without
restart, denied role capabilities, checkpoint cancellation and fresh-store resume.
The 64-event watch fixture is deliberately synthetic, expanded only after an
actual worker exited; it qualifies native observer limits, not extra worker
effects or authenticated history. Destination bytes and acquisition maps are
checked independently. Retained evidence remains scoped to the tested Windows
host; W033 and the full DiskEd 0.1.0 programme are tracked separately.

Clean source-bound dev.21 evidence and exact artifact identities are retained in
[the acquisition checkpoint](../.aide/evidence/2026-10-09-acquisition-public/README.md).
The requirement audit separates injected ordinary-file failures from unqualified
physical backing, thin provisioning, failing media and other-platform claims.
One initial execute-review screenshot was frame-only; the original and a separately
verified redraw capture are retained. The shared screenshot heuristic remains a
recorded harness limitation.

The dev.22 composition adds `health.assess` for compiled fake fixtures and now
reports 18 implemented command identities. It routes exact target/revision checks
through the shared frontend service and collects bounded fake field sets using
the private health reducer. Policy-selected `support_report` content is distinct
from the outer routing envelope. See [fake health observations](health-observation.md)
for explicit unknown/unavailable behavior and opt-in disclosure. No native SMART,
self-test, device access, support-file export or reliability claim is admitted;
DE-W032 remains partial.

DE-W040 adds a private proposed binary journal codec and native probe. It is not
linked to disked.exe and supplies no journal/file writer, recovery replay or
production admission. Its independent vectors check exact little-endian fields,
identity/chain binding, all small-frame cuts and single-byte corruptions, strict
producers/compatible observational readers, source faults and finite budgets.

DE-W034 adds a private native case/custody builder and fixture probe, described in
[case evidence](case-evidence.md). It retains immutable collector snapshots,
phase/sequence guards, separate public-field inference and a policy-selected
support chain that never exports original private-content hashes. It is currently
unlinked from the product. Native report-file export and actual acquisition/case
and physical/platform qualification remain open; public `evidence.export` is
unavailable.

```powershell
cmake --build --preset windows-bootstrap --target journal_codec_probe
python tests/journal/test_codec.py --probe build/windows-bootstrap/Release/journal_codec_probe.exe --root .
```

[DE-043](../spec/safety/journal-and-recovery.md) and its private profile describe
the exact framing proposal. A separate `disked_plan_prototype` and
`plan_definition_probe` validate immutable fake-model definition bytes, typed
resource/dependency bindings, composable recovery properties and separate
review/grant/admission/execution receipt data. Python independently calculates
canonical bytes/digests and tests stale bindings, bounded integers, dependency
cycles, permission scope and attempt/worker identities.

```powershell
cmake --build --preset windows-bootstrap --target plan_definition_probe
python tests/journal/test_definitions.py --probe build/windows-bootstrap/Release/plan_definition_probe.exe --root .
```

[DE-042](../spec/safety/planning.md#de-w040-private-immutable-definition-proposal)
owns the private payload proposal. These values are not product commands,
authenticated approvals, proven observations or writer admission. Live append/durability adapters, real flush/effect adapters and physical durability qualification
remain separate work; DE-DEC-004/008 stay proposed. Neither matching receipt data
nor a verified byte prefix authorizes effects.


DE-W040 also provides the separate closed `disked_guarded_model` and native
`guarded_journal_probe`. Explicit fake stable/volatile memory models intention
and completion barriers, resource identity/epoch and checkpoint capture, target
flush/verification, cancellation, worker timeout/exit, client loss, crash fates,
fresh-attempt recovery and retained journal generations. Independent fixtures cut
healthy execution at every action boundary and check that invalid transitions
preserve state. No file/device/process port or authenticated authority exists.

```powershell
cmake --build --preset windows-bootstrap --target guarded_journal_probe
python tests/journal/test_guarded.py --probe build/windows-bootstrap/Release/guarded_journal_probe.exe --root .
```

[DE-043](../spec/safety/journal-and-recovery.md#de-w040-guarded-fake-memory-execution-contract)
and the private profile own the selected fake flush/crash assumptions. The model's
hashed JSON histories are not the binary codec or a production storage ABI. A
complete fake prefix without intention can establish an unstarted step only
under this closed model's assumptions; missing physical journal bytes cannot.
Live append/durability adapters, real durability adapters, independent safety
review and physical power-loss qualification remain unverified. All five prototypes
remain outside the product's dependency closure; DE-W040 is still incomplete.


DE-W040 adds `disked_journal_semantics` and `journal_semantic_probe`, a separate
reader joining binary framing to immutable fake definitions, receipts and typed
event/recovery declarations. It binds independently supplied expected plan/header/
publisher identities, validates canonical payloads and exact references, and keeps
the last accepted projection on rejection or torn input. Independent Python vectors
construct and hash binary records before native evaluation, with matching prefix
controls and count/byte/epoch boundaries.

```powershell
cmake --build --preset windows-bootstrap --target journal_semantic_probe
python tests/journal/test_semantics.py --probe build/windows-bootstrap/Release/journal_semantic_probe.exe --root .
```

[DE-043](../spec/safety/journal-and-recovery.md#de-w040-semantic-binary-journal-declaration-contract)
owns this private proposal. Declared completion/exit/flush is historical input,
never authenticated authority, live quiescence or durable target evidence. Accepted
prefixes still require live reconciliation and never authorize effects, replay or
dependency retirement. The private model-history producer now connects recorded fake frames to binary
fixtures. All five private libraries remain outside the product
link closure; real adapters, independent safety review, physical qualification and
production decisions remain pending.


`model_journal_producer_probe` exercises the private model-history projection. It
records actual fake action proof fields, preserves retained generations and partial
candidate cuts, and returns binary bytes plus semantic inspection. Independent
Python framing/hashing checks the generated bytes and reader prefix controls.
These are in-memory declaration fixtures, without a journal file writer or physical
flush. The original fake JSON tail is preserved separately from the explicit half-
record binary cut. Exact source-bound validation lives in the DE-W040 evidence.

```powershell
cmake --build --preset windows-bootstrap --target model_journal_producer_probe journal_semantic_probe
python tests/journal/test_producer.py --probe build/windows-bootstrap/Release/model_journal_producer_probe.exe --semantic-probe build/windows-bootstrap/Release/journal_semantic_probe.exe --root .
```


`journal.repeated_crash_audit` now exercises repeated failures through actual native
fake-model recovery, checkpoint, cancellation and retained generation histories.
The model preserves the recorded exit epoch of the restored attempt and clears
old intention/proof state when another attempt is admitted. Action cuts and resource
fates are chosen independently; binary histories are compared with Python encoding
and all rejected actions must leave snapshots unchanged. This remains a closed
fixture audit, with no live journal writer or physical durability qualification.

DE-W034 also has a private typed support-file export port and Windows ordinary-file
adapter. It binds exact consent-selected bytes and producer/destination identities,
requires separate effect flags, creates without overwriting and verifies readback.
It remains unlinked from the product; evidence.export remains unavailable. The
adapter's synchronous fixtures do not qualify public native wait containment,
acquisition/custody integration or physical/platform evidence. See
[report-export.md](report-export.md) for its development contract and commands.

The dev.23 composition repairs shared ordinary-file ancestor coordination for
image capture and acquisition. Every ancestor must permit directory list/read
access; inaccessible strong pins refuse instead of falling back to metadata
handles. Every held ancestor generation and normalized path is revalidated,
along with bound source, executable and effect-owned paths. Private prospective
acquisition epochs now bind the full ancestor array. Old maps still require their
original executable generation; this is no cross-generation resume grant.
See [the shared path contract](../spec/catalog/ordinary-file-path-profile.json).
The same helper supplies the private report adapter. Public evidence.export
remains unavailable; the composition still exposes 18 development commands.

The focused native coordination test uses only owned disposable directories:

```powershell
python tests/images/test_parent_pins.py --probe build/windows-bootstrap/Release/file_acquisition_fault.exe --capture-probe build/windows-bootstrap/Release/image_file_capture_probe.exe --root .
```

It checks destination/map rename refusal while the exact worker is alive, and
refusal when metadata access succeeds but stronger directory access is denied.
These host observations do not establish a physical namespace fence, protection
against elevated/external writers, power-loss persistence or other-platform
qualification. The baseline defect observation is retained separately from fixed
qualification in `.aide/evidence/2026-10-09-parent-pins/`.

Dev.24 applies the shared strong directory guard to fake/acquisition worker state
and executable parents. It also retains exact CREATE_NEW facts when later
validation fails: such an admission is unknown and preserves its operation ID and
partial file. No incomplete claim is automatically removed or replayed. Existing
persisted directory identity fields are unchanged; per-session ancestor checks do
not imply cross-session ancestry continuity. Public evidence.export is still
unavailable, and the development composition still has 18 available commands.

The generated-directory test covers both rename/refusal, actual creation-time
changes and metadata-only permission refusal:

```powershell
cmake --build --preset windows-bootstrap --target worker_directory_probe
python tests/operation/test_worker_directory.py --probe build/windows-bootstrap/Release/worker_directory_probe.exe --root .
```

Separate native fake/acquisition fault probes cover validation failure after
actual creation; the product ignores those controls. See
`.aide/evidence/2026-10-09-worker-store/` for source-bound results and limits.

DE-W034 selects the native recorded-acquisition report composition in dev.31.
The exact case/source/effect/store/code contract and actual frontend journey
commands are described in [acquisition-cases.md](acquisition-cases.md). Preparation
and review are inert; execution requires separate grants. Report metadata
inspect/cancel/watch and bounded requests share the existing service, with no
fake fallback or ownership transfer when a frontend closes. Authored public
contracts remain proposed/planned while discovery reports this prototype's
implemented subset. Full case custody/before-after coverage, physical storage,
other platforms, owner acceptance and full DE-W034 remain separate.

The shared GUI capture helper now uses owned-window redraw and measured client
RGB content to reject a frame-only false positive. Visible button-caption
interior checks reject partial caption paint as well. Exact retained images and
actual inventory/review/minimum-window checks are part of
`tests/frontend/test_gui_capture.py`. Repainting preserves inert review; title
bar pixels and DIB alpha do not qualify client content. Clean evidence binds
the selected executable and harness separately. This is not complete visual,
accessibility, DPI or other-platform qualification.

The private acquired-image verifier adds a read-only current-byte observation
under DE-W034. It independently checks the explicit original plan, canonical map
chain/checkpoints/substitutions/seal, current output identities and chunk hashes,
with separate before/after resource checks. No stored path is followed and no
resume, replay, repair, output creation or write port exists. A matching image is
not an authenticated actor, source-preservation or point-in-time acquisition claim.

The synchronous ordinary-file adapter is qualified separately from product
availability and bounded worker containment:

```text
python tests/evidence/test_image_verification.py --probe build/windows-bootstrap/Release/acquired_image_verification_probe.exe --product build/windows-bootstrap/Release/disked.exe --root .
```

Current case/support reports still say image verification was not performed.
Binding the separate verification receipt into case/custody, product worker/watch,
all frontends and platform qualification remains work; no public command is added.

The private immutable image-verification observation binds the original case,
exact raw request and history, verification definition/outcome, code/clocks and
separate before/after case/image resources. Earlier acquisition case claims remain
unchanged. Its typed support projection tests all sixteen disclosure policies and
explicitly reviewed ordinary-file exports:

```text
python tests/evidence/test_image_observation.py --probe build/windows-bootstrap/Release/image_verification_observation_probe.exe --product build/windows-bootstrap/Release/disked.exe --root .
```

The private export review binds the observation/source and selected output effect;
a wrong or inner-only digest grants no write. Recorded matching is distinct from
attachment applicability and present-day state. No resource/customer hashes,
paths or arbitrary diagnostics enter this support artifact. Durable custody,
bounded reader/watch, public command/frontend and platform admission remain work.

Private historical verification collections retain the original raw metadata and
typed verification records in bounded snapshots. Their proposed contract is
`spec/catalog/image-verification-collection-prototype.json`. Private complete
retention requires an extra private-metadata grant; policy-selected support
omits original paths/hashes. Strict reload uses only an explicit selected file
and expected artifact digest. Native save/reload, source changes and record
contradictions need applicable qualification. This adds no image.verify command,
authenticated custody, latest-image authority or stable persisted ABI; product
reader/event/frontend and platform/owner/physical gates remain open.

The private `verification_worker_probe` and separately instrumented
`verification_worker_fault` execute a same-file ordinary-image reader with
explicit case/image/map/store/host/private-metadata grants. The contract in
`spec/catalog/verification-worker-prototype.json` fixes resource/code identities,
finite progress/history bounds and cancellation/retention expectations before
evaluation. Admission waits at most three seconds; unresolved workers retain
their operation and dependencies. Provider quiescence and observed OS exit are
separate. Collection or terminal-record failure preserves the actual verdict.

```text
python tests/evidence/test_verification_worker.py --probe build/windows-bootstrap/Release/verification_worker_probe.exe --fault build/windows-bootstrap/Release/verification_worker_fault.exe --product build/windows-bootstrap/Release/disked.exe --collection build/windows-bootstrap/Release/image_verification_collection_probe.exe --root .
```

The private finite history reader supports a digest-bound cursor. Public
image.verify commands, negotiated events, bounded caller request containment
and GUI/TUI/shell journeys still need implementation and qualification. The
product continues to exclude the native image-verification adapter and exposes
19 available commands. These fixtures use generated ordinary files only.

The `verification_command_probe` and its separate fault executable implement the
provisional shared `image.verify` service with a real owned verification worker.
`spec/catalog/verification-command-prototype.json` fixes expected CLI/form/request
semantics, six grants, strict producer relationships and finite negotiated watch
before evaluation. Observations compare separately reported retained request
bindings; execution never promotes an uncertain reply or attachment to success.

```text
python tests/evidence/test_verification_commands.py --probe build/windows-bootstrap/Release/verification_command_probe.exe --fault build/windows-bootstrap/Release/verification_command_fault.exe --product build/windows-bootstrap/Release/disked.exe --root .
```

Private definitions may exceed public input: retain the 64 KiB request/review
bound. Post-dispatch reply failure keeps unknown outcome and recovery routing.
Observer failure retains the last validated cursor/state without cancelling the
worker. The probe is not a product frontend. Actual product request containment
and CLI/stdio/GUI/TUI/shell integration remain the next gate; the product keeps
19 available commands and excludes the native verification adapter.
