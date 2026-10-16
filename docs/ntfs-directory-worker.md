# Owned NTFS directory observations

DE-W092 extends the existing NTFS snapshot and Windows reader for directory mode.
The [execution contract](../spec/catalog/ntfs-directory-worker-prototype.json)
was recorded before implementation and evaluation. It binds request/frame kinds,
full directory references, limits, source identity and the actual owned process.
Default bootstrap requests retain their existing v1 shape and behaviour.

The parent reconstructs directory observations from retained read responses,
including automatic NTFS3.0 profile selection. It derives the bootstrap prefix
from replay and checks the prefix foundation, hashes, counts, selected domain
and final report. It does not reopen the source or trust the child's completeness
claim. Legitimate incomplete results remain inspectable without applicability.

The adapter reuses the existing process host, finite8MiB mapping,128MiB job,
128KiB input and source quotas. Directory observation and capture components
have2MiB and64KiB bounds. The conservative frame bound is7,020,544 bytes.
Only a validated publication after actual owned-child exit can become an
immutable snapshot. Cancellation, a timeout or an uncertain live child does not
establish completion or writer quiescence. Test controls exist only in separately
built fault compositions.

The working corpus passes235 cases/12 methods, including both supported versions,
fragmented record/list/bitmap layouts, an exact128-block graph, actual reads
above4GiB, source removal, copied inputs, malformed frames, corruption of every
new prefix receipt and actual process lifecycle failures. These are working-tree
results; clean-source x64 and selected Win32/WOW64 qualification is pending.
The first code-hash fixture mismatch and its correction remain in
[working evidence](../.aide/evidence/2026-10-16-ntfs-directory-worker/working/).

This private adapter has no public directory command, namespace/tree traversal,
content extraction, physical-device or writer admission. It does not complete
NTFS, qualify all original platforms/storage or establish release readiness.
