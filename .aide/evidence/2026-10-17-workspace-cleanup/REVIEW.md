# Emergency scratch cleanup and script review

The user requested cleanup and review of the supplied PowerShell script before
execution. The native DiskEd goal is paused. The downloaded script was read, not
executed or overwritten. Earlier NTFS advice is historical context, not authority
to resume its campaigns.

Original: `E:\Downloads\DiskEd-emergency-scratch-cleanup.ps1`, SHA-256
`d834e2fe558435af5763606c55a3d913bd1f88e0aaae5cbd5a238e231cc4aa215`.
The reusable replacement is `tools/clean-scratch.ps1`; its tests are
`tests/tools/test_clean_scratch.py`.

## Findings and changes

The original defaults to inspection, verifies the fixed Git root and tracked-file
boundary, skips reparse points and `.git` checkouts, and uses individual file and
empty-directory deletion. Those are useful safeguards to retain. Its
`-WorkersStopped` flag asserts quiescence; it does not establish it.

The replacement additionally:

- Returns exit 2 for partial/skipped cleanup and 1 for refusal/error.
- Resolves the owning checkout from the tool location and verifies its exact Git
  root; accepts no arbitrary deletion target. Refuses a caller inside scratch.
- Preserves registered worktree roots even when `.git` is missing, plus nested
  and bare repositories. Worktree cleanup remains a separate Git/state review.
- Checks path containment and linked ancestors, streams directory entries and
  caps retained skip diagnostics at 20. It does not load a giant directory list.
- Preserves read-only files and their attributes, all links, ACLs, tracked source
  and Git metadata. Directory deletion requires emptiness, never recursion.
- Produces compact JSON with logical bytes and actual volume free observations
  separately, without changing the caller's directory or creating archives.

This is ordinary maintenance for quiescent trusted development output. Checks
followed by path-based deletion cannot prove safety against concurrent hostile
path replacement. Neither script establishes worker quiescence, a storage quota
or an allocated-byte accounting claim.

## What failed

The prior workflow retained repeated build trees, source checkouts (including
historical evidence), environments, generated fixtures and raw captures between
attempts. There was no enforced aggregate working-set or retention boundary.
Promises to clean up were not implemented as admission and cleanup rules.
That workflow failure is the agent's responsibility; passing native tests did
not justify exhausting a shared volume.

Earlier emergency passes had already deleted portions of `.aide-local` before
this script review. Their interrupted progress counters are not a complete
inventory and cannot retroactively prove that every deleted checkout was clean.
The actual root checkout's uncommitted changes are retained. Remaining registered
checkouts are reviewed in `worktree-review.json` before further removal.
Obsolete one-off cleanup executables/scripts were removed, rather than retained
as alternative recipes without these safeguards.

## Reuse and remaining gate

The safe cleanup patterns and small metadata policy are incorporated into DiskEd's
AIDE adapter instructions and input registry. `tools/workspace.py` adds one
campaign across DiskEd checkouts on the user's temporary volume, a 32 MiB context
budget, a 1 GiB working-data budget, a 20,000-entry limit (including directories
and links), 20 GiB free-space floors, process ownership and cleanup after
success/failure/interruption. CMake refuses unmanaged output before compiler
discovery. Limits were not raised to the larger values suggested in the supplied
review.

These are polling watchdog and admission controls, **not an OS quota**. A fast
writer can overshoot between polls and a command can still write outside its
owned directory. No actual host-enforced allocation denial, no-spillover boundary
or upstream AIDE runtime integration has been demonstrated. Native development
remains paused pending that demonstration. No elevation, filesystem provisioning,
mounting or upstream AIDE changes are authorized implicitly by this cleanup.

Completed historical x64 W105 observations were compacted and verified before
the latest script-review request, in `retained-result.json` and its 2.1 MiB archive.
They qualify their recorded source revision only. The private Win32 supplement
and qualification of the amended build gate remain unrun. There is no new native
acceptance, main promotion or release claim.

## Observed completion

`cleanup-result.json` records `.aide-local` absent with zero files/bytes and about
218 GiB free on D:. The volume change is an observation, not exclusive attribution.
All 38 remaining Git worktree registrations were removed (31 clean checkouts and
seven already absent paths). Another 96 standalone source copies were reviewed
and removed. One partial clone had lost `.git/HEAD`; Git silently discovered the
parent repository instead. Its surviving source was checked against historical
revision `829de03c` using a separate temporary index; the main index was untouched.

The one-off clone deletion preserved read-only attributes on surviving hard
links, using the installed SDK's `FileDispositionInfoEx` and its read-only deletion
flag, after a tiny real hard-link preservation check. Microsoft's
[file disposition documentation](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntddk/ns-ntddk-_file_disposition_information_ex)
describes the deletion flags. The exact executed emergency code is retained as
passive text in `executed-clone-cleanup.ps1.txt`, not as an alternative cleanup
entrypoint. The reusable helper still preserves all read-only files.

- Final workspace/build-boundary/cleanup suite: **67 run, 66 passed, one skipped**.
  Windows PowerShell 5.1's effective `Restricted` policy blocks script execution;
  that runtime remains unverified. Its parser check passed. No policy was changed
  or bypassed. Actual helper execution was tested with PowerShell **7.6.7** on
  Windows **10.0.19045**, as `BLACKGLASS-WIN1\Jules`.
- Full specification-tool suite: **253 run, 251 passed, two existing symlink
  privilege skips**. The final shared-lock change was subsequently covered by
  the 67-test tooling run and structural/freshness checks.
- Index, structural validation, manifest generation and verification passed.
  Canonical text was normalized to LF before the final manifest was generated;
  raw execution logs and the binary archive were preserved.
- The full validation workspace peaked at **52,405,955 bytes** and was removed.
  The final shared-lock regression and canonical-freshness workspaces were also
  removed. Dependency staging used only the owned temporary directory, with no
  retained environment or package cache.

The runner also counts empty directories, rejects dangling links and refuses to
clear attributes shared by a hard link. Cross-process admission was tested with
two DiskEd checkout identities. Polling overrun tests demonstrate detection and
termination **after** allocation, not hard denial of allocation. The hard storage
boundary gate remains unsatisfied and the native goal remains paused.
