# Held ordinary-file NTFS directory indexes

DE-W091 extends the existing ordinary-file adapter with the complete bounded
directory collector and explicit/automatic 3.0/3.1 selection. The
[execution contract](../spec/catalog/ntfs-directory-file-prototype.json) defines
immutable controls, prefix validation/continuation, quotas and retained replay.

Automatic 3.0 validates common facts from the exact retained bootstrap under 3.0,
then strictly reuses that prefix before new reads. Its actual native trace and
quotas equal explicit 3.0. Metadata after collection, selected observation, final
pure replay and final bindings remain separate properties. Refusal/incomplete
collection stays inapplicable even when replay agrees. Default bootstrap contracts
remain unchanged; the new wrapper/domain bind directory reference and limits.

Exact native source `4156accf` passes 550 responses/12 methods, five independent
report reconstructions, all-target x64 build, 31 selected native groups of 161,
63 C++ headers, strict C90/header checks, eight PE/import observations and 244
tooling tests (two skipped). The Win32/WOW64 supplement passes six groups/four
headers. Actual above4GiB reads and complete before/after file hashes are retained.
Two fixture failures and the rejected zero-test selector phase remain explicit;
corrected recipe `1e8d1087` reuses only verified unchanged build stages.
[Review and exact evidence](../.aide/evidence/2026-10-16-ntfs-directory-file/REVIEW.md).

This is a private synchronous source adapter. Contained worker/frontend admission,
namespace/content, original platforms/storage and separate owner, physical,
privilege and release gates remain required. Actual leaf-file symlink creation
remains unverified for absent privilege. No atomic snapshot or future effects
follow from equal finite observations.
