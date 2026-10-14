# Exact campaign failures and bounded timing investigation

The DE-W075 campaign at `39d514f1a606290c63a6a63b2ce9e6d5d6e3e673`
is not qualified while its complete native regression result contains failures.
Preserve its raw log, JUnit, source inputs, retained generated fixtures and actual
terminal status. A later isolated pass cannot rewrite that campaign as passing.

The extraction fixture's retained final records report completion of a 17 MB
resume in 213.422 seconds, after its original 90-second test deadline. This is a
recorded outcome, not a diagnosis of the delay or a passing test. The export
fixture with `request_wait_expired` has an admission file but no request/history
at the inspected location. Do not infer successful launch or effects from it.

The next experiment adds bounded timing output only under the existing
`DISKED_FILE_ACQUISITION_TESTING` composition. Normal builds do not read the new
environment control. Timings contain fixed phase names, ordinal, monotonic time,
process CPU time and checkpoint count; no source bytes, paths or credentials.
The trace stops at 16384 records and an incomplete trace cannot qualify a claim.

Expected diagnostic checks, defined before execution:

- Generate the same FAT16 allocation/content shape as the retained fixture.
- Create and verify an actual paused 589824-byte prefix, then resume it through
  the ordinary file adapter using 64 KiB chunks.
- Compare the entire final logical content and sealed map with an independent
  generated-byte oracle; hash the unchanged backing file before and after.
- Retain complete input/output, actual child exit, artifact identities, source
  identity and timings for metadata, content, binding and flush phases.
- A normal preparation ignores the test timing environment and creates neither
  destination nor map. Existing fault controls and product behaviour remain.

The experiment has its own finite 300-second diagnostic ceiling. It does not
increase the original test deadlines, suppress a failure, qualify the full
native suite or establish a fix. Sequential build/test execution avoids adding
another campaign to the measurement, without asserting the cause of old delays.

No physical devices, elevation, customer data, installation, signing, release
publication, owner acceptance or full original 0.1.0 completion is involved.

The complete campaign has 137 passes and eight failures. Its separate structural,
context, source/import and 242-test tooling checks (two skips) pass, and all
51 standalone header objects are retained by identity. See
`failed-39d514f1/observation-summary.json`; its raw logs and JUnit remain unchanged.

The working timing build and original file-acquisition regression pass. The
diagnostic verifies an actual paused prefix and complete resume in 29.984 seconds,
including 19.177 seconds in map flush spans and 8.988 in destination flush spans.
Metadata, content and binding spans total 1.508 seconds. The 6642 trace rows remain
below the cap. Normal preparation ignores the timing control and creates no
outputs. All children exited; content/map checks pass and the backing hash matches.
These timings include instrumentation overhead and are observations of this
run, not an explanation of the earlier delay or a throughput guarantee.

Selected adapter targets do not generate the product's embedded build-identity
file. The first retention attempt incorrectly expected it; retention now records
the actual selected compiler/configuration facts and that absence explicitly.
No product identity is fabricated. `timing-working/` retains the exact working
source snapshot, build commands, raw traces, results and artifact identities.

The once-only focused rerun at the original exact source and binary identities
passes all eight failed groups with unchanged deadlines and assertions. See
`retest-39d514f1/summary.json`. This is a diagnostic result; the original complete
campaign still has eight failures and their cause remains unproven. A complete
campaign at the next committed source remains required before integration.

That next complete exact campaign at `11e6f625` has144 passes and one failure in
joined-report read-only preparation (`request_wait_expired`). Build,51 headers,
242 tooling tests/two skips, imports/context and source freshness pass. Its raw
terminal evidence is retained in `failed-11e6f625/`; it is not native-qualified.

Six bounded CLI preparations on the actual retained fixture then complete in
0.103-0.165 seconds, with identical responses,0.094-0.156 seconds of observed CPU
time, matching source hashes and no destination or state-store outputs. All
owned children exit. Process I/O counters include stdout writes; they do not
imply report-output effects. These measurements include harness overhead and do
not identify the cause of the earlier deadline expiry. See
`joined-prepare-11e6f625/summary.json` and the complete raw responses.

Preserve the four-second request boundary and the original tests. No further
unchanged full campaign is justified merely to obtain a pass. The next corrective
task needs concrete phase observations or a diagnosed repair; independent work
can continue where its owning gates permit. Main integration remains withheld.
