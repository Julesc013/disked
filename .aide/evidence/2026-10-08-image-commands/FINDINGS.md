# W024 command development findings

The initial fixture runner assumed every corpus file supplied complete geometry.
Its retained log shows the 511-byte MBR capture correctly returned partial coverage
and exit 4. The corrected expectation explicitly includes that truncated recipe.
The next run reused an EBR prefix fixture's declared 256-block geometry for its
40-block raw file. The file contract derives geometry from length, so the
[10,210) extended root is outside [0,40) and no walk is admitted. The new test
asserts that exact independent geometry/range outcome instead of using the
prefix-only expectation. Other declared corpus findings remain unchanged.

The CLI invalid-unit test expected the protocol parameter diagnostic; the existing
argv parser correctly reports invalid_option_value. The test now asserts that
existing diagnostic, exit 2, and an image-open trap remains enabled to prove
refusal precedes I/O. No source-access or parser check was relaxed.

The first isolated TUI journey timed out even though its retained console text
shows Request completed and the image result. The reused small-console observer
read only the first 65,536 padded character cells, truncating the JSON. The new
fixture reads its own complete bounded 240-column/1000-row console. It does not
alter production limits, request deadlines or the response assertions. The
subsequent native command/frontend run passed all 125 recorded cases.

An early structural check caught an unregistered Markdown required-input ID and
a premature buildable composition without current import evidence. Normative
Markdown enters the pack through its stable concept IDs; artifact input IDs use
the registry. The composition stays planned until actual build/import observations
are retained. Structural/generated freshness is rechecked after canonical edits.
The initial contract helper also named a nonexistent storage/images.md path; it
stopped at its path assertion. The actual geometry owner is address-spaces.md;
no competing specification tree was created.


The first full native run passed 39 groups and failed the shared-image group's
post-timeout request assertion. That assertion did not print the returned value,
so its exact typed outcome was not retained. It assumed a 1.8-second sleep proved
completion of the delayed callback. The revised test observes release through
distinct bounded read-only requests, retaining every response; busy remains an
expected refusal until actual completion. It preserves the four-second product
deadline and rejects every non-busy failure. The focused 125-case run then passed.
This is not evidence of a particular kernel stall or a service-safeguard failure.
The original native run and subsequent verification logs remain separate.

After all 40 groups and 171 specification tests passed, source review caught a
runtime import of the concrete file provider, contrary to DE-010. Owned capture
and error values now live in the private inward-facing capture_port.h. The
application wires the actual provider and test-only delay; a separate pure
image-action library links only runtime/portable modules. Build inputs and the
task closure include the port. Full verification is repeated after this ownership
correction before committing the implementation.

An attempted scratch-runner update failed at PowerShell/Python quoting before
editing files. The already-started verifier therefore retained its old 189-input
assertion while the new port made the actual input count 190. The runner update
was then applied as a patch; the original run is allowed to finish, and continuation
requires a completed successful bound-build receipt and verifies all 190 hashes
before running tests. This is a verification-script bookkeeping correction, not
a reason to restart an executing capture/build or loosen an input hash check.

The port verification passed all native/specification tests, then its passive
AIDE export refused a scratch destination already used by the earlier verification.
The continuation uses a fresh export path for this run, verifies the existing
successful test receipts and unchanged input hashes, and completes passive/schema,
manifest and context checks. Existing caches/evidence were preserved; no passed
product test was relabeled or rerun merely for this scratch-directory correction.

Local staging returned a running process handle; a commit attempted before its
completion was refused by Git's existing index lock. The same staging process
was then awaited to its successful exit. No lock was removed and no other Git
process or credential was changed; commit proceeds only after staging completes.
