# Storage setup: partial qualification

Base: `d103a302fbc234de940033c45b070361ca31fa22`, with the working changes
identified by retained source hashes and the eventual development checkpoint.
The user granted bounded local scratch setup and shared-VM testing. The full
original DiskEd 0.1.0 programme remains unfinished.

## Working controls

The Windows worker uses an AppContainer with no additional capabilities, its own
desktop, and an explicit inherited-handle list. Launch is suspended until its
process belongs to the caller's kill-on-close job. Only its fresh work directory
receives the package SID's writable ACL. The temporary package profile points
into that work directory; it is removed after the job stops.

A bounded journal belongs to the controller, outside the worker's writable
directory. Actual controller termination was tested: its descendants retire,
the profile alias remains discoverable, and recovery removes the alias and
registration before the workspace can be discarded. Ambiguous creation state
blocks reuse and preserves the journal for review. It does not authorize deleting
an arbitrary user's profile. These are development controls for trusted tools,
not a qualification against hostile programs or every Windows broker.

All 94 tooling tests run: 93 pass and one existing Windows PowerShell 5.1 runtime
test is skipped because of execution policy. Eight new actual Windows isolation
tests cover outside-write denial, inherited restriction, non-elevated AppContainer
identity, both diagnostic streams, controller/descendant termination, profile
retirement/recovery and refusal of uncertain ownership. Five additional refusal
checks cover ordinary-volume admission, directory/volume confusion, bounded
metadata, unknown arguments and an ungranted setup size. The full log is
`storage-final-tooling.log`. Its managed workspace was removed; sampled peak
working data for the final tooling/freshness run was 497,223 bytes. A successful watchdog run is not a hard quota.

The full specification suite also ran: 251 pass and two existing symlink-privilege
skips (253 run). Final structural validation reports 1,323 checks, and manifest
generation/verification pass. Full-suite sampled working data peaked at
52,665,568 bytes and was removed. The final launch initialization and validator
catalog entry received fresh tooling, setup-refusal and structural/manifest
checks; the 253-test suite was not repeated for those final changes.

## Actual setup result

The first elevation request did not complete. Only its identified pending
controller was stopped; no elevated setup, image or mount was observed. Whether
a UAC dialog was visible at the VM console was not independently established.

The ordinary user-context attempt then created a new fixed 32 MiB VHDX. Its
backing file occupied 37,748,736 bytes (36 MiB). Windows refused `Mount-VHD` with
`0x80070522`, "A required privilege is not held by the client." The helper deleted
its exact owned image. The retained structured receipt is `capped-storage-32.json`.
The scratch directory and `.aide-local` were absent after cleanup.

This establishes creation/refusal/cleanup for a tiny image. It does **not** prove
filesystem allocation denial, a working mounted boundary, final 512 MiB scratch,
compiler compatibility or no spillover for native campaigns. The eight worker
tests used ordinary tiny fixtures, not a capacity-limited filesystem.

## Next bounded action

When the already-authorized Windows elevation request can complete at the VM
console, run this checkout's source-bound proof through the existing runner:

```text
python tools/workspace.py run -- python -B tools/qualify-storage.py --elevate
```

The fixed-path setup helper creates only a new blank image, binds partitioning
and formatting to that exact virtual image, and retires it after a nonce-bound
release or finite lease. It accepts no arbitrary command or source disk. Product
workers stay unelevated. Keep normal native campaigns stopped until actual
allocation denial, outside-write denial and interrupted cleanup pass, then
qualify the selected final scratch and compiler/test cohorts.

The watchdog still checks the two host backing-volume reserves. The proof checks
the tiny filesystem's capacity separately. Ordinary native runner integration,
final capacity qualification, DE-W105's remaining Win32 checks and original
all-platform/storage 0.1.0 completion remain open. Upstream AIDE is still a pinned
source/schema observation, with no live runtime integration or admission claim.

Primary agent review: the local setup grant overrides the former missing-grant
blocker. It does not override the requirement for actual storage proof, confer
physical-device/customer-media/release authority or accept the implementation.
