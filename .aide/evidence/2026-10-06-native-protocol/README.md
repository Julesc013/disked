# Native synchronous protocol evidence

Clean source: `e4cdaeda0281cff9505e09f6c3a19abe5463a403` on local branch `goal/disked-0.1.0`.
Product: `.aide-local/artifacts/DE-W012-e4cdaeda/disked.exe` (373760 bytes).
SHA-256: `sha256:5662ed817469ff2a70d347cddf239e0a9b260715310f489daccaea0b2bae37f3`.

An independent local clone configured, built and passed six native CTest groups,
strict response-schema checks, structural checks and spec manifest verification.
`clean-commands.json` contains the actual commands, working directories, outcomes
and log paths. `clean-results.json` binds the exact source inputs, compiler hash,
configuration, host and artifact. PE headers, direct imports and a real machine
launch are retained. Direct loader imports are KERNEL32.dll only; this is a host
observation, not clean-VM qualification.

Working-tree evidence separately retains 156 spec tests (154 passes, two skipped
symlink cases), 879 structural checks and passive validation of 36 AIDE-shaped
records at the pinned upstream revision. No live worker was launched.

The syntax runner executes 80 canonical vectors and 384 global option-placement
variations, plus exact quantities, literals, diagnostics and static completion.
The JSON/reader/process checks cover hostile encoding, duplicate decoded keys,
limits, framing, request order, flushing, unavailable handlers, output failure and
provider-initialization traps. Test counts are not storage-safety qualification.

See [development review](REVIEW.md) and the
[partial handoff](../../handoffs/DE-W012-synchronous-2026-10-06.json).
DE-W012 remains open for asynchronous admission. Owner acceptance is pending.
The programme continues with DE-W011 under the user's local continuation grant.
