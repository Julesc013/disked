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
Public command/frontend admission, attribute lists, namespace/content, physical
access, mutation, other hosts and full0.1.0 qualification remain outstanding.

Implementation and native qualification are in progress. W075/report-preparation
still prevents whole-branch promotion to main. Owner acceptance is separate.
