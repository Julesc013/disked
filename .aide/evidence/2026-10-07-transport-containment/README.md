# DE-W017 transport containment checkpoint

Source `a30313c09f4ba8de5770fea041ae1c71db015f55`; work base `37d69d2fdcaa9f4bc615b7346322ff9daeec4487`. The fake-only development executable is
version 0.1.0-dev.10 at `.aide-local/artifacts/DE-W017-transport-a30313c0/disked.exe`, 827904 bytes,
`sha256:fbe9081ced2dec0fed273f5f51c02ea99975c0251eb3b1ecc7676c57be6c3954`. Exact clean clone/build/test/launch commands, source inputs,
host and PE/dependency/import observations are in `reproduction-a30313c0/`.
DE-W017 remains active and partial; this is not a release or owner acceptance.

The clean checkout passes all 25 native CTest groups. The working specification
suite ran 169 tests (167 passed, two existing symlink-privilege skips). Structural
validation passed 900 checks, generated projections match, and the manifest
verifies in the clean clone. Actual protocol/fake-operation producer-schema checks
pass, including 12 retained new transport failure observations.
Passive AIDE validation covers 36 records at the unchanged pin; no live AIDE run.

CLI/stdio file callbacks now have a four-second frontend wait. The clean injected
6.5-second file-boundary probes returned unknown after
4.040, 4.022, 4.015 seconds. Known operation IDs and the
explicit state store remain available for reconciliation. A busy NDJSON channel
refuses another file call while serving cached observations. The next file request
consumes an actually completed late reply locally, freeing the slot without an
unsolicited response. Explicit same-store reconciliation observes the original
operation and one effect.

Standard-output writes have a three-second wait and one-MiB cap. The actual
undrained-pipe case exited 4 after 3.034 seconds. Readers
that resume within budget receive exact complete bytes; readers that stop after
a prefix receive no replacement frame or diagnostic. Human output is also bounded.
When a large response fails after admission, queued requests remain undispatched.
The admitted worker was still running after the frontend exited and subsequently
completed with one synthetic effect (frontend duration 6.054s).
Output failure is not cancellation, rollback, reader acknowledgement or durable
file flushing. The Windows writer retains its own handle/buffer until completion.

`INITIAL-FINDINGS.md` and initial JSON retain the prior wait beyond 4.5 seconds and the
buffered test-reader failure. Correcting the fixture to read exactly 128 kernel
bytes did not change the production deadline or expected outcome.

Only non-elevated BLACKGLASS-WIN1\Jules on Windows 10 x64 build19045 is exercised.
The file delay is synthetic; no arbitrary Windows driver stall is qualified.
Host-injected Windhawk modules are separate from product imports. Other platforms,
real storage, privilege isolation, recovery, installation, signing/publication and
owner acceptance remain unverified or separately gated.

Continue DE-W017: measure whole-frontend memory and enforce applicable limits, exercise full-destination and combined malformed/crashed/slow-provider faults, and resolve event-stream scope with explicit gap/resnapshot contracts before public streaming. Preserve immutable claims, uncertain outcomes and epoch ownership; no automatic operation retry.
