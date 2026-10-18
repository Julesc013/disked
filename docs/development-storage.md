# Development storage

`.aide-local/` is small disposable context/metadata, with a 32 MiB aggregate limit.
Builds, checkouts, dependency environments and raw probe dumps do not belong there.
The [shared instructions](../AGENTS.md) and [workspace runner](../tools/workspace.py)
own the development rules and their enforcement.

BLACKGLASS-WIN1 is the physical shared host. The earlier description of it as
the test VM was incorrect. On 2026-10-18 the user directed low-level testing into
the existing Hyper-V VM `Windows 10`, while allowing necessary host tests. Use
the guest by default and record why any test needs the host. Do not make repeated
host UAC prompts the normal execution path. Physical devices, customer data and
release work remain outside the test grant.

The guest's original 8 GiB startup and 32 GiB maximum could consume nearly all
available host memory. The owner changed the configuration on 2026-10-18 to four
virtual CPUs and 1–16 GiB dynamic memory, with 2 GiB startup, verified through
Hyper-V. Observe actual assigned memory; the maximum is not a reservation.
Automatic checkpoints are disabled; the pre-existing checkpoint is preserved. The original settings
are retained in the [VM inventory](../.aide/evidence/2026-10-18-vm-execution/before-start.json).
Do not delete or compact its existing disk/checkpoint chain as scratch cleanup.
Dynamic VHDs and dynamic memory still consume physical host resources. Monitor
backing-file growth, guest temporary output and host free space; deleting guest
files does not itself prove that the backing file shrank.

Cleanup of the incident scratch is complete. Normal native campaigns still
require actual proof of a hard filesystem boundary in the selected environment;
the watchdog below cannot deny allocation or prevent writes elsewhere. Keep the
existing budgets, protect concurrent users, and remove disposable output after
use. A guest login/transport and its actual toolchain must be established before
claiming a guest build or test result.

The [2026-10-18 guest proof](../.aide/evidence/2026-10-18-guest-capacity/README.md)
now demonstrates both 32 MiB and 512 MiB fixed filesystems in this guest. Windows
returned disk-full error 112; outside writes and backing-file writes were denied;
non-elevated AppContainer workers, descendants and interrupted controllers were
retired, and their profile mappings and test images were removed. The earlier
failed attempts remain retained. This qualifies the recorded bootstrap boundary,
not a native compiler, product, physical device or other execution environment.

The guest coordinator may administer its newly owned virtual image. An elevated
coordinator now derives a restricted primary token before starting tools; the
worker's actual elevation flag must be zero. Service sessions use an owned private
window station, with the coordinator's station restored after creation. Device
access for fresh package identities is separate from the backing-file ACL, which
must remain unchanged. The storage watchdog still does not constitute a quota.

`C:\ProgramData\DiskEd\python314\python.exe` is a verified project-owned portable
Python 3.14.7 runtime (37,630,185 content bytes), copied from the installed host
runtime without site-packages, caches or an installer. Its transfer archive was
removed. It changes neither the global PATH nor registry; additional coordinator
dependencies and every actual compiler/build claim remain separate work.

The subsequent [restricted compiler checkpoint](../.aide/evidence/2026-10-18-guest-native/README.md)
compiled and launched x64 and Win32 probes with the pinned compiler/SDK/static
runtime, verified non-elevated confinement, retained direct-import observations
and removed its outputs. It exposed a missing native AppContainer temporary
directory: the worker now provisions that directory inside fresh owned work and
validates it before each launch. This is compiler/bootstrap evidence; subsequent
source transport, configuration and product tests retain their own results.

Use [tools/source-snapshot.py](../tools/source-snapshot.py) for the bounded exact
source transfer. It selects the canonical build inputs, an explicit work unit's
required inputs and routing files; only their blobs and the selected commit/trees
enter the pack. The default requires a clean checkout. With `--revision` set to
an exact commit ID, both input catalogs and payload come from that commit; local
uncommitted edits remain untouched and the manifest records producer dirtiness
separately. This permits retaining campaign observations without incorporating
them into the tested source. It refuses unsafe paths, links, oversized selections
and corrupted packs. Materialization uses explicit
LF checkout policy and verifies every selected file plus the exact clean Git
identity. The [real-repository transport check](../.aide/evidence/2026-10-18-guest-source/README.md)
verified 931 inputs in a 3.7 MiB pack; the disposable pack/checkout were removed.
Its hash-bound metadata does not qualify a guest build or authorize execution.

