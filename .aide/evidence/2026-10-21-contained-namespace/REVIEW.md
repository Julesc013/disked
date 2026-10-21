# Contained native namespace: integration review

Status: the full x64 gate **passes all 180 groups** at `c0eab59b`, with
69 standalone headers, 14 executable/import observations, six actually reviewed
GUI captures and verified owned cleanup. Repository checks are recorded
separately. This is a selected DE-W030 slice,
not full-unit, owner, public-provider, physical-storage or release acceptance.

## Source and contract review

The eight changed library files add an explicit compiled `NamespaceBackend::Native`
through the existing observation host, namespace graph and inventory publication.
`prepare_native`/`start_native` construct an empty provider-input object. A distinct
child role, schema, scope and attempt prefix prevent fixture input from selecting
native effects. Old injected entrypoints still refuse native and mixed tables.
Native namespace profiles reject payload/effects combinations.

Graph projection checks the selected native/fixture context and snapshot binding.
Backend selection is immutable for an adapter; default constructors remain injected.
Complete/partial frames, retained immutable publications and actual reader retirement
retain their existing separate meanings. The dispatch checkpoint is not proof of
kernel API entry, cancellation acknowledgement or completion. Namespace names and
mounts do not establish physical identity, topology or authority to mutate storage.

The product entrypoints and fake-only inventory defaults are unchanged. There is
no new public command, arbitrary executable/callback selection or broker endpoint.
No general source restructuring or stable-ID change was needed.

## Revision-bound evidence

- Focused source `57578ab08541e22f6cdfadc8c9db43ff182f59bb` passes 15 fixed cases
  on each of x64 and Win32, plus the existing adapter/worker/graph regressions.
  [Focused review](FOCUSED-REVIEW.md) and [closed replay](capture/replay.json)
  retain the exact boundaries, earlier failures and cleanup.
- Private Win32 source `8bc7947147c46801687632ae02f40fac4932d47d` passes its
  18 groups, 12 standalone headers and nine executable/import observations.
  [Replay](private-win32/review.json) checks every retained archive member and
  owned cleanup. This is not a full Win32 product or XP qualification.
- Full x64 source `54bc8cd8a844344336ce8485202a108e5c04d784` built successfully,
  with 69 headers and 14 executable/import observations, but fails four of
  180 groups. [Closed failure review](full-native/failure-review.json) verifies
  all 4,378 archive entries and their hashes. This is not a passing full gate.

[Input comparison](input-applicability.json) establishes unchanged native product,
test/fixture and build inputs between these native revisions. It explicitly
excludes changed host tooling and does not claim identical coordinators or
metadata. Each receipt retains its actual tested revision.

The first full x64 attempt at `8bc79471` reached its original 1,800-second build
deadline before running product groups. Its [failed receipt review](build-timeout-8bc79471/failure-review.json)
and cleanup are preserved. A prolonged tracked-linker wait was observed; its cause
is unresolved. The next clean build uses the [predeclared tracking setting](clean-build-profile.json)
without changing compiler semantics, test expectations, budgets or deadlines.
That build completed, but source `54bc8cd8` did not pass all native tests.
The later complete `c0eab59b` run supersedes its qualification result while
preserving the original failed evidence.

The four historical `54bc8cd8` failures were:

| Group | Actual observed failure |
|---|---|
| `frontend.fat_tree_sessions` | JSON text read from a changing GUI control was truncated; the length/read race is now covered by an independent growing-control regression and a single bounded snapshot read |
| `frontend.gui_windows` | A window message timed out during oversized/multiline input refusal testing |
| `image.fat_commands` | FAT32/4096 inspection returned `request_wait_expired`, unknown/exit6 instead of the expected completed result |
| `image.fat_retention_commands` | Reader startup remained unresolved; the original worker was retired and returned an unknown outcome |

The GUI text race is repaired without swallowing parse failures. The other
three timing symptoms did not recur in the complete current run; their causes
remain unestablished. Assertions, deadlines and resource limits are unchanged.
The `a8b013b6` focused attempt remains failed because its GUI companion binaries
were omitted. The corrected dependency selection has an independent CMake-command
regression. [Repair history](REPAIR.md) and [focused failure audit](repair-focused/review.json)
retain that setup error; no attempt is relabelled as a pass.

