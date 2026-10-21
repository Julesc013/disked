# DE-W107: complete bounded Windows reference set

The [combined replay](capture/combined-replay.json) verifies all **12 frozen
observation tuples**: four native candidate sets and four actual Windows API
queries at `6a688b79`, plus four actual Disk Management UI Automation captures
at `68989ab2`. These are separate identified participant copies and executions,
not a fictional single latest-build run. Both used the same recorded Windows
10 Enterprise build 19045.7548 and compiler/linker identities. No product
provider, physical hardware, owner or release admission follows.

The final UI campaign ran 21 October 2026, **05:16:41–05:17:13 UTC**, in the
existing Windows 10 guest. Routine coordination used Agents/session 3. The
restricted ordinary worker passed the original capacity, outside-write,
inheritance, interruption and eight native byte-port controls. It compiled the
private observer and proved its capped profile. The same disposable account
then obtained a fresh administrator token for the separate reference role. Its SID,
administrator/elevation/restriction state, session, private desktop, actual
profile, known folders and temporary paths were independently observed. It is
not claimed to have token-enforced write confinement.

## Observations and adoption

| Case | Actual Windows API projection | Actual accessible Disk Management volume rows |
|---|---|---|
| Valid MBR | Two 1,024-sector partitions | Two `1 MB` rows, `Healthy (Primary Partition)`; first filesystem field `RAW`, second blank |
| Valid GPT | Two agreeing native copies; API projection matches both | Two `1 MB` rows, `Healthy (Basic Data Partition)` |
| Damaged primary GPT CRC | API projection matches the valid backup's extents | Same two rounded capacities/basic-data status labels |
| Individually valid conflicting GPT copies | API projection matches the primary; native reader retains both candidates | Same two rounded capacities/basic-data status labels |

The API's ordinary partitions contain 524,288 bytes. The conflicting backup's
first partition would contain 523,776 bytes. The UI strings cannot distinguish
those geometries. This does not establish a general Windows rounding rule.
The damaged-primary observation cannot prove how Windows selected metadata;
identical extents could also be obtained by ignoring that primary CRC. No
captured UI label resolves the conflicting copies or proves filesystem health.

This is **UI Automation/LegacyIAccessible evidence**, not screenshots. The
accessible volume-list data were captured; the target disk's graphical
nameplate was absent from the captured accessibility tree, and no scrolling was performed.
Offscreen state is retained, and no claim about actual pixel rendering or all
properties dialogs is made. The complete frozen case set concerns this bounded
partition-inventory question, not every Disk Management behavior.

Keep the existing DE-034 distinction between OS topology, decoded bytes and UI
display. DE-W030 must preserve exact geometry and independent conflict evidence;
`Healthy`, free-space strings and rounded capacities cannot establish write or
recovery eligibility. DE-W035 retains its own activation/selection/lifetime and
registration gates: this experiment ran Microsoft's MMC, not a DiskEd snap-in.
No new public API or production encoding is frozen by these private collectors.

## Controls, failures and cleanup

Each case used a fresh 4 MiB fixed VHD on the proven 32 MiB guest cap, attached
read-only without drive letters/permanent lifetime. A held verified virtual-disk
object, UUID, file identity and immutable recipe bound the transient UI locator.
All actual payload and full-container hashes remained unchanged. Both process
trees retired before each exact VHD detached and was removed.

The first observer compile failed at `b9c044e1` because COM declarations were
missing before the SDK UI Automation header. Two later attempts retained the
job-assignment rejection and its diagnosis. Both suspended processes already
belonged to inherited jobs; a nonempty shared leaf rejected the second process
with error 5 despite zero UI restrictions and low commit. Separate empty leaf
jobs solved that observed restriction. The inherited job owners were not
identified. Each concurrent leaf is limited to 128 MiB/four processes, retaining
the original combined 256 MiB/eight-process ceiling; no breakaway or higher
budget was used. All nine reference jobs have verified zero active processes.
The first captured set's noncanonical counter labels were corrected to the
unchanged frozen participant/kind names before the final set was admitted.

The final archive has **21 entries, 311,898 original bytes, compressed to
8,956 bytes**. Entry sets, hashes, raw UI records, actor/process/desktop/nonce
relationships, source Git blobs and rebuilt fixture/footer hashes replay.
Malformed/missing UI data and missing/duplicate/noncanonical tuples are rejected
by retained regressions. Reference disagreement is separate from completeness.

Profile, loaded hive, membership, account, station/session exceptions and owned
scratch were removed. [Fresh cleanup](capture/cleanup-live.json) found no owned
processes or inaccessible ownership queries, qualification root, R: drive, actor
directory, profile key, backup key or hive. The host managed launch workspace
peaked at 1,027,524 bytes and was removed. The shared backing file's logical
length was unchanged; allocated growth was not measured. No bulk image, profile
or build objects are retained.

SCM status was stopped before the earlier capture and running afterward; the
final capture began with VDS already running. Activation was declared. Shared
services were not stopped during cleanup; SCM state is not provider admission.
[Full repository validation](ui-validation.json.xz) passed **253 specification,
247 tooling and 108 differential tests**, with eight documented skips. Watched
inputs remained unchanged during that run; product source is unchanged. The
managed validation workspace peaked at 57,804,207 bytes and was removed. Final
metadata/context/manifest checks are recorded separately. Agent review accepts
this bounded reference deliverable for local DE-W030 continuation; owner acceptance and
the original all-platform/storage 0.1.0 finish line remain outstanding.
