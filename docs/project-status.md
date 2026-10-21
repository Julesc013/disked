# DiskEd implementation and release status

Reviewed 21 October 2026. This is a status publication, not a new release scope
or an acceptance record. The [programme](../.aide/programmes/disked-0.1.0.json),
[work definitions](../spec/work/units.json) and linked evidence own the details.

DiskEd is a substantial native Windows image workbench, currently identified as
`0.1.0-dev.72`. It is not a qualified replacement for Disk Management on real
drives. No release is authorized by this checkpoint.

## What exists

| Area | Implemented surface | Remaining qualification or functionality |
|---|---|---|
| Application | One native executable; CLI, JSON/NDJSON, console TUI, command shell and Win32 GUI; shared invocation, result and review semantics | Broader usability, accessibility, DPI, terminal and platform matrix; no alternative frontend framework is needed to continue |
| Commands | 26 command identities admitted in the selected development composition; static discovery distinguishes planned/unavailable commands | A command's presence does not qualify every provider or target; system target observations remain separate from the fake composition |
| Partitions and images | Supplied-byte MBR/EBR/GPT readers, conflicting candidate evidence, ordinary raw-file inspection and verification | Real backing topology, live storage admission and broad partition mutation |
| FAT | Bounded allocation/directory/tree inspection, ordinary-image extraction and constrained recursive extraction to an explicitly selected ordinary destination | Broader fidelity, consumers, repair, formatting, resizing and migration |
| exFAT | Boot/allocation/system metadata, root observations and selected command/worker paths | Complete namespace, content, extraction, repair, mutation and consumer qualification |
| NTFS | Boot/FILE/attribute/runlist work, captured streams and record closure, directory indexes, filename instances, correspondence, uppercase tables and same-capture mapped name-order inspection | Complete namespace, lookup/content, full collation and alias policy, recovery/repair and writer admission |
| Acquisition and evidence | Ordinary-file acquisition with operation identity, cancellation/resume, verification and reports; selected extraction/report workflows | Physical/failing-media acquisition, real dependency topology, snapshot/application consistency, authenticated custody and persistence qualification |
| Native Windows observations | Injected query/frame/graph/frontend infrastructure; actual guest volume namespace and typed contained native publication | A public Windows provider, physical identity/topology, broader API/provider/service coverage and other Windows builds |
| Operations | Same-file workers, finite waits, retained identities, watch/cancel/reconnect and explicit unknown outcomes | A qualified production privileged broker and durable real-storage execution |
| Image mutation/recovery | Private generated-image GPT planning/execution/restoration/history and journal framing/semantic experiments | Accepted production journal encoding/durability, public writers, physical/power-loss recovery and independent protection |
| Delivery | Portable payload inventory, package/extraction fixtures, private Setup source-consumer and finite-carrier/servicing fixtures | Full installed lifecycle, upgrades/state compatibility, servicing ownership, signed/published artifacts and actual release admission |

Acquisition, extraction and report export can write their ordinary destinations.
Calling source inspection read-only does not imply that the whole application
or host performs no writes. The selected composition does not admit physical
storage mutation.

The general command catalog has 41 descriptors whose product-wide availability
remains planned. The native bootstrap catalog separately selects 26 implemented
development command identities. Those are different claim scopes: implementing
an image/fake command does not admit every provider or its production equivalent.

The source ownership remains `source/portable`, `source/runtime`,
`source/providers`, `source/platform` and `source/apps/disked`. Current source-map,
dependency and standalone-header checks accompany the implementation. Stable
public IDs and admitted formats carry compatibility obligations; private names
and paths can evolve. Another general directory overhaul is not on the critical path.

## Latest evidence and its limits

The last integrated full product baseline is
[`5c2f5337`](../.aide/evidence/2026-10-21-product-capture/REVIEW.md): 180 x64 groups,
69 standalone headers, 14 executable/import observations, the selected 18-group
private Win32 slice and six actual reviewed GUI captures. Historical results
remain attached to their exact inputs.

DE-W106 repaired evidence accounting and the bounded Windows coordinator path.
DE-W107 completed the frozen four-partition-case native/API/Disk Management UI
pilot. The [combined review](../.aide/evidence/2026-10-21-windows-reference/ui/COMBINED-REVIEW.md)
keeps Windows presentation separate from exact bytes and GPT conflict evidence.
These cases do not qualify every Windows integration or storage provider.

