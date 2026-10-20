# DE-W023 partition parser campaign contract

This work exercises the private MBR/EBR/GPT readers using generated ordinary
files and independently maintained installed tools. It does not admit a product
image provider or qualify a storage writer. Expected DiskEd findings and the
comparison rules below precede evaluating the campaign.

## Generated corpus

Deterministic recipes create complete or deliberately truncated raw images with
512-byte logical blocks. Include ordinary and extended MBR layouts, EBR cycles,
overlaps, malformed signatures and ranges; GPT primary/backup agreement, valid
disagreement, independent header/array corruption, entry ranges, duplicate IDs,
reserved bits and lossless name edge cases. Preserve input bytes by SHA-256.
Non-512 decoding remains covered by W021/W022; external tools in this initial
campaign are invoked only for their explicitly supported 512-byte file profile.
Large generated images and mutated corpora remain outside ordinary source
history. Recipes, manifests, small reproductions and evidence identify them.

## Differential observations

Run the exact native probes against views taken from each generated image.
Expected status/issue relationships come from DE-032 and independent recipes,
not external-tool output. Retain both GPT candidates and EBR coverage boundaries.

Invoke installed util-linux sfdisk only with explicit JSON/verify observation
commands and the exact synthetic regular file. Invoke GPT fdisk sgdisk only with
pretend/print/verify options. Never invoke either tool without a file argument.
Use an explicitly unprivileged Linux identity. Bound time, memory and output;
retain refusals, crashes and timeouts as observations. Hash the file before and
after every tool invocation. No devices, mounts, installation or repair commands.

Normalize only fields actually reported: label kind, partition slot, first/last
block, type, disk GUID and partition unique identity where available. Do not infer lossless names from
a display string, a full diagnostic set from success exit, or independent GPT
copy verification from a selected table. Compare those projections separately
from raw diagnostic output. Preserve every discrepancy with its fixture and
exact tool/source-package identity. Agreement is not a correctness vote; an
external tool's repair/selection policy never changes DiskEd's expected result.

## Parser fault campaign

Build the unmodified C90 readers with the installed GCC AddressSanitizer and
UndefinedBehaviorSanitizer, with fatal sanitizer findings and branch coverage.
Exercise deterministic seeded mutations of the generated images and their
truncations, plus structured mutations with repaired test-only CRCs so entry
paths remain reachable. Bound image size, entry workspace, EBR visits, iterations
and wall time. Keep the exact failing iteration/input before reporting a failure.
Check input immutability, bounded extents, progress/visit limits and agreement
invariants. Positive controls must demonstrate that sanitizer and campaign
failures cannot silently become passes.

Report actual iteration counts, source/compiler/runtime identities, coverage and
uncovered paths. This is a bounded deterministic mutation campaign with measured
coverage; it is not coverage-guided fuzzing or exhaustive parser qualification.
Coverage-guided tooling can be added independently when its runtime is available.

## Planned evidence-boundary correction (DE-W106)

The historical comparator evaluates the observations supplied to it without
proving a complete expected set. Its current passing-control flag alone is
insufficient. This is a validation gap, not evidence that retained historical
results were incomplete. Before the next campaign, implement these requirements:

- A predeclared campaign manifest lists exact case, participant/reference profile
  and observation-kind tuples, including diagnostic-only calls and optional tools
  selected before execution. Zero expected tuples is not a complete campaign.
- Manifest case names and native/external tuple keys are unique. Reject missing,
  duplicate, unknown and unexpected records before comparison, including tuples
  whose projection is null. Do not collapse duplicates into a dictionary.
- Bind every participant record to the same fixture recipe, initial hash, byte
  length, logical block size and block count. Bind native code/build/probe hashes,
  reference executable/component identities and comparison-contract revision.
  Verify raw-artifact hashes and actual input-preservation/effect receipts.
- Validate required field relationships before normalization. Diagnostic-only
  observations count toward completeness but not fabricated partition projections.
  Optional tools cannot silently disappear after being selected for the campaign.
- Report evidence as complete, incomplete or invalid; report execution separately
  as completed, refused, timed_out, crashed or unavailable; report comparison as
  agreement, disagreement or not_comparable. No complete-success summary is
  permitted for incomplete/invalid evidence, failed controls or required
  unavailable/timed-out/crashed execution. A refusal may satisfy an expected
  observation but cannot satisfy a control that requires a successful projection.
- Preserve all discrepancies. Matching one GPT candidate never resolves conflict.
  Define compared fields and tolerated nondeterminism before evaluation; do not
  normalize away refusal, competing copies, lossless names or permitted effects.

Regressions must include absent observations, duplicates, wrong hashes/geometry,
unknown cases, missing/unidentified participants, changed inputs/raw artifacts,
diagnostic-only observations and a valid complete set with a retained disagreement.
The coordinator must use the validated completeness result in its success gate.

