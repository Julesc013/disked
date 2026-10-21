# Learning from Windows

DiskEd will use documented Windows interfaces, controlled reference experiments
and independent regressions to settle specific compatibility questions. This
extends the existing differential tests. It preserves the current source owners,
native implementation direction and original 0.1.0 scope. DE-W107's
[native/API checkpoint](../.aide/evidence/2026-10-21-windows-reference/api/REVIEW.md)
records four actual Windows layout queries and their independent native results.
The full campaign remains incomplete until four Disk Management UI observations
exist. REA has not been installed or qualified.

The [disposable profile preflight](../.aide/evidence/2026-10-21-windows-reference/ui/REVIEW.md)
passed at `10f4173f`: Windows resolved the restricted probe's profile and known
folders on capped guest storage, its owned hive write was independently verified,
and cleanup completed. Actual administrative MMC/UI execution remains unqualified.

## Which Windows component does what?

| Surface | What to study | DiskEd owner and implementation boundary |
|---|---|---|
| Disk Management | Selection, refresh, disabled actions, diagnostics and the storage facts actually displayed | Shared operation meaning in `source/runtime/`; native presentation in `source/apps/disked/`. A display is evidence of that UI, not proof of disk contents. |
| `.msc` and MMC | Saved console composition, snap-in interfaces, host bitness, selection and remote retargeting | Optional DiskEd-owned adapter under `source/integrations/` when implemented. A saved console is not a storage engine. |
| Computer Management | Extension points, selected computer identity, disconnects and independent teardown | The same thin integration adapter; no copied Microsoft COM identity or replacement system file. |
| Windows storage interfaces | Enumeration, topology, identifiers, capabilities, errors and preconditions | Concrete provider under `source/providers/`, native mechanisms under `source/platform/windows/`; public contracts before undocumented implementation details. |
| Services and service control | Relevant lifecycle, dependency, stop/cancel/reconnect and access behavior | Documented service interfaces and existing runtime execution contracts. Study only services needed by a DiskEd capability; this is not a replacement of Windows services generally. |
| Explorer shell | Context menus, properties, image associations and launch target binding | Optional thin owned shell adapter. Keep parsing and long operations outside Explorer; registration belongs to managed delivery. |
| Filesystem and partition behavior | Recognition, rejection, metadata and effects on generated media | Supplied-byte algorithms in `source/portable/`, acquisition through providers, independently specified comparison rules. |
| Historical Windows and other targets | Available imports, ABI, encoding and actual behavior on an exact build | Explicit target composition and evidence. One modern Windows result does not qualify XP, Win16, ReactOS or another OS. |

