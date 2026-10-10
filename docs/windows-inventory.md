# Native Windows inventory development

DE-W030 starts with a native volume-namespace/mount adapter. It calls the
documented volume enumeration APIs only through an explicitly dispatched cursor.
Construction performs no query; the current DiskEd product composition and
startup remain unchanged. The private
[profile](../spec/catalog/nt-volume-namespace-prototype.json) defines expected
behavior before native evaluation.

Original UTF-16 code units have a lossless representation separate from escaped
display. Capture/ordinal observation IDs are not physical disk IDs. Duplicate
volume names and observed mount conflicts remain separate and cannot authorize
mutation. Denied/unavailable/removed responses, finite budget exhaustion,
cancellation and uncertain search-handle close are explicit. Complete here
means only the selected namespace enumeration, never complete storage topology.

The adapter opens no files/devices and reads no filesystem labels, contents,
capacity or layout. Its modern-toolchain x64/x86 probe injects exact Win32
replies; it does not enumerate the live host. Native table binding can be
inspected without dispatch. A documented API floor does not qualify the selected
compiler/CRT/PE closure for XP. Actual live namespace, hangs/process containment,
provider/graph/public-service admission, physical identities and the full
Windows/platform matrix remain open.

Build the standalone private project and run a new fixture output directory:

```text
cmake -S tests/windows/native -B PRIVATE_BUILD -G "Visual Studio 17 2022" -A "x64,version=10.0.19041.0" -T "v143,version=14.44.35207,host=x64" -DCMAKE_SYSTEM_VERSION=10.0.19041.0
cmake --build PRIVATE_BUILD --config Release
python tests/windows/test_volume_namespace.py --probe PRIVATE_BUILD/Release/nt_volume_namespace_probe.exe --output NEW_EVIDENCE --pointer-bytes 8
```

`Win32`/`--pointer-bytes 4` select the separate x86 private probe. This is not a
shipped product composition, legacy support certification or owner acceptance.

Microsoft documents the APIs and their returned buffers/order independently:
[FindFirstVolumeW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-findfirstvolumew),
[FindNextVolumeW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-findnextvolumew),
[GetVolumePathNamesForVolumeNameW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getvolumepathnamesforvolumenamew).


A private same-file contained observer is implemented under the
[namespace worker profile](../spec/catalog/nt-namespace-worker-prototype.json).
It reuses existing native worker code pins, ACLs, job limits and restricted
handle lists. Input is a read-only bounded mapping; one verified reply binds
all epochs and actual process creation. Late observation keeps the same attempt.
Cancellation, publication and process exit are separate. Reader-only job
retirement/disconnect never supplies writer authority or durable reconnect.

The standalone CMake project also builds `nt_namespace_worker_probe`. Run:

```text
python tests/windows/test_namespace_worker.py --probe PRIVATE_BUILD/Release/nt_namespace_worker_probe.exe --output NEW_EVIDENCE --pointer-bytes 8
```

This selected worker uses modern job-list assignment; the API adapter's older
documented floor does not establish XP support for this process host. Microsoft
documents [job/handle-list attributes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute)
and [mapping access](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-mapviewoffile).
Native table binding can be inspected but cannot dispatch through this fixture
worker. Actual live/storage/public/provider/platform qualification remains open.

The [retained implementing-agent review](../.aide/evidence/2026-10-10-nt-contained/REVIEW.md)
records clean x64/x86 evidence at `d3798a7`: each architecture ran 49 adapter
processes with 258 assertions, and 24 controller invocations with 18 actual
reader launches and 116 assertions. Both full and mixed native tables are
refused before admission. The selected dev.36 composition remained unchanged
at that revision.

The common capture publication/retirement boundary now has exact-source local
qualification at `2d753bae` ([review](../.aide/evidence/2026-10-10-capture-publication/REVIEW.md)).
Complete/partial publications retain outstanding workers until bound actual
exit; stale old-capture replies cannot authorize replacement. Proposed dev.37
passes all 77 selected native regression groups. Both x86/x64 owned-reader
lifecycle and existing worker campaigns pass, with 16 independent reducer tests.
At that revision the lifecycle adapter used empty graph fragments; namespace
node projection was still pending, alongside native physical identity/topology
and live/product/provider/platform admission. Owner and full-unit/all-platform/storage claims remain open.

