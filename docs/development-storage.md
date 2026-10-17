# Development storage

`.aide-local/` is small disposable context/metadata, with a 32 MiB aggregate limit.
Builds, checkouts, dependency environments and raw probe dumps do not belong there.
The [shared instructions](../AGENTS.md) and [workspace runner](../tools/workspace.py)
own the development rules and their enforcement.

Native development is currently paused at the user's request. A hard filesystem
boundary has **not** been provisioned or demonstrated. The watchdog described
below does not deny filesystem allocation and cannot prevent a command from
writing elsewhere. Cleanup and tiny tooling checks can proceed; normal native
campaigns must remain stopped until that separate gate is satisfied.

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