The new contained native namespace passes all 15 fixed cases on each of x64 and
Win32 at `57578ab0`, together with the injected adapter/worker/graph regressions.
Its [focused review](../.aide/evidence/2026-10-21-contained-namespace/FOCUSED-REVIEW.md)
records exact process, schema, capture and immutable publication bindings.
The first full x64 attempt at `8bc79471` reached its unchanged 1,800-second build
deadline before running product test groups. Its failed evidence and cleanup are
retained. The separate current private Win32 supplement at `8bc79471` passed
18 groups, 12 headers and nine executable/import observations; its closed archive
and cleanup pass replay. The clean x64 build at `54bc8cd8` completed under the
original deadline, with 69 headers and 14 executable/import observations, but
the full native gate **failed at 176/180 groups**. The four unresolved groups are
`frontend.fat_tree_sessions`, `frontend.gui_windows`, `image.fat_commands` and
`image.fat_retention_commands`. Observed symptoms are truncated GUI JSON, a
window-message timeout, an inspection wait expiry and unresolved reader startup.
Their root causes are not yet established. The [current review](../.aide/evidence/2026-10-21-contained-namespace/REVIEW.md)
retains the exact failures and successful owned cleanup. The documented clean-build
tracking option is not a repair for these test failures. No current full native
pass or public provider admission is claimed.

Native campaigns use the shared Windows 10 guest and the demonstrated 32/512 MiB
scratch boundaries. Local context is limited to 32 MiB; disposable work to 1 GiB,
20,000 entries and the existing free-space reserves. Owned scratch is removed;
the VM itself, its checkpoints and other users are preserved. Host coordination
and filesystem accounting do not qualify host storage operations.

## What remains for the original 0.1

The owner-selected 0.1.0 finish line is **all platforms and storage operations
specified at base `40ac8ec`**. It has not been replaced with an inspector release.
The development version number and completed private slices do not establish
completion of that programme.

1. Diagnose and repair the four current native failures, then obtain applicable
   qualification before treating the checkpoint as fully qualified.
2. Admit a coherent real Windows read-only provider/workflow, with identity,
   freshness, aliases, partial observations, removals and permission failures.
3. Complete the promised filesystem namespace/content/fidelity capabilities and
   operation-specific support for additional filesystem families.
4. Qualify acquisition against real backing dependencies, failing media,
   consistency boundaries and independently verified destinations.
5. Settle production plan/journal/durability contracts; qualify image writers,
   then the privileged broker and each separately admitted storage mutation.
6. Complete resize/move/format/repair/conversion, copy/migration, erase/sanitize,
   interruption/recovery and
   independently placed backups for the operations included in the original scope.
7. Qualify boot/system-disk dependencies, BitLocker, WinRE/offline continuation
   and cross-boot identity before offering those operations.
8. Build and exercise the named historical Windows, DOS/JC-DOS/Carbon, OS/2,
   ReactOS, Linux, BSD/Unix and classic/modern macOS profiles, including the
   selected ARM, Server Core, recovery and frontend variants. Modern Win32 probes and C90
   syntax checks do not establish those product/platform claims.
9. Implement and qualify the specified advanced storage/media, tape/optical/flux, arrays/pools,
   shared-storage/fencing and enterprise capabilities under their existing gates.
10. Qualify the selected Explorer/MMC/Computer Management/service integrations,
    installed Setup lifecycle, carrier/channel ownership and updates/removal.
11. Complete the supported UI/terminal/accessibility matrix, live AIDE
    interoperability where claimed, reproducible delivery and relevant adverse testing.
12. Resolve affected owner decisions, licensing, formal acceptance and release
    governance. A merge is not owner acceptance, release signing or publication.

The current plan permits local implementation across work units after recorded
tests and agent review. It does not repeatedly require restarting DE-W000 or
DE-W010, and it does not remove the later storage/release gates.

The existing work records route the remaining programmes as follows. An active
record can contain substantial private implementation while still lacking its
full acceptance evidence.

| Existing owners | Remaining programme |
|---|---|
| DE-W030, DE-W031, DE-W032, DE-W035 | Native Windows inventory, target/frontend qualification, health and optional native integration |
| DE-W033, DE-W034 | Acquisition consistency, evidence applicability and complete reports |
| DE-W040, DE-W041, DE-W042, DE-W043 | Production journal, image mutation/formatting, interruption and verified recovery |
| DE-W050, DE-W051 | Privileged broker and separately authorized physical qualification |
| DE-W060, DE-W062 | Setup integration, finite carriers and servicing ownership |
| DE-W061 | Actual round-trip AIDE interoperability |
| DE-W018, DE-W070, DE-W071 | Constrained platforms, current Carbon/JC-DOS integration and DOS/OS/2 image profiles |
| DE-W080 | Separately scoped advanced operation/provider admissions |
| DE-W000, DE-W090 | Genuine baseline/owner acceptance, licensing and release criteria |

