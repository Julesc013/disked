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

Exact source `1001d463` passes 235 cases/12 methods on x64 and Win32/WOW64,
including source removal, copied inputs, every new receipt corruption, real process
lifecycle, exact 128-block graph and actual reads above 4GiB with unchanged source
hashes. The clean x64 campaign builds all targets and passes 35 selected groups
of 162, 63 standalone headers, C90/import checks and 244 tooling tests (two skips).
The Win32 supplement passes eight groups/six headers; it is not the full Win32
product. [Review and evidence](../.aide/evidence/2026-10-16-ntfs-directory-worker/REVIEW.md)
retain the first fixture failure and the unavailable expanded-working exit receipt.
Clean qualification records actual exit codes; no result is manufactured.

This private adapter has no public directory command, namespace/tree traversal,
content extraction, physical-device or writer admission. It does not complete
NTFS, qualify all original platforms/storage or establish release readiness.
