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

## Review and continuation

The local deliverable requires reproducible recipes/adapters, retained independent
observations and disagreement triage, passing native contract checks, a completed
bounded sanitizer campaign and real positive controls. Required unavailable checks
remain not_run. Record implementing-agent review under the cross-unit grant;
owner acceptance, historical/platform qualification and W024 capture/frontend
integration remain separate. Any production-reader defect requires a regression
and requalification of the affected code before local continuation.
