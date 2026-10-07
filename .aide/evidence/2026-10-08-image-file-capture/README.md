# DE-W024 private ordinary-file capture checkpoint

Source `d0229f7a52e79a938cc6b3389be96366f686e389`, base `307d3814fda66466a36f352d986da03d4df8c622`. This partial W024 deliverable adds a native
Windows ordinary-local-file adapter and metadata-region integration over the
existing private C90 map readers. The product remains 0.1.0-dev.17 with its fake
command composition: image.inspect and table.verify are still unavailable.

The provider reads explicitly named generated/disposable ordinary files without
mounting or writing them. It resolves and binds the selected path, pins inspected
ancestors, rejects reparse/device/network/stream/alias profiles and uses read-only,
non-inheritable handles with write/delete sharing excluded. Its prototype path
limit is 240 UTF-16 units and selected logical block units are 512 or 4096. These
restrictions do not qualify general filenames, other Windows or physical storage.

Capture retains volume/128-bit file identity, exact file length, derived block
geometry, attempt epoch/interval, region coordinates, actual bytes/digests/errors
and before/after metadata. Exact regions can be reused; distinct overlapping
regions are checked. All buffers outlive reader comparison, and returned values
own their data after source handles/buffers have been released. A finite second
pass checks every captured region. Coverage, observed stability and source
consistency remain separate: live-uncoordinated reads and equal rereads never
establish a snapshot, whole-file hash, recovery guarantee or writer authority.

Clean reproduction passes 104 file-capture cases and 75 map cases, all 39 native
CTest groups and 171 specification tests (169 pass, two existing Windows symlink
privilege skips). Cases retain independent corpus assertions and byte hashes,
missing/truncated geometry, valid/disagreeing GPT copies, duplicate/overlapping
region behavior, lossless Unicode paths, actual sharing/DACL/hardlink/junction
refusal and separately compiled read/short/change/metadata fault controls. The
fault controls change returned test observations; they are not evidence of actual
source mutation, hot removal, hardware failure or power loss.

A sparse generated GPT image of 8,590,065,664 bytes places its backup metadata
above a 32-bit byte offset. The provider captures five regions totaling 34,304
bytes and compares a second read of those regions. Large file support is not
limited by the 16 MiB immutable-prefix test API. The request ceiling is 517 and
5 MiB per observation; reports bind an owned full region manifest by digest and
retain bounded detail. No whole-image byte checksum was claimed or performed.

Commands/logs, 185 hashed native inputs, actual clean source/build identity,
executable/library hashes, imports and launch output are retained. Artifacts are
in `.aide-local/artifacts/DE-W024-file-d0229f7a/` with identities in
`reproduction-d0229f7a/clean-results.json`. Structural, manifest/context,
strict producer and passive AIDE validation pass; live AIDE was not run. Initial
directory/fixture/overlap/diagnostic failures remain in FINDINGS and selected logs.
The owner-pasted service notice is retained separately without an invented trigger,
request ID, model diagnosis or attribution of engineering failures to the service.

Reproduce on the pinned installed Windows toolchain with
`cmake --preset windows-bootstrap`, `cmake --build --preset windows-bootstrap`,
and `ctest --preset windows-bootstrap --output-on-failure`. The individual file
command is `python tests/frontend/test_image_file_capture.py --probe build/windows-bootstrap/Release/image_file_capture_probe.exe --fault build/windows-bootstrap/Release/image_file_capture_fault.exe --map-probe build/windows-bootstrap/Release/image_observation_probe.exe`.
No model service is needed by those repository commands.

Continue DE-W024 shared image command admission and actual CLI/TUI/GUI/shell parity. Define the prototype image-only composition, raw-file operands/unit and exact outcomes/preconditions in their owners before implementation; preserve source consistency/coverage limits and frontend stale/late-result containment. Do not treat captured-region verification as whole-file/snapshot/physical-storage qualification. Keep the full 0.1.0 scope, owner acceptance and storage/release authority gates separate.

The runner subsequently reported the persistent goal as blocked, without a reason
in its available status response. This is retained in runner-status.json; it does
not invalidate the completed local checks or establish a new engineering defect.
The project programme remains incomplete and resumable at shared image command work.
