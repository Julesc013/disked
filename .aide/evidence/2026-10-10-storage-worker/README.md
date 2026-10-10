# Owned injected Windows storage observations

Exact source `16259b7a3d6ba19cf23b6305f16118bd9bc6955d` builds and runs six private targets on both x64 and x86
using the recorded ordinary, non-elevated Windows 10 Enterprise 10.0.19045 host.
The new owned metadata campaign passes 43 controller executions, 35 actual
reader launches and 671 independent assertions per architecture. Existing
namespace graph/worker/lifecycle, volume adapter and standalone metadata
campaigns pass too. Combined: 444 controllers, 170 children
(614 processes), 8480 assertions and 12 local probes.

One shared observation host owns both private profiles. Preparation pins code,
serializes input and creates finite mappings/jobs/events without a child. The
adapter retains the prepared session before capture registration and launch.
Successful native process/thread ownership is stored before identity lookup
or allocation. Known no-launch and unresolved post-spawn failures are separate;
post-spawn exceptions, including the selected allocation fault, keep the exact
reader outstanding until observed exit. Tests cover both metadata and namespace
startup, refusal of replacement, actual reader-only retirement and a new capture.

The parent verifies one publication against exact request/code/host/epoch and
native process identity. It reconstructs the immutable metadata frame from
bounded returned-byte receipts and original subjects/policy without invoking
the original provider. Receipt decoding verifies conformance; it supplies no
provenance or proof of unrecorded calls. Owned-session context binds graph IDs
separately from fixture-only context. Identity/generation/physical capacity
properties stay unknown/null and all authority flags stay false.

Cancellation, held publication, timeout/late result, pending queries with an
invalid returned count, callback exception, reader crash/retirement, superseded
captures and controller disconnect retain separate outcomes. Partial frames
retain only the last complete frame as stale content without recursive cache
growth. The peer source remains intact. Native/mixed tables, malformed envelope/
claims/frame/policy/receipt/capacity and unbound subject data are refused.

MSVC 19.44.35228/v143 14.44.35207, SDK 10.0.19041.0, C++14/static CRT,
actual configurations, PE headers/imports/dependencies, commands, requests,
replies, logs and artifact hashes are retained. The tooling suite runs
215 tests (213 passed,
2 skipped); 1049 structural
checks, generated freshness, source-bound context and manifest pass.
54 selected private inputs match exact Git/checkout bytes.
The dev.38 product's 401 inputs remain identical to its qualified source
`3463fb238c38f4dbe085061c7980aaf7eaab53d2`; no new product build/full-suite
result is claimed for this private-only change.

`initial-compile/` retains the actual wrong-JSON-null-enumerator compiler defect
and source/error bytes. `initial-harness/` retains the actual duplicate-subjects
Python fixture-construction defect and incomplete native observations. Neither
is a passing campaign. The earlier harness probe's hash is recorded; its binary
was superseded and is not claimed as a retained artifact. Both fixes preceded
the final clean qualification. `inventory.json` binds retained raw evidence and
all twelve final local executable artifacts. See [implementing-agent review](REVIEW.md).

This is a compiled injected-reader qualification. Live dispatch, actual physical
identity/topology/raw layout, frontend/product/provider admission, all historical/
other platforms, owner acceptance and full DE-W030/0.1.0 remain open. It is not
a hostile-code sandbox, universal kernel-latency bound, exhaustive host-allocation
sweep, durable reconnect, writer retirement or recovery authority. No physical
device, elevation, customer data, installation, signing or remote write occurs.

```text
python .aide/evidence/2026-10-10-storage-worker/reproduce.py --source-revision 16259b7a3d6ba19cf23b6305f16118bd9bc6955d --output .aide-local/NEW_SHORT_ROOT
```
