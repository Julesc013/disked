# DE-W107 native/API checkpoint

Exact source `6a688b79ba3639ff5b65582617c3ea676674254c` collected all four native
and four Windows API observations. **The campaign is incomplete: four declared
Disk Management UI observations remain not_run.** This is a tested development
checkpoint, not public Windows-provider, product, owner or release admission.

The [receipt](receipt.json.xz) records 2026-10-21 03:40:18–03:40:49 UTC on the
existing `Windows 10` guest, build 19045.7548, x64, with the `Agents` coordinator.
MSVC 14.44.35207/19.44.35228 and SDK 10.0.19041.0 built the actual C90 MBR/GPT
probes and private SDK observer with static CRT. Native observations ran as a
fresh restricted ordinary Medium/nonadministrator/non-elevated actor. Installed
component/header file hashes, compiler/linker and executable hashes, source
inputs and the emitted Win64 SDK ABI are retained. These identify this profile;
they do not qualify another Windows build, architecture or loaded-kernel source.

## What was observed

| Fixture | Native byte interpretation | Windows layout-query projection |
|---|---|---|
| Valid MBR | Two nonoverlapping entries | Same extents/types |
| Valid GPT | Both valid copies agree | Matches both candidate projections |
| Damaged primary header CRC | Primary invalid; valid backup retained | Reports a layout matching the valid backup projection |
| Conflicting valid GPT copies | Two valid candidates; first start 2048 versus 2049 | Matches the primary candidate's projection |

The damaged-primary observation does **not** establish how Windows obtained its
layout: accepting primary fields despite their CRC and reading the backup could
produce the same visible projection. No claim of repair, fallback algorithm or
undocumented backend is made. The conflicting case establishes the projection
reported in this run; it does not resolve the independent native conflict.
Candidate-relative agreement is distinct from consistency of both GPT copies.

These are immediate documented `IOCTL_DISK_GET_DRIVE_LAYOUT_EX` observations
following read-only attachment, not Disk Management presentation or a claim about
all provider refresh states. A Windows refusal/disagreement is retained as a
finding rather than changing the authored byte facts or becoming a failed vote.

## Identity, execution and effects

Twenty-five owned execution-port calls include the original eight byte-I/O
controls, four native build steps, two native protected-memory guards, one SDK
observer build, its ABI check, an invalid-handle refusal and eight fixture calls.
Original capacity/outside-write/inheritance/abrupt-interruption controls also pass
in the 32 MiB filesystem. Jobs retain 256 MiB commit/eight-process limits. No
host test media, shared-account/UAC changes, reboot or VM reconfiguration occurred.

Each native participant received its own ordinary-file copy; only the required
sectors entered its request. The full 4 MiB source identity/hash was checked
before/after and the copy removed. Each API participant received a separate fixed
VHD with exactly those initial payload bytes, its own virtual-disk UUID, verified
backing-file identity and footer. Administrative guest setup temporarily enabled
the existing volume-management privilege, then restored its prior state.

The VHD was attached read-only, without drive letters or permanent lifetime.
The coordinator resolved its device from the held verified virtual-disk object,
opened `GENERIC_READ`, revalidated the attachment and delegated only that handle
to the already assigned suspended observer. A transient disk number alone never
selected a target. The actual one-byte write attempts failed with zero bytes;
raw length/geometry/device/layout responses and Win32 errors were retained.
API success, evidence validity and candidate comparison remain separate fields.

All four payload **and full VHD file** hashes were unchanged after the actual
queries and detach. Each held object was rechecked before retirement; detach
succeeded, attachment-path lookup then returned error 55, all handles/jobs
retired and each owned image was removed before the next case. This does not
claim that Windows generated no registry, device-history, service or log effects,
nor that hashes alone establish acquisition/application consistency.

## Replay, validation and cleanup

[Replay](replay.json) verifies the single [10,376-byte archive](retained.tar.xz),
all 43 entries (679,866 original bytes), staged controller aliases, fixture/source
identities, native requests/checks/projections, raw SDK field decoding, delegated
handle/PID binding, VHD reconstruction from known payload plus actual footer,
per-case effects and the incomplete expected set. No retained command is executed.
It explicitly finds eight observations and four missing UI tuples.

The [full host pass](validation.json.xz) ran 253 specification tests (two skips),
241 tooling tests (one skip), 97 differential tests (five skips), all 1,328
structural checks, source-map coverage and manifest freshness with unchanged
tested inputs. [Preflight](preflight.json.xz) records five subsequent pre-execution
input changes and 99 passing differential tests (five skips). They remove
an unjustified Windows-agreement assertion, reject invalid/empty candidate matches,
separate reference attempts and bind controller aliases; no actual Windows result
or fixture expectation was changed to make a test pass.

The [first native attempt](compile-failure-90aedee2/review.json) failed at observer
compilation because Windows' `min`/`max` macros collided with standard C++ names.
Its evidence and cleanup remain intact. The sole following source repair defines
`NOMINMAX` before `windows.h`; the actual successful compile/ABI/guard/query run
qualifies that correction. Product implementation and historical evidence are
unchanged. No full current product suite or independent Linux/sanitizer campaign
was rerun or claimed here.

[Cleanup](cleanup.json.xz) and [fresh observation](cleanup-live.json) confirm no
owned actor/profile/process, qualification root or scratch drive remains. Host
launch/replay workspaces were removed; `.aide-local` is empty. The VM backing
file's logical length remained 34,580,987,904 bytes; allocated backing growth was
not measured. Disposable binaries, raw images, objects and extracted captures
were removed; only bounded source/commands/results/hashes/raw observations remain.

## Adoption and next work

The findings reinforce existing DE-032/DE-034 ownership: retain independent raw
partition candidates beside OS-reported layouts; never make Windows selection
authority to erase a conflict or admit mutation. The fixed native expectations,
raw-response checks and replay are regressions for this exact experiment.
No broader provider behavior is added from one reference run.

Continue DE-W107 with a separately demonstrated bounded MMC/UI profile and four
actual UI observations from independent initial copies. Coordinate/isolate the
desktop and profile/output paths without changing shared users or security policy.
API-only evidence cannot close that gate. Original all-platform/storage 0.1.0,
owner acceptance, physical-media, production-writer/recovery and release gates
remain unchanged and incomplete.
