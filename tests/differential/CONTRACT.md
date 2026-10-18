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
