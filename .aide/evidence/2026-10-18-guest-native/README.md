# Restricted guest compiler checkpoint

Work `DE-W105`, base `c038fb5069d342052e0d3623473010e1a4df3b5f`, branch `dev`.
This checkpoint qualifies native compiler probes. It is not a DiskEd product
build, work-unit completion, owner acceptance or release qualification.

The actual pinned MSVC 19.44.35228.0 toolset 14.44.35207 and Windows SDK
10.0.19041.0 compiled and launched the retained `compiler.cpp` for both x64
and Win32/x86, using `/MT`, warnings as errors and the recorded hardening flags.
Both executables reported their exact `_MSC_FULL_VER=194435228`, pointer width,
AppContainer=1, elevation=0, outside-write error 5 and capped filesystem size
535,752,704 bytes. Their observed PE machines were `0x8664` and `0x14c`.
Each architecture has actual environment, compile, launch and direct-import
observations, process IDs, executable/compiler hashes and exact commands.
The direct-import observation is not a transitive dependency qualification.

The first attempt failed with compiler D8018: no linker response file could be
created. The diagnostic attempt then showed Windows rewriting native TMP/TEMP
to `local/Packages/<fresh-identity>/AC/Temp`, which did not exist. Python had
cached an earlier environment snapshot and selected a different usable path.
The diagnostic's first JSON reader also encountered a previously retained
Python startup warning; the full merged output is retained, and the corrected
reader selects the emitted final JSON line. No product output parser changed.

`tools/windows-worker.py` now creates the exact package temporary directory
while the workspace is fresh, before any worker starts. Every later launch
validates its ancestors and sets the native/Python temporary environment to the
same owned location. A replaced junction is refused before launching a process.
The Windows regression exercises actual GetTempPathW and native file
create/delete, plus the junction replacement. All **106 tooling tests passed,
with one expected skip**. The earlier 253 specification tests/two skips are
retained in the preceding checkpoint; canonical specification files are unchanged,
and current structural/manifest/context checks passed.

The successful campaign reused the existing fixed-guest setup in managed host
staging, with a declared native payload and compiler source. Source hashes bind
every guest input. The host adapter additionally monitors a 1 GiB conservative
shared-VM backing-file growth ceiling and the established free-space reserve.
No toolchain ACL, host UAC, account, checkpoint, VM CPU/memory configuration or
network listener was changed. Routine access used Agents only; Codex remains the
emergency spare. The successful campaign's backing file remained exactly
28,809,625,600 bytes from start through completion. This does not reclaim earlier
shared-guest growth or claim that virtual storage is free.

The image, objects, generated executables, profile mappings and temporary guest
copy were removed. The verified context pack was removed after use; its complete
size was 17,690,570 bytes. Only the already verified portable Python runtime is
retained in the guest as development infrastructure.

`observations.json.xz` preserves exact raw successful/failed compiler results,
early context and full tooling/snapshot-test logs once. Its JSON maps original
names to `sha256` and exact `utf8`; `observations-index.json` records the verified
9,668-byte archive and original hashes. Readable final receipts omit raw command
output/log text and refer to those retained bytes. Do not rerun the one-time
retention script or overwrite this checkpoint's receipts for later work.

`source-snapshot.py` prepares the next product build's source transport: exact
selected Git blobs, original commit/current trees and a shallow sparse checkout,
without parent history or unselected evidence blobs. Seven actual small Git
fixture tests pass, covering exact clean revision/bytes, omitted bulk/history,
dirty-source refusal, corrupted pack, unsafe paths, linked output, source output
and oversized manifests. The helper bounds selected content/pack size at 32 MiB,
selected files at 2,000 and objects at 10,000, with admission before packing.
**The actual DiskEd snapshot export and guest product build remain next.**

Commands actually run:

```text
python -B tools/workspace.py run -- python -B .aide/evidence/2026-10-18-guest-native/prepare-context.py
python -B tools/workspace.py run -- python -B .aide/evidence/2026-10-18-guest-native/validate-tools.py
python -B tools/workspace.py run -- python -B .aide/evidence/2026-10-18-guest-native/compiler-campaign.py
python -B tools/workspace.py run -- python -B .aide/evidence/2026-10-18-guest-native/test-source-snapshot.py
```

Proceed with an exact clean source snapshot, pinned x64 CMake File API configure
and the bounded eighteen-group private Win32 supplement. Preserve all required
tests/headers/import observations. Keep all broader platform/storage, journal,
physical-device, owner-acceptance and release gates separate.
