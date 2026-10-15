# Held ordinary-file NTFS observations

DE-W081 binds the existing supplied-reader NTFS bootstrap to a Windows ordinary
image file. Its [execution contract](../spec/catalog/ntfs-file-prototype.json)
defines the source/window, profile and evidence rules before evaluation.
The synchronous adapter requires process containment before public frontend use.

The request and callbacks are copied before callbacks run. Existing shared file
mechanisms pin each ancestor, bind the exact opened ordinary file and deny
cooperating write/delete access. Source generation and metadata are checked
around each bounded native read and after retained replay. Actual seek/read
attempts, refused reads, available bytes and errors stay distinguishable.

Automatic mode observes supported NTFS3.0/3.1 volume information. A3.0 selection
re-evaluates the supported common bootstrap using retained bytes and requires
exact trace/result agreement after only documented profile fields change. It
does not issue another native read or blindly relabel a failed result. Explicit
profiles preserve version mismatches. Unknown versions remain inapplicable.

Final pure replay, metadata completeness/equality, sticky binding diagnostics,
process creation/sequence and profile/window-bound domain hashes remain separate
facts. Any disagreement withdraws applicability. Equal finite observations do
not establish atomicity, allocation ownership, future source permission, health
or writer authority. Expected metadata is a precondition, not a grant.

Native tests use only generated ordinary files and separate test-only controls.
Normal code exposes no environment fault protocol. Worker/public integration,
attribute-list/extended records, namespace/content, other platforms, physical
writer/recovery and the original all-platform/storage0.1.0 remain required.

Exact clean `777fd71f` passes 73 file responses/nine methods, all 18 selected x64
native groups, five headers and 242 tooling tests/two skips, with source/context,
manifest, dependency and normal/fault import/security checks. An isolated x86
fixture derived from the actual CMake codemodel passes the same 73 file responses,
154 bootstrap cases, two groups and two headers on the recorded x64 host/WOW64.
Both architectures exercise real native seeking above4GiB and full logical source
hash preservation. Four full launch samples retain independently checked process
creation, source metadata, exact read responses and profile decisions.

Actual leaf-file symlink creation remains unverified because the required
privilege is absent; parent/leaf junction and hardlink refusals are tested.
This does not qualify the full product/Win32/other hosts or public NTFS dispatch.
[Evidence and implementing-agent review](../.aide/evidence/2026-10-16-ntfs-file/REVIEW.md).