Microsoft documents [saved MMC consoles](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/mmc),
[snap-ins](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/mmc/snap-ins),
[shell handlers](https://learn.microsoft.com/en-us/windows/win32/shell/handlers) and
the [Service Control Manager](https://learn.microsoft.com/en-us/windows/win32/services/service-control-manager).
Storage Management and legacy VDS have different availability and coverage; see
Microsoft's [transition guidance](https://learn.microsoft.com/en-us/windows/win32/w8cookbook/vds-is-transitioning-to-wmiv2-based-windows-storage-management-api).
Do not infer the internal backend of a particular Disk Management build without
observing it.

## Experiment first, then implementation

1. State one unanswered question and inspect the public contract.
2. Fix the expected observation set, fixture recipe, comparison fields and
   permitted effects before running the reference or evaluating DiskEd.
3. Observe the exact reference version in the guest with a separately owned
   fixture copy. Capture raw results, failures and before/after identities.
4. Separate documented facts, measured behavior, inference and unresolved results.
5. Review the behavior contract, then implement and test against that contract
   using independent expectations.
6. Retain the smallest replayable evidence and remove disposable output.

For each promoted finding, record the question, exact evidence, applicable target
and profile, canonical contract owner, adoption decision and regression/work-item
link in the existing evidence and handoff records. The decision can be to use a
documented API, reuse an admitted upstream implementation, reproduce an observed
behavior, deliberately differ for a stated reason, or leave the question open.
Do not turn every observed quirk into a requirement or create a second registry.

The [canonical testing policy](../spec/development/testing-and-ci.md) and
[differential contract](../tests/differential/CONTRACT.md) own the evidence rules.
Independent implementation means more than generating code and matching tests
from the same model assumption. Reference agreement cannot authorize a writer,
erase conflicting GPT candidates or prove physical persistence.

## Planned sequence

| Work | Deliverable | Completion boundary |
|---|---|---|
| DE-W105, native gate passed | Same-source native qualification at `5c2f5337` | 180 x64 groups and 18 private Win32 groups; retained failures and separate owner/release gates. |
| DE-W106, development review passed | Complete evidence validation and bounded coordinator controls at `cfbde97b` | Sixty owned calls and replay/cleanup pass. A labelled repository protocol fixture does not qualify unavailable independent reference tools. |
| DE-W107, current | One small Windows partition-inventory experiment | Four recipe-defined cases: valid MBR, valid GPT, damaged primary GPT and conflicting valid GPT copies. Bind API and Disk Management UI observations to the same recipes and explicit participant copies. |
| DE-W030 | Settle a named read-only API/provider or required-service ambiguity | Existing inventory, capability, source identity and provider admission gates remain. Reviewed reference findings enter the relevant follow-on slice without blocking unrelated current inventory work. |
| DE-W035 | Qualify one selected MMC or shell adapter profile | Thin read-only dispatch, exact host/selection/callback lifetime, standalone-service parity and owned fixture registration/teardown. Subsequent surfaces are separately bounded selections. |
| DE-W050 / DE-W060 | Apply relevant findings to execution and deployment | DE-W050 owns the local privileged broker boundary. DE-W060 owns Setup integration; optional service/adapter installation follows DE-061/DE-063 lifecycle and account ownership. Research does not select a persistent service. |
| DE-W018 with DE-050 / DE-051 / DE-052 | Repeat relevant contracts on selected historical/other targets | Record actual compile/import/launch/operation evidence per target. DE-W070 applies to JC-DOS/Carbon integration where selected. New target profiles require an explicit scope decision. |
| DE-W042 / DE-W080 and the selected operation owner | Investigate later mutation, interruption and recovery behavior | DE-W042 owns recovery/cancellation experiments; DE-W080 owns advanced operation/provider admission, not historical-host qualification. Existing writer and recovery gates remain. |

DE-W106 corrects the comparator gap recorded by the earlier review; that finding
did not establish that the historical campaign was invalid. The current comparator
rejects missing, duplicate, mismatched and unidentified evidence, and its coordinator
consumes that complete gate. The [review](../.aide/evidence/2026-10-21-differential-qualification/REVIEW.md)
records the available confined Windows controls and their limits. The obsolete WSL
recipe stays suspended until its actual execution profile is qualified.

The first Windows campaign records observations rather than selecting a winning
parser. An unavailable API or inaccessible UI remains explicit. A reference
refusal can be a complete observation; missing evidence cannot. API-only results
do not satisfy a campaign that declared UI observations too.

## Integration experiments at their implementation gates

DE-025 owns adapter semantics; DE-034 owns Windows provider strategy. Select one
surface, question and host profile before implementation. The following cases
sharpen those existing gates; they are not additions to the four-case DE-W107
partition pilot or a claim that any adapter is already implemented.

| Surface or transition | Bounded experiment | Required interpretation |
|---|---|---|
| MMC console and snap-in | Save/reopen a DiskEd-owned console; exercise the selected standalone or extension mode, host bitness, multiple instances, failed activation and unload | Console composition, COM adapter lifetime and backend capability are separately qualified. One instance cannot retain callbacks into another or into unloaded code. |
| Computer Management retargeting | Select fixture computer A, expand its Storage extension, retarget to B, then deliver A's delayed observation and attempt another read | Invalidate A's selection and pending presentation. Preserve the old result's identity; it cannot publish as B or authorize an action on B. An unsupported remote target remains unavailable. |
| Explorer activation | Exercise the declared file/volume/multiple-selection contexts, spaces, non-ASCII names, unsupported namespace items and a removed/replaced target | Preserve structured selection or exact supported locators, then resolve them in the shared engine. A display name, drive letter or disk number is not target authority. |
| Shell host responsiveness | Construct a menu with a missing or stalled provider, invoke an action, then close one adapter instance | Menu callbacks remain bounded. Parsing and long work use the existing operation machinery; presentation closure does not establish an operation's cancellation or outcome. |
| Required service or provider | Inject absent, denied, pending, running-but-unavailable and dependency-loss states | Record SCM status, endpoint availability, provider/target capability and the actual operation result separately. An unavailable provider is not a successful empty inventory. |
| Cancellation and reconnect | Race completion with cancellation; disconnect and reconnect to an existing owned attempt; observe restart with an unresolved operation | Request, actual completion and recovery are different events. Keep the existing operation identity and reconcile uncertain effects before considering a new attempt. |
| Managed integration lifecycle | Exercise the selected adapter/service install, update and removal on owned fixtures with later foreign changes | Preserve unrelated registrations, account selections and active/recovery dependencies. Strict portable use remains free of persistent registration. |

Microsoft documents a [Storage extension point in Computer Management](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/mmc/computer-management-extensible-node-types)
and a [retargeting lifecycle](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/mmc/retargeting-the-computer-management-snap-in)
in which the extension's component instance survives removal of its old subtree.
That makes delayed results and target changes useful tests, beyond visual parity.

Choose the simplest sufficient [classic shell activation method](https://learn.microsoft.com/en-us/windows/win32/shell/shortcut-choose-method).
Classic verbs, COM local-server activation and the
[Windows 11 package/sparse-package command registration](https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/integrate-packaged-app-with-file-explorer)
are distinct host profiles. A context-menu command, property page and namespace
extension do not inherit one another's compatibility. The selected profile must
record its actual COM hosting, process architecture and installation mechanism.

Use injected states or owned fixtures for the first read-only adapter. Observe
real reference services only as needed by a named capability; an API may activate
a service, so declare and record those effects. Do not stop or replace unrelated
services to make a fixture convenient. A service-control or recovery event is not
proof of storage transaction recovery.

MMC retargeting tests establish selector and refusal behavior. Actual remote
observation or execution additionally needs the authenticated host, transport,
provider and reconnect contracts in DE-015/DE-022/DE-041/DE-052. The first broker
remains local-only. Integration qualification does not enable a network listener
or silently redirect an unavailable remote request to local storage.

## REA's role

[REA](https://github.com/morluto/rea) offers application and native-binary analysis;
it is not inherently limited to black-box observation. It is an optional modern
development tool, not a DiskEd runtime dependency or an acceptance oracle.
Pilot it only against one remaining documented question, with exact tool/input
identities, a fixed resource allowance and a reproducible finding or regression.
Installation and cache growth count against the existing resource policy; do not
run fetched installers merely because this plan links them.

Record provenance separately for public documentation/behavior, licensed source
reuse and proprietary binary-analysis output. A behavioral implementation task
receives its reviewed contract and permitted fixtures. If a task requires strict
observer/builder separation, enforce access restrictions and separate histories;
the shared administrator account and different prompts do not provide isolation.
Do not label a task clean-room merely because an agent rewrote the result.
Use original or permitted UI assets; this plan grants no redistribution rights.

## Resource and host boundaries

Use the existing Windows 10 guest and Agents connection by default. Preserve
the 32 MiB local metadata limit, 1 GiB aggregate disposable limit, 20,000-entry
limit, host reserve and demonstrated filesystem cap. Generate one needed fixture
at a time and retire it before the next participant when possible. Mounting may
change media; retain changed-byte evidence rather than assuming a read-only UI
left it untouched. Media presented as a disk must be explicitly owned disposable
guest virtual media, never a transient disk number alone.

Coordinate exclusive interactive-desktop use for UI experiments. Do not reset,
reboot, compact or reconfigure the shared guest as automatic cleanup. Reference
work cannot silently fall back to the host, enlarge budgets or accumulate
checkpoints, images, disassembly databases or archives. Retain generators, hashes,
compact raw observations and bounded failure reproductions. The current product
qualification stays first in the programme.
