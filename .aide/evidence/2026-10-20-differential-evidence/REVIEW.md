# DE-W106 preparation: evidence sets and finalized packet bindings

This is a partial development checkpoint. DE-W105 remains current; its native
GUI capture and full qualification gates are open. No dependency, owner, release
or external-campaign acceptance is recorded here.

The comparator now requires a nonempty predeclared observation set before its
adapter controls can pass. It rejects missing and duplicate observations,
unexpected participants/cases/kinds, duplicate declarations and fixture hash or
geometry mismatches. Diagnostic-only records count toward completeness. Invalid
sets retain their original inputs, and GPT comparisons preserve both candidates.

Set-only receipts do not qualify the underlying evidence. They remain
`unverified` and cannot yield `complete_success`. The opt-in private finalized
packet checker now verifies bindings against a separately supplied frozen
manifest digest. The old collectors and WSL campaign remain unqualified.

The independent regressions first failed against the unchanged comparator.
The initial set slice ran 23 tests with nine Linux-only skips.
Its broader validation passed 253 specification tests with two skips, 210 tooling
tests with one skip, 1,327 structural checks, manifest checks and coverage of
all 327 runtime source files once. These are Python/metadata checks, not native
DiskEd or external-tool runs. Exact outputs are retained in compressed form and
bound by [the validation review](validation-review.json).

Current work and authority remain in the programme; the supplied external
status report supplied context rather than authority. Historical receipts
remain source-bound; later tests do not retroactively qualify those campaigns.

The CLI follow-up passes 29 Windows-host tests with nine Linux-only skips.
It requires explicit participant IDs and managed paths, preserves prior reports,
rejects ambiguous/non-finite JSON, and bounds accepted inputs to 8 MiB each and
16 MiB combined. Reports stream within 64 MiB; a 32-byte test exercises refusal
without producing a large file. The old WSL entrypoint refuses before effects.
These are routing/application bounds, not OS confinement or quota qualification.
The earlier full-suite receipt remains unchanged; see the separate
[CLI review](cli-review.json) for exact follow-up scope and input hashes.

The finalized-packet follow-up runs 42 Windows-host tests with five Linux-only
skips. Four pure normalization checks now run on Windows after extraction from
the Linux process tests. The new regressions use synthetic packets, not actual
native or external executions. They reject incorrect identities, changed raw
bytes, fixture effects, contradictory requests/projections and invalid paths.
Refusal, timeout, crash and unavailability remain separate. Valid disagreements
and both conflicting GPT candidates are retained.

This checker reads and hashes every artifact, then rechecks it. Identical payloads
may share memory; participant fixture copies still require distinct file
identities. Per-artifact, aggregate memory, file-count and I/O bounds apply.
A successful packet check establishes consistency, not execution authenticity,
worker confinement, platform support, work acceptance or product qualification.
Existing collectors do not yet emit this format.

The current broader pass ran all 253 specification tests (two skips), 211 tooling
tests (one skip) and 42 differential tests (five skips), plus structural,
source-map and manifest checks. Exact bytes and command outputs are in the
[binding review](bindings-review.json) and compressed validation receipt. The
managed validation workspace peaked at 53,760,433 bytes and was removed. The
first binding run's four assertions selected the wrong participant's result;
the corrected test selects by participant/kind and retains both outcomes.
The original failed run remains available.

Continue with collector and coordinator migration, bounded output, complete
failure receipts, qualified managed execution and real controls. DE-W105's
native capture and qualification gates remain open. No main promotion, owner
acceptance, native/external campaign success or release is claimed.
