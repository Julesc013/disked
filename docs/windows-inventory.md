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
The lifecycle adapter uses empty graph fragments: namespace-to-node projection,
native physical identity/topology and live/product/provider/platform admission
remain next work. Owner and full-unit/all-platform/storage claims remain open.
