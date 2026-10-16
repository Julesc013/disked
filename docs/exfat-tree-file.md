# Held ordinary-image exFAT trees

DE-W075 extends the existing `providers/image/exfat_file` adapter. Its new private
tree API holds the ordinary file and ancestor generations through collection,
retained replay and final binding checks. Root capture v1/v2 outputs and their
read order remain compatible. The runtime collector remains the owner of tree
semantics; portable/exfat remains the format decoder.

Inputs, limits, expected metadata and callback objects are copied before any
callback. Actual held metadata establishes source identity and capture epoch.
Every applicability decision is retained alongside the ordered read responses.
Replay consumes those exact sequences without native reads or live cancellation
callbacks. Changed binding, metadata or replay withdraws stability and retains
observed prefixes. Tree completeness and observed source-region stability are
different properties; neither grants current-source or mutation authority.

The original working native tests passed 46 generated-file cases/eight methods, including nested
fragmented/NoFatChain allocations, ValidDataLength zero filling, actual held-handle
exclusion, invalid inputs, cancellation and replay disagreement. The original89
root-file cases and44 supplied-tree cases pass. The first dependency check correctly
reported the new tree/namespace closure; its owning declaration is updated for
the implemented shared API. The complete exact `39d514f1` native campaign has
137 passes and eight failures in existing verification, export and extraction
journeys. Its 51 headers, 242 tooling tests/two skips, structural checks, imports,
context and source freshness pass. At that revision, native qualification and integration were
withheld; those independent checks cannot clear the failed campaign.

A bounded fault-build timing experiment independently verifies the same generated
17 MB resume shape, final content, sealed map and unchanged backing image. It
completes in 29.984 seconds, with 28.165 seconds in measured flush spans. This does
not explain the earlier 213.422-second resume or establish a fix. The normal
adapter ignores the new test timing control; the existing acquisition regression
passes. [Retained evidence](../.aide/evidence/2026-10-15-native-delays/README.md)
keeps failures and diagnostic measurements distinct.

The later complete exact `11e6f625` campaign passes 144 of145 native groups,
51 headers and242 tooling tests/two skips with imports/context/source checks.
Joined-report read-only preparation returns `request_wait_expired` in its failing
group. Six subsequent bounded samples on that retained fixture return identical
completed preparations in0.10-0.17 seconds, preserving inputs and creating no
outputs. They do not reproduce or diagnose the earlier delay. Integration was withheld for that campaign; the full failed campaign is preserved alongside these observations.

This is a synchronous private adapter. It creates no extracted files and is not
admitted to normal worker/frontend dispatch. Paging/backpressure, contained
transport and process retirement, other platforms/storage, owner acceptance and
full original 0.1.0 remain at their gates. No new fault environment protocol is
available in normal code.

Current clean `7bb6153a` passes 46 tree-file cases/eight methods and all 160 x64
native groups, including every previously failing group. 63 standalone headers,
244 tooling tests (two skips) and source/import/context/manifest checks pass.
[Current-source review](../.aide/evidence/2026-10-16-exfat-tree-review/REVIEW.md)
supersedes the historical campaigns as an active integration blocker. It retains
both failures and does not establish their original delay cause or owner acceptance.
The private synchronous boundary and later transport/platform/privilege gates above
remain unchanged.
