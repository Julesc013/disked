# W033 private acquisition worker checkpoint

Clean source: `e835a0322392fa941939cb067eb05df86660f370`.
Work base: `de2f64dc9c790e4d268334106f7ac22217b4edba`.

The private Windows worker performs real generated-file acquisition independently
of its submitting process. It retains an immutable reviewed definition and a
separate explicit effect grant, operation/worker/attempt identities, bounded
verified-checkpoint progress and a terminal record after provider-handle release.
Cancellation pauses at a verified checkpoint; explicit same-code resume creates
a new operation attempt and preserves original capture provenance. The worker
shares the tested four-process/128-MiB-per-process/512-MiB aggregate job budget.

Fresh-checkout results: **43 native groups**, **387 recorded worker checks**
(including reconnect polls), **10 completed byte/map verifications**, **126 file
adapter cases**, **218 core cases**, and **171 specification tests** (169 pass;
two existing symlink skips). All 909 structural checks and generated/manifest/
context freshness checks pass. Exact commands, raw logs, artifact hashes, source/
configuration identity and six executable PE/import observations are in
[the reproduction receipts](reproduction-e835a032/clean-results.json) and
[commands.json](reproduction-e835a032/commands.json). Only static import tables
and source-declared system-library loading were checked; these are not a complete
observed runtime-module inventory. See [FINDINGS](FINDINGS.md) for corrections and
superseded working observations; [REVIEW](REVIEW.md) records agent review.

To reproduce from this source:

```powershell
cmake --preset windows-bootstrap
cmake --build --preset windows-bootstrap
ctest --preset windows-bootstrap --output-on-failure
python tests/images/test_acquisition_worker.py --probe build/windows-bootstrap/Release/acquisition_worker_probe.exe --fault build/windows-bootstrap/Release/acquisition_worker_fault.exe --root .
python tests/images/test_file_acquisition.py --probe build/windows-bootstrap/Release/file_acquisition_probe.exe --fault build/windows-bootstrap/Release/file_acquisition_fault.exe --root .
python tests/images/test_acquisition_pipeline.py --probe build/windows-bootstrap/Release/acquisition_probe.exe --root .
```

The selected toolchain is MSVC 19.44.35228.0, toolset 14.44.35207, SDK
10.0.19041.0, x64/C++14/static release CRT. The tested host is non-elevated
Windows 10 Enterprise 10.0.19045. Binary copies are retained locally under
`.aide-local/artifacts/DE-W033-worker-e835a032/`; their exact hashes are in the
receipt. They are development/test artifacts, not signed or published releases.

`disked.exe` retains the existing image-observation/fake composition and does
not link the acquisition worker. Public `image.acquire`, acquisition operation
commands/watch and shared frontend review/grant integration remain unavailable.
DE-W033 and all DiskEd 0.1.0 remain incomplete. Physical media, real failing media,
power loss, snapshots, restore readiness, other platforms, owner acceptance and
release/storage authority are separate gates. The prototype map is not the
production journal or a stable storage ABI. Retain the v1 source/binaries/evidence;
no automatic cross-generation resume is admitted.