[Fresh cleanup](full-native/cleanup-live.json) finds no owned process, actor,
profile, hive, qualification root or scratch; owner queries all succeeded. The
512 MiB cap peaked at 440,646,289 allocated bytes. The raw archive is 2,547,572
bytes for 916,433,851 original bytes; it is streamed, not bulk-extracted. The host
workspace peaked at 87,702,468 bytes and was removed. The shared VM remains intact.

The complete [current native review](repair-native/native-detail-review.json)
verifies all 4,374 archive entries and hashes: 913,589,580 original bytes retained
as one 2,575,132-byte archive. Source `c0eab59b` passes 180/180 groups, 69 headers
and 14 executable/import observations. The build took 1,232.89 seconds and the
test commands 4,310.59 seconds under the original limits. All four prior failing
groups pass in this same build. This is not a combination of separate runs.

[Visual review](repair-native/visual-review.json) records actual inspection of all
six current PNGs, after pixel/source/receipt checks. It does not establish full
text recognition, accessibility or other-host qualification. [Fresh retirement](repair-native/cleanup-live.json)
finds no owned process, actor, profile, hive, qualification root or scratch, with
zero inaccessible owner queries. Peak allocated scratch is 442,075,523 bytes
within the 512 MiB cap; host workspace peak is 91,454,011 bytes and it was removed.
Only six hash-verified PNGs were extracted into a managed host workspace for
review; that workspace and its small metadata pointer were removed.

Repository validation in `validation.json.xz` passes 253 specification,256
tooling,13 native-reader and108 differential tests:630 run with eight declared
skips (2+1+0+5). Structural/source-map checks, all required evidence replays,
manifest verification and complete work-context generation/verification pass.
Its host workspace peaked at65,311,755 bytes and was removed. These results bind
the prepared metadata inputs; final handoff/synchronization bookkeeping receives
separate finalization checks. They are not replacement native execution evidence. The source-bound context carries actual contracts and
artifacts, with the existing no-truncation and byte-budget rules.

## Reproduction and retention

The exact tested source is the native receipt's revision, not a fictional latest
combined run. Its launcher is invoked through `tools/workspace.py run` in the
managed environment, using the existing Windows 10 guest, Agents coordinator,
qualified restricted workers and the 32/512 MiB scratch profiles. Retained-output
guards refuse accidental reuse. Do not run historical unbounded recipes or copy
the whole evidence tree into scratch.

Native build objects and generated images are disposable. Retained archives,
entry manifests, artifact hashes, commands and compact results preserve the
evidence without retaining a build tree. Review archives by bounded streaming;
do not expand the full raw archive to view a few PNGs.

## Open scope

DE-W030 remains active. Native physical identity/layout/topology, broader
provider/service coverage, public frontend admission and other host profiles
remain unqualified. Production journal, broker, mutation/recovery, historical
platform, owner/licensing and release decisions retain their existing gates.
The original all-platform/storage 0.1 scope is unchanged. No separate DiskEd 1.0
completion contract has been baselined. The owner authorizes dev/main source
synchronization and explicitly withholds release/tag publication.

## Continuation on another machine

The owner requests repair and requalification before dev/main synchronization,
then a pause. Complete REPAIR.md before promotion; do not start another feature
work unit before that handoff. Resume only on
the owner's instruction, from the identical remote branch checkpoint recorded
in the integration receipt and the current programme.

Read root `AGENTS.md`, the programme, this review, `docs/project-status.md` and
the typed handoff. Preserve base `40ac8ec` and the original release scope. Resolve
DE-W030's remaining native inventory/public-provider contract; do not restart the
bootstrap programme or reinterpret private qualification as owner acceptance.

Inspect the new machine's actual identity, toolchain, free space and available
guest connection before native work. The recorded Windows 10 guest/toolchain
results apply to their named profile. This host's DPAPI-protected credential and
Hyper-V configuration are machine-specific; do not copy credentials or assume
unattended access on a different host. Keep ordinary metadata checks bounded,
qualify any new execution environment, and preserve the existing storage and
physical-media authority gates. Shared guest maintenance is not routine cleanup.

Retained Git evidence and generators are sufficient for continuation; disposable
builds, expanded archives, temporary accounts and context packs are not a transfer
bundle. The final cleanup receipt, not this requested pause, establishes their
actual retirement.
