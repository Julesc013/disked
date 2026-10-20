# DE-W106 preparation: explicit evidence sets

This is a partial development checkpoint. DE-W105 remains current; its native
GUI capture and full qualification gates are open. No dependency, owner, release
or external-campaign acceptance is recorded here.

The comparator now requires a nonempty predeclared observation set before its
adapter controls can pass. It rejects missing and duplicate observations,
unexpected participants/cases/kinds, duplicate declarations and fixture hash or
geometry mismatches. Diagnostic-only records count toward completeness. Invalid
sets retain their original inputs, and GPT comparisons preserve both candidates.

Set completeness does not qualify the underlying evidence. `evidence_status`
remains `unverified`, and `complete_success` remains false until participant,
artifact, preservation and execution checks are implemented. The CLI consumes
the stronger gate. The old WSL campaign remains suspended.

The independent regressions first failed against the unchanged comparator.
The current Windows-host suite runs 23 tests with nine Linux-only skips.
Broader validation passes 253 specification tests with two skips, 210 tooling
tests with one skip, 1,327 structural checks, manifest checks and coverage of
all 327 runtime source files once. These are Python/metadata checks, not native
DiskEd or external-tool runs. Exact outputs are retained in compressed form and
bound by [the validation review](validation-review.json).

Continue with typed participant/code/profile binding, actual raw-artifact and
input-preservation checks, execution outcomes, collector updates and bounded
managed output. Do not unlock a complete-success claim merely by removing the
current fail-closed gate. Current work and authority remain in the programme;
the supplied external status report supplied context rather than authority.

The CLI follow-up passes 29 Windows-host tests with nine Linux-only skips.
It requires explicit participant IDs and managed paths, preserves prior reports,
rejects ambiguous/non-finite JSON, and bounds accepted inputs to 8 MiB each and
16 MiB combined. Reports stream within 64 MiB; a 32-byte test exercises refusal
without producing a large file. The old WSL entrypoint refuses before effects.
These are routing/application bounds, not OS confinement or quota qualification.
The earlier full-suite receipt remains unchanged; see the separate
[CLI review](cli-review.json) for exact follow-up scope and input hashes.
