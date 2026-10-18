# Guest storage boundary checkpoint

Base: `3a133e50b121bf19b62b5fe1325e9de644f6c49c`, branch `dev`, work `DE-W105`.
This is execution-environment evidence. No DiskEd product build or test ran.
The owner's primary/spare policy remains **Agents / Codex**; Codex was not used
for routine access and its account and profile remain present.

The portable Python 3.14.7 copy passed isolated imports and per-file verification:
612 source files, 37,630,185 content bytes. The retained guest directory includes
its small manifest; transfer archives were deleted. No installer, global PATH,
registry or host UAC change was made.

Both final proofs passed with the same current worker/qualification source:

| Check | 32 MiB | 512 MiB |
|---|---|---|
| New fixed VHD inside the verified guest | Pass | Pass |
| Footer UUID, associated non-system disk, partition binding | Pass | Pass |
| Deliberately wrong image/disk identities refused | Pass | Pass |
| Actual disk-full error | 112 | 112 |
| Worker elevation flag | 0 | 0 |
| Own temporary-file create/read/write/delete | Pass | Pass |
| Outside writes, descendant writes, backing-file write-open denied | Pass | Pass |
| Payload removal restores filesystem free space | Pass | Pass |
| Owned job termination releases worker/held file | Pass | Pass |
| Abrupt Python controller death retires worker and profile mapping | Pass | Pass |
| Coordinator window station restored | Pass | Pass |
| Image detached/deleted, source/report copy removed | Pass | Pass |

The small proof keeps its original 64 KiB write-through allocation blocks and
25-second worker deadline. The first larger proof hit that inherited deadline;
its failure is retained. Before retrying, `expected.json` records the reason for
using 1 MiB write-through blocks and a finite 90-second deadline at 512 MiB.
Capacity, allocation-error, confinement and cleanup assertions remain required.
The larger proof wrote 517,996,544 bytes before error 112; its bounded attempt
limit was 640 MiB. Passing this proof does not authorize larger storage.

An administrative coordinator now derives a restricted primary token with
Administrators deny-only, removed privileges, and a usable user owner/default
ACL. AppContainer restrictions are also applied. The worker remains suspended
until assigned to its owned job. An explicitly selected private window station
fixes native-module initialization in the PowerShell Direct service session;
ordinary host callers keep their existing path. The coordinator restores its
original station and never modifies a shared station's ACL.

The attached device grants Modify to the three fresh campaign package SIDs.
The earlier read/write/execute device grant lacked DELETE and caused temporary
file operations to fail. The backing-file ACL remains unchanged; the worker's
attempt to open it for writing returns access denied. Windows documents the
separate device descriptor in [AttachVirtualDisk](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/nf-virtdisk-attachvirtualdisk).
Restricted own-token launches follow [CreateRestrictedToken](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-createrestrictedtoken)
and [CreateProcessAsUserW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessasuserw).

`proof-32.json` and `proof-512.json` bind every transferred source by hash and
retain actual outcomes. `cleanups.json` binds removal observations to image UUIDs.
`qualified-setup.ps1` retains the exact setup bytes used for both final proofs.
Subsequent review corrected the current setup's early-interruption guard: once
a runner has started, missing confirmation of its termination preserves the
bounded image, even if no exit receipt was written. `retirement-guard.json`
records all four pure guard cases; no additional media were created for that
check. Full remote-session interruption remains unverified.
`final-observations.json` records account configuration, host/guest free space,
VM memory, existing checkpoint and backing-file length. Deleting guest files
does **not** establish host backing-file shrinkage: it grew from 23,004,708,864
to 28,809,625,600 bytes since the previous checkpoint. This shared-guest growth
is observed, not attributed wholly to DiskEd. No compaction, checkpoint removal
or shared-VM restart was performed. Disposable file removal is not a claim that
those 5,804,916,736 host bytes were reclaimed.

Superseded failures and early successful receipts are retained exactly once in
`observations.json.xz`; `observations-index.json` records original hashes/sizes.
The 99,002 original bytes round-trip to the verified 9,968-byte archive. The
archive stores a JSON mapping from original names to `sha256` and exact `utf8`.
Use the index and decompress when investigating; do not rerun the one-time
archiver or old failed commands as ordinary setup.

The first full specification-suite wrapper stopped at its 240-second deadline.
The archived `spec-checks-first-timeout.json` preserves its incomplete receipt: only dependency
setup, index and structural check completed; no suite outcome or raw timeout
diagnostic was retained. The corrected wrapper records failures/timeouts and
allows the full suite a finite 900 seconds on the shared host. Its final outcome
belongs in `spec-checks.json`; an incomplete receipt is not a passing test.

Final results: 104 tooling tests (one expected skip), 253 specification tests
(two expected skips), 1,323 structural checks and 420 manifest entries passed.
The context pack bound 1,203 inputs, verified successfully and occupied
17,687,582 bytes; `context-cleanup.json` records its removal with no skipped
entries. Its separate artifact budget initially refused 8 MiB; the successful
retry selected explicit 2 MiB prose and 24 MiB artifact budgets, with a 28 MiB
complete reservation below the unchanged 32 MiB aggregate ceiling. No inputs
were truncated and the passing suites were not repeated for that retry.

`spec-checks.json` is the compact readable coordinator receipt. Exact outputs,
the first timeout receipt and the artifact-budget refusal are retained once in
the verified 7,064-byte `coordinator-observations.json.xz`, using the same JSON
mapping/UTF-8/hash format as the earlier archive.

Bounded commands actually used:

```text
python -B tools/workspace.py run -- python -B .aide/evidence/2026-10-18-guest-capacity/copy-runtime.py
python -B tools/workspace.py run -- pwsh -NoProfile -File .aide/evidence/2026-10-18-guest-capacity/run-proof.ps1 -SizeMiB 32
python -B tools/workspace.py run -- pwsh -NoProfile -File .aide/evidence/2026-10-18-guest-capacity/run-proof.ps1 -SizeMiB 512
pwsh -NoProfile -File .aide/evidence/2026-10-18-guest-capacity/clean-proof.ps1 -SizeMiB 512
python -B tools/workspace.py run -- python -B .aide/evidence/2026-10-18-guest-capacity/validate-tools.py
```

The runtime command refuses an existing installation; do not repeat it. Proof
setup is restricted to the fixed guest/Agents/directory and refuses leftovers.
These scripts are retained finite bootstrap recipes, not a portable deployment
framework. Host tooling tests are necessary to validate the host coordinator and
its ordinary-token behavior; they do not mount media or run DiskEd.

Actual compiler execution, clean build and native tests remain next. The guest's
compiler files match the pin, but file identity is not compiler qualification.
Do not rerun historical unbounded recipes. All original platform/storage,
owner-acceptance and release gates remain separate. Remote-session loss or host
controller death is not qualified by the inner Python-controller death case.