The old WSL coordinator and README currently route generated data into
`.aide-local`; that recipe is suspended. Migrate source, compiler caches, corpora,
logs, process ownership and cleanup together to the existing managed campaign
workspace. Validate path refusal and failure/interruption cleanup before reuse.
The watchdog does not supply a filesystem quota or qualify WSL isolation. Select
an available qualified guest/external worker; no silent host fallback, dependency
installation, budget increase or repeated historical unbounded campaign.

### Initial DE-W106 set-validation slice (unqualified)

The private manifest field `expected_observations` declares unique
`{name, participant, kind}` tuples before collection. `native` identifies the
native participant and its observation kind. External receipt keys identify
their reference participant. Every declared case requires native and reference
tuples. Diagnostic-only calls remain required tuples even with null projections.
Records must match the corpus SHA-256, byte length, logical unit and block count.
Truncated fixtures may contain fewer bytes than the declared block geometry.

This first slice reports `set_status` separately from `evidence_status` and
`complete_success`. Invalid sets retain their original inputs rather than
selecting one duplicate. Historical receipts without a declaration remain
unverified; their candidate comparisons may still be inspected as diagnostics.
Set-only receipts remain unverified. The opt-in binding profile below checks
participant, artifact, preservation and execution relationships before permitting
a complete evidence-packet result. Coordinated collector APIs now emit that
profile; the legacy direct CLIs are suspended. No actual campaign or worker is
qualified by the offline tests.
This neither qualifies DE-W106 nor closes its DE-W105 dependency.

### Provisional finalized-packet bindings

This is private test data, not a public DiskEd protocol or storage ABI. A manifest
with `evidence.schema = org.disked.differential-evidence/1` declares the following
before collection. The caller separately supplies its frozen SHA-256 over sorted,
compact, ASCII JSON; the verifier does not derive the expected snapshot from
returned observations.

- `contract` and `generator` identify retained bytes. The comparison contract
  must equal the current reader's owning contract. The generator hash matches
  the corpus identity. `fixtures` binds every case to its original bytes.
- `participants` maps each selected participant to its role, exact declared
  profile and identity artifact. Profiles name OS/build, architecture, runtime,
  token, original workspace and Windows/POSIX path style. Identity JSON binds
  participant/profile, source revision and inputs, build configuration,
  toolchain/component and executable hashes. Native revisions are exact Git
  identities; unverified upstream reference source remains explicitly unverified.
- Each expected tuple additionally carries `policy`: comparison role
  (`native`, `projection`, `diagnostic`), exact `argv`, relative `input_path`,
  allowed outcomes and timeout. Native probes receive byte views on stdin;
  reference commands include the fixture argument derived from the original
  workspace. The verifier never executes these recorded arguments.

Every receipt and observation binds the expected participant identity hash.
Observations retain executable before/after hashes, `execution` (status, argv,
exit code, elapsed seconds), `input_before` and `input_after` artifacts,
`input_unchanged`, and `raw` stdout/stderr artifacts. Native records also retain
their exact request. UTF-8 display, byte hashes and invalid-byte hex must agree
with raw bytes. The verifier reconstructs native requests, checks recipe-defined
native facts and recomputes projections from retained output. Diagnostic roles
do not invent projections.

Artifact descriptors are `{path, bytes, sha256}`. Paths are relative beneath the
selected finalized packet root; traversal, links, multiple links, changed files
and contradictory descriptors are refused. Each artifact is at most 2 MiB, with
32 MiB of unique payload bytes in memory and 2,048 files in this initial profile.
Identical copies share cached content, but every file is read and checked. Each
pass reads at most 128 MiB, allowing the existing corpus's separate participant
copies without accumulating duplicate payloads in memory. The verifier
rechecks bytes and identities after reading the packet. Participant copies must
have distinct file identities, separate from the canonical fixture. Producers
must retire their jobs and finalize output before verification. These checks do
not establish an atomic snapshot in the presence of an authorized concurrent
writer, nor replace OS-enforced worker confinement.

`evidence_status`, per-observation execution outcomes and `comparison_status`
remain separate. Required timeout, crash or unavailability prevents complete
success. Output exhaustion is recorded as `output_limited` with outcome
`output_limit` and likewise cannot pass execution. A deadline or output failure
remains a failure even if the eventual process exit is zero. A declared refusal
can be a complete observation, but cannot pass a
common control requiring a successful projection. Complete noncontrol
disagreements remain findings, and selecting one GPT candidate never resolves
the native conflict.

The CLI uses `--expected-manifest-sha256` and optionally `--artifact-root` beneath
the managed workspace. A successful consistency check establishes only that the
finalized bytes and declarations agree with the caller's snapshot. Plain hashes
do not authenticate execution, admit the collector/worker, accept this work unit
or qualify a product, platform, provider or release. Actual collector migration,
qualified execution and the DE-W105 dependency remain separate gates.