The private namespace observation graph is now locally qualified at `3463fb23`
([review](../.aide/evidence/2026-10-10-namespace-graph/REVIEW.md)). Proposed dev.38
passes 77 product groups and 23 reducer tests. Both x64/x86 graph campaigns pass
30 controller invocations, 26 actual injected reader launches and 1,103 assertions
per architecture; existing adapter/worker/lifecycle regressions also pass.
Volume/mount observations retain exact names, distinct context-bound IDs and
unknown physical identity. Partial frames retain only the last complete frame
as stale background; publication and owned reader exit remain separate.
The adapter is private, and the existing frontend rejects its unadmitted profile.
Native identity/topology, observation frontend, live/product/provider/platform
and owner/full-unit qualification remain next work.

The private injected storage metadata/extent layer is locally qualified at
`e469d70f` ([review](../.aide/evidence/2026-10-10-storage-queries/REVIEW.md)).
Each x64/x86 campaign passes 70 native fixture executions and 1,987 independent
assertions. Descriptor bytes, capacity disagreements, cloned serials, duplicate
numbers and candidate extent topology remain explicit observations. Pending
queries stop the batch, including invalid returned counts. Immutable frames
project into the common graph without physical identity or mutation authority.
The selected dev.38 product's 401 input bytes remain unchanged; this private
slice does not claim a new product build or a repeated full product suite.
Actual owned-reader integration, startup/retry reconciliation, observation
frontend, native identity/raw layout, live/provider/platform and owner/full-unit
qualification remain next work. Both full and mixed native tables are refused.

The shared owned namespace/metadata host is now locally qualified at `16259b7a`
([review](../.aide/evidence/2026-10-10-storage-worker/REVIEW.md)). Each x64/x86
metadata campaign passes 43 controllers, 35 actual reader launches and 671
assertions; five existing campaigns also pass (614 processes/8,480 assertions
combined). Preparation creates no child, post-spawn errors retain ownership,
and exact exit is observed before replacement. Parent receipt reconstruction
does not call the provider; owned process/code/request context binds graph IDs.
The dev.38 product's 401 inputs remain unchanged, with no new product/full-suite
claim. Observation frontend semantics, native identity/raw layout and actual
live/product/provider/platform/owner/full-unit admission remain next work.

The compiled private cached-observation frontend slice is locally qualified at
`8f55d867` ([review](../.aide/evidence/2026-10-10-observation-frontend/REVIEW.md)).
Dev.39 passes all 77 selected product regression groups. Each x64/x86 private
frontend campaign passes 15 controllers/26 actual
reader launches/1300 assertions; all private campaigns combine
696 processes/11080 assertions. Exact evidence focus, owned
context, missing/stale state, atomic publication, conservative target boundaries
and maximum inert display under the actual memory job are checked in existing
models. The ordinary product stays Fake. Actual new-profile visible interfaces,
native identity/raw layout, live/product/provider/protocol/platform and owner/
full-unit/all-platform/storage admission remain open. The source map now explains
all 170 files and planned ownership; private path changes preserve public IDs.

The private identifier/alignment/OS-layout query profile is locally qualified at
`b853621b` ([review](../.aide/evidence/2026-10-10-identity-queries/REVIEW.md)).
Each x64/x86 binary passes 57 generated cases and 197 assertions; affected
metadata/frame/owned-worker/cached-frontend regressions also pass (492
processes/8310 assertions combined). Exact identifier bytes, SDK layout,
GPT name units and conflicting reports stay evidence without physical identity
or effects. The dev.39 product's 403 inputs remain unchanged; no new product or
full-suite run is claimed. Integrate the new receipts into owned frames/graph
context next; raw-media comparison, composite identity, live/product/provider/
protocol/platform and owner/full-unit/all-platform/storage admission remain open.
