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
available host memory. Its current configuration uses two virtual CPUs, 2 GiB
startup, 1 GiB minimum and 3 GiB maximum dynamic memory. Automatic checkpoints
are disabled; the pre-existing checkpoint is preserved. The original settings
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

### One-time guest connection setup

Use PowerShell Direct with the existing VM ID, rather than opening network
listeners or sharing the host's source drive into the guest. In a normal Jules
PowerShell 7 window on the host, run:

```powershell
pwsh -NoProfile -File tools/connect-vm.ps1 -SetupCredential
```

Enter a guest account and its password in that local window. The VM currently
shows `Codex` and `Jules` accounts; do not assume either password is known, blank
or the same as the host password. A PIN is not a password. If the password is
unknown, cancel; do not reset an existing shared account or guess credentials.

The helper verifies a PowerShell Direct connection to the fixed VM ID and checks
the guest's computer/model identity before saving anything. Windows encrypts the
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
After the owner finishes, inspect the guest `Codex` account's Administrators
membership, `EnableLUA` and new boot identity through the verified connection.
Until then, the change is unverified. This is the Windows
[UAC policy](https://learn.microsoft.com/en-us/windows/security/application-security/application-control/user-account-control/settings-and-configuration),
not simply the notification slider. Retain explicit test-token observations;
an administrative test pass does not establish standard-user behavior.

The Codex guest account is shared with other agents. Use distinct workspaces,
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