### Coordinated collectors (private, execution qualification pending)

`observe_native.collect` and `observe_external.collect` accept a caller-frozen
manifest, packet root, measured worker identity, explicit tool paths and an
execution callback. The adapter constructs its fixed native-probe or read-only
sfdisk/sgdisk command and compares it with the declared command. Manifest data
never supplies an executable command on its own. The shared declaration resolver
checks the contract, generator, canonical fixture bytes, identities, policies
and independent participant paths before any invocation. The measured identity
must equal the frozen identity; its workspace is the actual packet root beneath
`DISKED_WORK_ROOT`, outside the repository.

The collector exclusively creates a distinct case/participant copy and its own
collection directory. Existing copies, reports or collection directories cause
refusal. Every call retains a separate before snapshot, the native stdin bytes
where applicable, raw stdout/stderr, actual after-file identity and bytes, and
executable before/after hashes. Malformed native output and non-UTF-8 data remain
evidence. Changing an input or executable stops collection after retaining the
available observations. `collected` means calls were recorded, not that their
execution, native checks, comparisons or worker qualification passed.

The owning qualified runner implements
`execute(argv, cwd, payload, timeout, output_limit)`. It must enforce the selected
process/resource profile and retire its entire process tree before returning
`{outcome, exit_code, elapsed_seconds, stdout, stderr, terminal:true}`. Streams are
exact bytes. Outcomes are `exited`, `timeout`, `output_limit` or `unavailable`.
Positive ordinary tool exits below 256 are recorded as refusals; other nonzero
exits are crashes. Neither can satisfy a native-success requirement. Missing
execution is represented by `unavailable` and a null exit, not a fabricated child.
This port is not an execution-permission flag or a replacement scheduler.

Before dispatch, a bounded receipt records the active call and available
artifacts. Completed calls are checkpointed individually. A callback exception
or interruption preserves the unfinished call, records its known terminal
status and never triggers an automatic retry. The prior receipt and bounded
partial files survive a failed checkpoint. Explicit failed/interrupted or active
receipts cannot pass finalized-packet validation. The outer runner owns cleanup
on success, failure and interruption after compact evidence is collected.

Raw bytes returned by a call are limited to 1 MiB total, artifacts to 2 MiB,
receipts to 8 MiB and all writes by one collector to 64 MiB. This includes repeated
receipt checkpoints. The existing aggregate workspace and OS-enforced caps still
apply across participants. A supplied callback must enforce its output bound
during execution; checking returned bytes does not establish that property.
No native/external campaign is admitted until that worker and the coordinator's
success/cleanup path are exercised. Legacy direct CLIs refuse before effects.

## Windows reference pilot (DE-W107, planned)

Fix four generated cases before execution: valid MBR, valid GPT, damaged primary
GPT and two valid conflicting GPT copies. Use an exact Windows build and declared
sector geometry. Recipe-defined facts, OS-selected layout and UI presentation
remain separate, including the possibility that the reference refuses the input.
The expected set contains documented layout-query and Disk Management UI
observations for each case; declare exact call/interaction steps in a bounded
execution contract before running. API-only completion does not qualify the UI.

Each record binds campaign/case/participant/kind; OS build/architecture and
component/tool hashes or an explicit unavailable identity; code, fixture-generator
and comparison revisions; initial hash/length/geometry; disposable copy identity;
token/privilege, relevant policy and virtual-device presentation; action/request;
raw returned bytes/UI observations/errors and their hashes; actual elapsed time;
before/after media identity and effects; interpretation and result dimensions.
Identify documented fact, observation, inference and unresolved issue separately.
Unavailable identity cannot qualify a complete successful experiment.

Each participant starts with its own copy of the same known bytes. Record changes
caused by attachment, mount, background services or the reference itself. Only
explicitly owned disposable guest media may be presented to Windows; never infer
authority from a disk number. Retain independent byte observations and source
preservation without treating an unchanged hash as proof of acquisition consistency.
All mutation qualification remains at its original operation/recovery gate.

Use the established capped guest workspace and aggregate limits; reserve the
shared desktop before UI work. Retain compact observations and generators, remove
owned attachments/processes/output on every path, and record actual residuals.
No automatic shared-VM restart, checkpoint or compaction. Cache results only by
their actual input/environment/action/contract dependencies. A reviewed contract
and deterministic independent regressions are the deliverable; REA is optional.

## Local review and continuation

The local deliverable requires reproducible recipes/adapters, retained independent
observations and disagreement triage, passing native contract checks, a completed
bounded sanitizer campaign and real positive controls. Required unavailable checks
remain not_run. Record implementing-agent review under the cross-unit grant;
owner acceptance, historical/platform qualification and W024 capture/frontend
integration remain separate. Any production-reader defect requires a regression
and requalification of the affected code before local continuation.
