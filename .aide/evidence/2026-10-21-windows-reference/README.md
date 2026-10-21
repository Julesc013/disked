# DE-W107 fixture preparation

This is working preparation, not a completed Windows reference campaign.
The [frozen byte facts](fixtures-before-native.json) define four separate 4 MiB,
512-byte-sector fixtures and twelve required native/API/UI observation tuples.
No native probe, virtual-media attachment, Windows API query or Disk Management
observation has yet evaluated these fixtures.

The generator uses only Python's byte, integer, UUID and CRC facilities; it imports
no product implementation. MBR has two bounded nonoverlapping extents. GPT copies
have independently placed arrays and reciprocal headers. The damaged case changes
only primary header CRC byte 528. The conflict case advances the backup's first
partition from LBA 2048 to 2049 and recomputes both backup CRCs; both interpretations
remain valid and unresolved. These images contain partition metadata, not formatted
filesystem contents.

Microsoft documents a [3 MB minimum for CreateVirtualDisk](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/nf-virtdisk-createvirtualdisk).
The historical 128 KiB corpus remains unchanged; simply padding its GPT bytes would
not relocate or repair the backup geometry. These new fixtures explicitly bind
their full 8,192-sector geometry and exact bytes before evaluation.

The [fixture validation](fixture-validation.json.xz) records 89 differential tests,
five platform skips, zero failures, 1,328 structural checks and manifest freshness.
Five new byte/CRC tests use independently decoded offsets, fixed extents and CRC
recalculation; the remaining suite preserves the existing completeness and worker
controls. These are ordinary host byte/metadata tests with no native product or
storage API execution. Managed temporary output was removed.

Next, finish the exact guest execution contract and implementation together:

1. Bind the existing guest build, code/tool/component identities and fixed API/UI
   commands before evaluation. Query only an owned virtual disk resolved from its
   file/virtual-disk identity and handle; a disk number alone is insufficient.
2. Demonstrate the owned attachment and output/profile path within existing caps.
   Administrative reference setup and UI observation must be labelled separately
   from the restricted native product worker. Protect shared Agents state and
   coordinate the desktop; do not change shared users, UAC or VM configuration.
3. Collect all four native/API/UI sets from independent initial copies, including
   raw failures, component identity, UI evidence and actual before/after effects.
   An API-only result cannot complete the declared UI set. Detach and remove one
   participant's media before creating the next; retain generators and compact
   results rather than images or profiles.

The documented API question is
[IOCTL_DISK_GET_DRIVE_LAYOUT_EX](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-ioctl_disk_get_drive_layout_ex).
Its result, the independently decoded bytes and UI display remain separate.
The full specification/native/Windows execution gates for this new slice are
pending. DE-W106's integrated review is retained separately; original 0.1.0 scope,
owner acceptance, provider admission and release gates remain unchanged.
