# Learning from Windows

DiskEd will use documented Windows interfaces, controlled reference experiments
and independent regressions to settle specific compatibility questions. This
extends the existing differential tests. It preserves the current source owners,
native implementation direction and original 0.1.0 scope. The work below is
planned; no Windows reference campaign or REA installation has been qualified.

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

The [canonical testing policy](../spec/development/testing-and-ci.md) and
[differential contract](../tests/differential/CONTRACT.md) own the evidence rules.
Independent implementation means more than generating code and matching tests
from the same model assumption. Reference agreement cannot authorize a writer,
erase conflicting GPT candidates or prove physical persistence.

## Planned sequence

| Work | Deliverable | Completion boundary |
|---|---|---|
| DE-W105, current | Finish the existing same-source native qualification | Preserve failures and all original Win32/x64 checks; reference research does not replace them. |
| DE-W106 | Validate complete differential evidence and migrate the old runner | Reject missing, duplicate, mismatched or unidentified evidence; run only in managed bounded workspace; prove owned cleanup. |
| DE-W107 | One small Windows partition-inventory experiment | Four recipe-defined cases: valid MBR, valid GPT, damaged primary GPT and conflicting valid GPT copies. Bind API and Disk Management UI observations to the same recipes and explicit participant copies. |
| DE-W030 / DE-W035 | Apply reviewed findings to providers and optional integrations | Existing capability, host identity, installation and teardown gates remain. Service/integration experiments are scheduled only for a named contract gap. |
| DE-W018 / DE-W080 | Repeat relevant contracts on selected historical/other targets | Record actual compile/import/launch/operation evidence per target. New target profiles require an explicit scope decision. |

DE-W106 records a current comparator gap, not a finding that the historical
campaign was invalid. Its current function can report passing adapter controls
when no external observations exist, when fixture hashes disagree, or when a
record is duplicated. The old WSL coordinator also requires bulk output under
`.aide-local`; do not run that recipe. Repair and validate it before reuse.

The first Windows campaign records observations rather than selecting a winning
parser. An unavailable API or inaccessible UI remains explicit. A reference
refusal can be a complete observation; missing evidence cannot. API-only results
do not satisfy a campaign that declared UI observations too.

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
