# Native execution storage gate: concrete setup decision

Status: proposed execution setup, **not authorized, provisioned or qualified**.
Base: `1e7573ce745b758e68e3be53ce3ec2d9abae3276`.
The continuing 0.1.0 goal is active; native campaigns remain at the storage gate.
The preceding cleanup turn was progress: it removed the accumulated scratch and
committed tested maintenance controls. This note does not narrow the product goal.

## Current host observations

Read-only inspection on 2026-10-17 found Windows 10 Enterprise build 19045 under
`BLACKGLASS-WIN1\Jules`, with a non-administrator token. C: and D: are NTFS and
have more than the required 20 GiB free. Hyper-V's VHD commands are available and
its services are running. No VM matching `DiskEd*` was returned. Windows Sandbox's
executable exists; no Sandbox was launched and its effective configuration was
not qualified. FSRM quota commands are unavailable. A command's presence does not
establish permission to execute it or an effective storage boundary.

The installed watchdog still does not deny allocation or prevent writes to other
directories. There is no evidence that the native storage gate has been satisfied.

## Two concrete routes

1. **Use an existing capped Windows worker.** The owner identifies the environment
   and authorized access method. Before any native campaign, verify a hard
   working-storage ceiling of at most 1 GiB, confinement of worker writes to that
   storage, and the actual compiler/SDK configuration. A folder name, a VM name or
   a JSON assertion is insufficient. No new VM, image, download or host change is
   implied by choosing this route.
2. **Authorize bounded setup on this host.** Proposed target:
   `D:\Projects\DiskEd\scratch\disked-work.vhdx`, a single new, blank, fixed
   512 MiB virtual disk. Its backing file and all disposable state must remain
   within the existing 1 GiB aggregate allowance. It must be paired with an
   OS-enforced worker write restriction; a mounted small volume alone does not
   stop fallback writes to C:, D:, another checkout or a user profile. Source and
   toolchain inputs remain read-only to workers. No generic disk-number target,
   source-disk cloning, physical-device operation, broad permission change,
   software installation or new servicing daemon is included. Provisioning and
   mounting require separate authority; elevation may also be needed. The exact
   provisioning and confinement implementation must be reviewed before execution.

Neither route is selected. No storage or worker identity has been created.
The local route may fail toolchain-compatibility checks; no successful isolation
or native build is assumed in advance.

## Required evidence before admitting a native campaign

- Start with a tiny, explicitly capped test filesystem, at most 32 MiB, and a
  bounded writer capped at 64 MiB. Write actual distinct data; a sparse logical
  length is not an exhaustion test. Observe filesystem allocation denial before
  the writer's own upper bound. A plain host directory must fail qualification.
- From the same restricted worker, attempt writes to an owned stand-in directory
  outside the allowed workspace, including a fallback temporary path. The OS must
  deny the writes; the outside sentinel must remain byte-identical. Do not probe
  another project's actual files. Verify descendant workers have the same limits.
- Interrupt an owned writer and verify process retirement and cleanup. Retain
  compact source/configuration identities, exact commands, OS errors, hashes and
  actual allocation/free-space observations. Do not retain the generated payload.
- Only after those checks pass, qualify the selected 512 MiB production scratch
  configuration and the existing process/job/file-count watchdog together. A
  failed setup must not create another image or choose a fallback directory.
- Confirm the source/toolchain snapshot and build configuration fit the cap.
  Build smaller cohorts when needed; do not raise limits or duplicate the whole
  repository and its historical evidence.

The 20 GiB reserve must continue to protect the **host backing volumes**. A capped
32/512 MiB filesystem cannot itself have 20 GiB free. Any selected implementation
must explicitly distinguish host reserve from scratch capacity, update the
owning runner contract and test both. The current runner has not been changed to
make that distinction, and the existing reserve rule has not been relaxed.

Microsoft documents [FSRM folder quotas](https://learn.microsoft.com/en-us/windows-server/storage/fsrm/quota-management),
[virtual disk creation](https://learn.microsoft.com/en-us/powershell/module/hyper-v/new-vhd)
and [Windows process/file isolation](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer).
These are available design mechanisms, not evidence that this host's complete
boundary exists. An AppContainer, restricted token or VM must be qualified for
the selected compiler/tests and all relevant writable locations.

## Authority needed

Root `AGENTS.md` states: **"Do not provision/mount storage or elevate implicitly."**
The programme separately reserves elevation and installation authority. The goal
continuation supplies no selection or grant for either setup route. Native work
therefore stays stopped while independent read-only/tooling preparation continues.
