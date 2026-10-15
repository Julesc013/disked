# NTFS captured-stream joining

DE-W085 verifies one exact type/raw-name stream across supplied captured FILE
records. The [execution contract](../spec/catalog/ntfs-join-prototype.json) fixes
sequence/owner/instance matching, coverage, budgets and result ownership before
implementation/evaluation. Source `23ceeb24` passes 298 protected-record cases,
25 selected native groups, 9 standalone headers and 244 tooling tests
(two skipped). [Exact source evidence](../.aide/evidence/2026-10-16-ntfs-join/qualified-23ceeb24/summary.json) and
[implementing-agent review](../.aide/evidence/2026-10-16-ntfs-join/REVIEW.md) retain the selection,
output ownership, missing-reference handoff, original failures and limitations.

Capture contexts are asserted input, not proven native provenance. A typed
stream exists only after complete checks. Missing/stale/malformed or unsupported
records produce observations without usable mappings. The separate
[source-bound closure](ntfs-closure.md) extends acquisition of supported
MFT/Volume dependencies and nonresident list values. Namespace/content and
general record lookup retain their implementation gates; inspection remains
bootstrap-scoped.
