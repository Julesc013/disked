# Private injected Windows storage observations

Exact source `e469d70f8845ae4659b335d61a6527b70b695dff` builds and runs the private metadata/extent target on
the recorded ordinary, non-elevated Windows 10 Enterprise 10.0.19045 host.
Both x64 and x86 campaigns pass 70 native controller executions and 1,987
independent assertions each: 140 executions and 3,974 assertions in total.
These use generated binary replies and pseudo-handles, with no child workers
or live storage queries. They qualify the selected injected factory only.

The layer captures descriptor strings/opaque properties, transient device
numbers, geometry, length and volume extents through exact Win32 signatures.
It preserves absent/empty/original metadata, escaped display, denied and
unsupported queries, changed/truncated results, capacity disagreements,
cloned serial candidates, duplicate numbers and unresolved/ambiguous extents.
Every resource/extent projects into the existing observation graph with
content-bound IDs, unknown physical identity and false authority flags.

All input validation precedes dispatch. Each component can be queried once;
descriptor and extent buffers grow at most once. Native/mixed pointer tables
are refused before querying. Cancellation is checked before each call. Pending
I/O remains unresolved even when its returned-byte count is invalid; callback
exceptions also stop the batch. This is a port/batch quarantine, not process
exit, cross-instance retry admission or complete storage identity.

The finite profile covers 16 subjects, 4,096 descriptor bytes, 256 string bytes,
64 extents per subject and 128 per frame. Receipts bind exact known returned
bytes and digests. The declared per-subject limit is captured before dispatch,
including the subject that consumes the final frame budget. The immutable
private frame has no external deserialization interface.

MSVC 19.44.35228/v143 14.44.35207, SDK 10.0.19041.0, C++14 and the static CRT
are recorded with compiler configuration, PE headers/imports/dependencies,
actual commands, replies, launches and executable hashes. Selecting the older
API declarations does not establish XP or other historical-platform support.
The tooling suite runs 215 tests
(213 passed, 2 skipped);
1047 structural checks, generated freshness, task context
and manifest pass. 37 private inputs are bound to exact Git
and checkout bytes. All 401 product inputs match the prior qualified source
`3463fb238c38f4dbe085061c7980aaf7eaab53d2`; dev.38 was not rebuilt and its full
product suite was not rerun for this private-only change.

`reproduction-e469d70f/` retains the clean run; `initial-compile/` retains
the actual earlier C2664 fixture compile defect, source bytes and exit result.
The accessor fix preceded qualification; no campaign was claimed from that
failed build. `inventory.json` binds the retained bytes and two local probes.

Owned-reader integration, startup/retry reconciliation, source authentication,
native physical identity/topology, frontend/product/provider/live admission,
all historical/other platforms, owner acceptance and complete DE-W030/0.1.0
remain open. This code is not linked into the product. No physical device,
elevation, customer data, installation, signing or remote write is involved.
See the [implementing-agent review](REVIEW.md).

Reproduce using the recorded toolchain and Python dependencies:

```text
python .aide/evidence/2026-10-10-storage-queries/reproduce.py --source-revision e469d70f8845ae4659b335d61a6527b70b695dff --output .aide-local/NEW_SHORT_ROOT
```