The programme lists 55 completed development slices. Several other implemented
records retain `needs_review`; neither count establishes owner acceptance or
an overall completion percentage. The outstanding decision register still covers
licensing, production journal/durability, exact-image elevation, canonical plan
encoding and profile-specific admission. Their blocking scopes remain attached
to the affected features rather than every ordinary development task.

## What 1.0 means at present

There is **no separately baselined DiskEd 1.0 feature list or completion contract**
in the current repository. References to upstream SDK/ABI 1.0 are not DiskEd
product-release commitments. It would be inaccurate to invent a completed 1.0
roadmap, or move unfinished original 0.1 requirements into it.

A proposed 1.0 maturity contract should define the supported release matrix,
stable public interfaces and durable-format compatibility, upgrade/migration and
recovery obligations, security/servicing policy, operational documentation and
repeatable independent qualification. Several of those capabilities are already
required by the original 0.1 scope; 1.0 must not become an excuse to defer them.
This paragraph is a recommendation, not an accepted scope amendment or date.

## Usability and completion timing

There are already useful development workflows over ordinary image files:
partition inspection/verification, selected filesystem inspection, FAT file/tree
extraction, ordinary-file acquisition, verification and evidence/report export.
They exist in the native development build; they are not a published, generally
qualified storage product. Fake inventory remains the default product composition.

The next practical threshold for everyday Windows drive inspection is a qualified
public read-only Windows provider, correct target identity/freshness/topology and
a coherent interface workflow, with permission/removal/partial-result tests. The
private namespace observations are progress toward that threshold, not its completion.

Real partitioning, formatting, repair or recovery requires the separately admitted
writer/journal/broker and operation-specific interruption/recovery evidence. An
installer or attractive GUI cannot substitute for those capabilities. Broad
historical/platform support also needs actual builds, launches and supported
operation tuples on the named profiles.

There is no evidence-based completion date for the entire owner-selected 0.1
programme. It spans substantially more than the current Windows image workbench,
and remaining work includes unavailable qualification environments and genuine
owner/physical/release decisions. No date for an undefined 1.0 scope can be
substantiated either. Estimate the next bounded implementation and qualification
slice after resuming, then revise the programme using actual results; do not
convert work-unit counts or passing test counts into a release forecast.

The target catalog contains the same 41 declared profiles as the programme's
base revision, including explicitly labelled research entries. Their catalog
admission remains planned. A tested Windows 10 development composition and private
Win32 probes do not qualify that whole matrix or every operation on every host.

## Universal Setup, AIDE and repository governance

DiskEd's inspected Setup source pin remains `2e64f654`; its local package and
native consumer fixtures do not qualify actual install/repair/update/uninstall.
A fresh [hosted observation](../.aide/evidence/2026-10-21-contained-namespace/hosted-observations.json)
shows upstream Setup PR237 merged into `dev`, with seven successful reported checks and a
failed `publisher-qualification` check. This supersedes the old snapshot saying
that PR was open with a failing native-Windows job. It does not qualify DiskEd's
consumer against the newer upstream state.
Upstream `main` remains `c048f7f1`; its latest listed main-branch CI run succeeded.
The main-branch result and the newer dev/PR result are distinct observations.

AIDE was reviewed on 19 October and pinned at `7877e056`; the next recorded
review is 26 October. Passive WorkUnit/schema/export validation is distinct from
live scheduler/CLI interoperability. DiskEd does not depend on a particular model
vendor or on AIDE being a finished scheduler.

GitHub reported `main` unprotected and no DiskEd releases in the same read-only
observation. Required PR/status-check enforcement remains unfinished governance
work. The owner has explicitly authorized this turn's dev/main synchronization
and explicitly withheld release publication. No release or tag is created here.

## Remaining maintenance debt

[Read-only accounting](../.aide/evidence/2026-10-21-contained-namespace/evidence-storage.json)
found 63,535 tracked historical evidence files with about 1.74 GiB of uncompressed
logical payloads. That figure excludes Git history and is not an exact measurement
of filesystem allocation. Legacy raw outputs still need reference-audited
consolidation while preserving verifiable receipts. Current campaign scratch and
local context have their separate enforced limits; new native evidence is retained
as bounded compressed archives. The tracked tree also contains no GitHub Actions
workflow at this checkpoint; configuring and enforcing CI remains real work.
