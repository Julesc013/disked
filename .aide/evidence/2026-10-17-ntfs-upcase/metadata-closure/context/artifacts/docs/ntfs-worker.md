# Owned NTFS reader prototype

DE-W082 executes the private NTFS file bootstrap in the existing Windows
observation-worker host. Its pre-evaluation contract is
[ntfs-worker-prototype.json](../spec/catalog/ntfs-worker-prototype.json).
Source ownership follows the existing exFAT reader: `providers/image/ntfs_snapshot`
owns strict retained-byte frames and pure replay; `platform/windows/storage/ntfs_worker`
owns the concrete process/payload adapter. It introduces no second scheduler.

The caller supplies exact ordinary-file metadata, a path/window, profile, limits
and capture epoch. The worker opens the source only after release. The parent
checks publication digest, exact input, source/domain, process identities and
retained-byte reconstruction. A usable immutable result requires actual child
exit. An 8MiB payload mapping and the common host's 128MiB worker budget bound
transport and process allocation; source limits are unchanged.

`Snapshot` names the retained immutable observation object. It is not an atomic
filesystem snapshot or a grant to reopen the source. Explicit or automatically
selected NTFS3.0/3.1 bootstrap remains incomplete filesystem interpretation.
This unit's evidence alone does not qualify public command/frontend admission,
attribute lists, namespace/content, physical access, mutation, other hosts or
full0.1.0. Later bootstrap admission is documented in [NTFS inspection](ntfs-inspection.md);
private directory progress is in [NTFS directory indexes](ntfs-directory.md).

Exact clean `e164f863` passes 106 cases/eight methods, 20 selected x64 native
groups, eight headers and 242 tooling tests/two skips. Four full launch records
retain actual process/source/frame identities. See the [implementing-agent review](../.aide/evidence/2026-10-16-ntfs-worker/REVIEW.md)
and [qualification](../.aide/evidence/2026-10-16-ntfs-worker/qualified-e164f863/summary.json).
No full native, x86/old/other-host or public NTFS admission is claimed. The existing
file-symlink privilege gap remains unverified. The later
[current exFAT re-review](../.aide/evidence/2026-10-16-exfat-tree-review/REVIEW.md)
supersedes the old failed campaigns as an active integration blocker while
preserving their outcomes and unknown causes. Owner acceptance remains separate.
