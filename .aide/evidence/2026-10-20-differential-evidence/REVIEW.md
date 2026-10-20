# DE-W106 preparation: evidence validation and coordinated collectors

This is a partial development checkpoint. DE-W105 remains current and its native
capture/full qualification gates remain open. No dependency, worker, campaign,
owner or release acceptance is recorded here; main remains at its qualified
DE-W104 checkpoint.

Native and reference collector APIs now use the shared declaration resolver and
caller-frozen manifest. Fixed adapter commands must match that manifest, measured
worker identities must match the declarations, and output stays beneath managed
scratch. Collection retains distinct participant copies, independent before
snapshots, actual after bytes/file identities, raw output, native requests and
executable hashes. Existing collection output is preserved. Legacy direct CLIs
and the obsolete WSL coordinator refuse before effects.

An in-progress receipt retains each active call before dispatch and checkpoints
completed observations. Interruptions preserve unfinished calls without retry or
a quiescence claim. Known terminal results, changed input/executable identities,
refusals, unavailable children, timeouts and output exhaustion remain distinct.
A zero final exit cannot erase a deadline/output failure. A collected packet is
not a successful execution or qualified campaign. Explicit unfinished receipts
cannot pass finalized-packet validation.

All 61 current differential tests pass with five Linux-only skips. They use
synthetic runner callbacks and ordinary files, not native or reference-tool
execution. The earlier broader pass at this checkpoint ran 253 specification
tests (two skips), 211 tooling tests (one skip), and 60 differential tests (five
skips), plus 1,327 structural checks, source-map and manifest verification. After
that pass, code review added an extra-native-kind regression, which first proved
that ambiguity could evade a required comparison. The shared resolver now
rejects it; the complete 61-test differential suite reran. Failure receipts also
retain a precise error code and the active call's executable hash. The broader
receipt retains its exact pre-follow-up hashes; it is not relabelled as a later
full-suite run. See [the collector review](collector-review.json).

The initial collector tests exposed different ctime values from Windows path
and handle stat queries for unchanged files. The corrected check compares each
query source with itself and still requires cross-query file identity, size and
mtime agreement, plus matching executable bytes. The failures, numeric
observations and deterministic regression remain retained. No production ACL,
worker restriction, assertion, deadline or budget was weakened.

The broader validation workspace peaked at 53,866,679 bytes and was removed.
Collector writes are bounded, but neither serialization tests nor a caller's
terminal assertion qualifies process-tree ownership, storage confinement or an
OS quota. Coordinator preparation, actual qualified execution and end-to-end
success/failure/interruption cleanup remain open. No product/native capture
retry, physical-media access, main promotion or public release occurred.

Earlier source-bound checkpoints remain in the [set review](validation-review.json),
[CLI review](cli-review.json) and [packet-binding review](bindings-review.json).
Their historical outputs and applicability have not been rewritten. Continue
with frozen-manifest preparation and coordinator integration using the new APIs,
then exercise a genuinely qualified worker and real positive controls.