The [guest build checkpoint](../.aide/evidence/2026-10-18-guest-build/README.md)
subsequently verified 931 source inputs inside the guest and completed the pinned
x64 configuration at its recorded revision. It exposed a fixture support-file
ownership error, now covered by 119 coordinator tests with one expected skip.
The later guest attempt stopped on directory DACL editing before native Win32
evaluation. Source copies, images and context packs were removed. No private
Win32/product build, owner acceptance or release qualification follows from this
partial checkpoint; its failed attempts and remaining repair are retained.

The shared NTFS fixture bases use [tests/support/tempdir.py](../tests/support/tempdir.py)
for temporary directories. Ordinary processes retain Python's standard behavior.
Inside an actual Windows AppContainer, the helper requires the source-bound work
marker and a plain temporary parent inside that workspace, then creates a fresh
directory inheriting its private parent's permissions. Python's explicit Windows
`0700` permissions omit the package identity; this is also reported in
[CPython issue 134587](https://github.com/python/cpython/issues/134587).
The helper changes fixture creation rather than interpreter globals or product
assertions. Cleanup checks the directory identity and preserves replacements.
Its unit tests do not substitute for actual guest fixture and native qualification.

### One-time guest connection setup

The Agents guest administrator and its encrypted host-side credential are now
configured. Do not repeat credential setup on each run. Use PowerShell Direct
with the existing VM ID, without opening network listeners or sharing the host's
source drive. Check the current programme before a campaign. Early connections
failed, including immediately after restart. After the owner completed first-login
setup, fresh Agents sessions passed identity, account configuration, tool inventory
and compiler-file inspection. Retain the earlier failures; this does not qualify
native campaigns or promise uninterrupted service availability.

For a new authorized setup only, in the Jules PowerShell 7 host context:

```powershell
pwsh -NoProfile -File tools/connect-vm.ps1 -SetupCredential
```

Use only the guest `Agents` account for automation. The owner selected it as the
single routine shared account. The helper rejects Codex and guest Jules before
authentication. Keep Codex and its profile as an emergency spare; the owner's
later clarification supersedes the earlier account-deletion request.
The observed guest account domain is `BLACKGLASS-HYPE`; its DNS name is
`BlackGlass-HyperV`. The saved credential uses `BLACKGLASS-HYPE\Agents`.
The owner removed Codex's password; actual blank-password PowerShell Direct
attempts were rejected. Do not repeat that setup or weaken the Windows
blank-password policy. An authorized guest-console bootstrap may create Agents
with the owner's supplied password. The owner also authorized setting that password
on the retained Codex spare. Guest Jules remains untouched.

For a credential already supplied through an authorized local setup process,
`-SetupCredential -GuestCredential $credential` avoids another prompt. Supply a
`PSCredential` containing the guest account and nonempty password, never a host
password or Windows Hello PIN. Do not put passwords in Git or retained logs.
Setup refuses an existing credential file instead of replacing it.

The helper verifies a PowerShell Direct connection to the fixed VM ID and checks
the guest's DNS/model identity and actual Agents identity before saving
anything. DNS and the Windows account domain need not have the same spelling.
Windows encrypts the
credential for this host user through `Export-Clixml`; it is stored outside Git
at `%LOCALAPPDATA%\DiskEd\credentials\vm-3ebbe558-91b9-435b-96e4-0c8199bd38ad.xml`.
It refuses an existing file during setup and never prints the password. The
default invocation checks an existing connection without prompting or running
tests. A missing credential fails immediately. See Microsoft's
[PowerShell Direct requirements](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/powershell-direct).

For an authorized guest campaign, obtain a session in the same PowerShell
process as the commands that use it, and remove it in `finally`:

```powershell
$session = & ./tools/connect-vm.ps1 -OpenSession
try {
    Invoke-Command -Session $session -ScriptBlock { hostname }
} finally {
    if ($session) { Remove-PSSession -Session $session }
}
```

This is connection setup, not worker qualification. Record the actual guest
token and toolchain, prove its working-storage boundary, and run builds/tests
with the bounded workspace runner inside the guest. Do not execute product tests
with an administrative connection token merely because setup required one.

The user explicitly authorized guest administrator access and disabling UAC for
the guest OS on 2026-10-18, then elected to make those account/policy changes
personally. Do not race that setup with another account change or guest reboot.
The owner subsequently reported completing that setup and restarting the guest.
Inspection confirmed Codex's Administrators membership, but found `EnableLUA=1`
and a filtered ordinary console token. The authorized guest-only bootstrap created
Agents, verified an administrative connection, and set `EnableLUA=0`. The owner
then authorized restarting despite unknown concurrent work. A normal shutdown
and start completed, preserving the checkpoint and host `EnableLUA=1`; see the
[restart receipt](../.aide/evidence/2026-10-18-guest-start/restart-result.json).
Later Agents sessions verified `EnableLUA=0` and an administrator token. Agents
is the primary account; Codex remains an enabled administrator spare with the
owner-supplied password and its original profile. Both passwords are non-expiring.
The helper does not automatically fall back to Codex. Actual observations,
failed checks and completed account setup are retained in the
[bootstrap result](../.aide/evidence/2026-10-18-guest-start/result.json).
This is the Windows
[UAC policy](https://learn.microsoft.com/en-us/windows/security/application-security/application-control/user-account-control/settings-and-configuration),
not simply the notification slider. Retain explicit test-token observations;
an administrative test pass does not establish standard-user behavior.

The existing guest compiler is at `C:\BuildTools`: toolset 14.44.35207 and
compiler file version 19.44.35228.0 match the pin. SDK 10.0.19041.0, CMake 3.31.12
and Git 2.53.0.windows.3 are present. The Python launcher reports no installed
runtimes; its WindowsApps alias is not an interpreter. The project-owned Python
runtime and subsequent compiler/capacity qualification are recorded above;
these do not qualify a DiskEd build.

Keep resource checks separate. Preserve the host backing-volume reserve and
the guest OS-volume reserve. Run the guest coordinator and its small managed
control workspace on the OS volume; do not point its temporary directory at a
512 MiB scratch filesystem and then demand 20 GiB free there. Confined child
processes use the capped filesystem, whose remaining capacity must fit the
declared task. Its reserved backing allocation and other disposable output must
fit the existing aggregate 1 GiB budget. A controller must also monitor actual
host free space and backing-file growth. The guest proof above establishes the
recorded bootstrap topology; the earlier host proof alone did not establish it.

The Agents guest account is shared with other agents. Use distinct workspaces,
keep DiskEd's single-campaign lock and budget, and retire only owned processes.
Do not reset, stop, reboot or compact the shared VM as automatic campaign
cleanup. Coordinate disruptive work and heavy campaigns with other users; a
VM-wide reboot is not equivalent to deleting one project's temporary directory.

[The current setup review](../.aide/evidence/2026-10-17-workspace-cleanup/storage-setup-review.md)
records the earlier refusal and AppContainer preparation. The pending host proof
subsequently completed: [its exact-source receipt](../.aide/evidence/2026-10-17-workspace-cleanup/capped-storage-32.json)
records allocation error 112 on the 32 MiB filesystem, denied outside writes
including a descendant, job retirement, held-file removal and backing-image
deletion. The helper ran elevated; test workers did not. This qualifies those
host proof cases only. It does not qualify a 512 MiB campaign, native compiler or
the Hyper-V guest. The host scratch directory was also verified absent.

`tools/qualify-storage.py` and `tools/capped-scratch.ps1` describe the fixed host
proof, not a portable guest setup command. Do not copy their host identity/path
assumptions into the guest or rerun them merely because a guest connection is
unavailable. Final capped runner/compiler qualification and live upstream AIDE
integration remain open.

Before requesting elevation, the proof reads the live Windows process snapshot.
An existing `consent.exe` in the current session, or one whose session cannot be
queried, blocks an additional request. Complete or cancel the relevant Windows
prompt at the host console before retrying a necessary host proof. Stopping a requesting process does not
prove that Windows retired its consent process. The tool never terminates those
processes or assumes that they belong to DiskEd. Admission refusals are retained
separately from the earlier virtual-image creation/cleanup receipt.
The setup helper also holds a named mutex throughout creation, mounting, its
finite lease and cleanup. Late approvals cannot make two helpers race over the
same image. Cancelling an obsolete DiskEd prompt avoids starting a helper after
its controller has exited; identify the relevant command at the console.

Before creating a context pack, check its complete upper bound:

```text
python tools/workspace.py check --planned-bytes 12582912
```

Run a complete build/test campaign in one managed command. `{work}` in its arguments
is replaced with a newly owned temporary directory; `DISKED_WORK_ROOT`, `TMP`,
`TEMP` and `TMPDIR` identify that same directory. The directory is deleted when
the command finishes, including failure and interruption. An identified leftover
from a hard termination is cleaned before another campaign starts.

If cleanup cannot finish, the runner fails closed and refuses to create another
workspace. It does not change attributes shared with another hard link; such a
leftover needs explicit review before the next run.

```text
python tools/workspace.py run -- python -c "import os; print(os.environ['DISKED_WORK_ROOT'])"
```

Only one campaign may run at once. DiskEd checkouts share the same admission lock
on the user's temporary volume. Each campaign has a 1 GiB working-data budget, a
20,000-entry limit (including directories and links) and a 20 GiB free-space floor
on both involved volumes. Sparse fixtures are
charged by allocated data; links are never traversed by the storage scanner.
These are watchdog budgets, not a filesystem quota. Commands still need bounded
writers and must use the owned output directory. Do not bypass the runner or
increase limits after a refusal. Reduce the working set and clean intermediate
data between phases.

The CMake preset is unavailable without a managed workspace. The root build also
refuses output in the source checkout or outside the managed directory before
compiler discovery. Historical evidence and recipes keep their original paths;
adapt their working outputs and retention before running them again.

Keep compact review results once under `.aide/evidence/`. Rebuildable objects,
duplicate raw captures, complete old checkouts and abandoned virtual environments
are disposable. Compression is not permission for unlimited historical caches.
Validate the runner with `python -m unittest discover -s tests/tools -v`.

Inspect emergency scratch cleanup without deleting anything:

```text
pwsh -NoProfile -File tools/clean-scratch.ps1
```

After stopping the owning workers, add `-Delete -WorkersStopped` to opt in.
The [reviewed helper](../tools/clean-scratch.ps1) resolves this checkout's exact
Git root and fixed `.aide-local` target. It refuses tracked scratch files and
linked ancestors, skips links, nested/bare repositories, registered worktrees
and read-only files, and deletes ordinary files and empty directories individually.
It creates no archive, changes no ACLs/attributes and does not terminate workers.
It is not safe against concurrent replacement of paths: worker quiescence remains
a prerequisite. Inspect registered worktrees separately before using Git's
worktree removal; this helper deliberately does not force their removal.

Exit 0 means the traversal completed, 2 means some entries were preserved or could
not be processed, and 1 means refusal/error. Its JSON output records logical file
bytes and actual volume free space separately; other projects can change the
volume concurrently. A partial result must never be reported as an empty folder.

For DE-W105, [the Win32 fixture preparer](../tools/ntfs-win32-fixture.py) replaces
the fixture-generation portion of the historical supplement. It reads a fresh
CMake File API codemodel for the same checkout from the managed workspace and
generates at most 128 KiB there: the CMake fixture, twelve header probes and a
hashed input/generated-file manifest. It retains all eighteen test groups and
nine executable targets, including distinct normal/fault variants. It copies no
checkout, launches no compiler/test and grants no native execution authority.
It refuses missing headers, mismatched metadata, linked/escaping paths and
oversized input/output before creating its output directory.

Generate the fresh codemodel only after the native storage gate is satisfied.
The generated manifest binds fixture-generation inputs; it is not the complete
work-unit/test-helper execution closure or qualification evidence. Future native
execution and compact retention still need a bounded campaign; historical
unbounded orchestration must not be rerun to produce the missing codemodel.
