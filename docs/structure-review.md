# Source structure and release review follow-up

## Exact lease campaign and quota-harness correction: 14 October 2026

The clean `e75602f8` build and 48 standalone headers pass. Its full native
campaign passed 139 of 141 groups, including all eight earlier failures.
[Retained terminal results](../.aide/evidence/2026-10-14-worker-leases-exact-failed/README.md)
show two quota-harness failures: the fifth worker is refused during preparation,
while the harness catches only launch refusal. Working corrections verify
`operation_worker_budget_resource`/1816, no constructed fifth worker, four live
workers, confirmed retirement and source/output preservation. Both corrected
groups pass. A new exact-source complete campaign remains required; `main` and
full original 0.1.0 qualification remain separate.

## Worker repair checkpoint: 14 October 2026

Keep the five source owners, the 283-file source map and the existing CLI,
TUI, shell and terminal boundaries. Independent caller-job probes reproduced
the shared worker job's launch error 5. The replacement uses four inherited
kernel slot leases and existing private jobs, preserving caller restrictions
and the four-worker/128 MiB per-process/512 MiB total limits. The
[working repair evidence](../.aide/evidence/2026-10-14-worker-leases-working/README.md)
retains original failures and selected passing results. A new exact-source full
141-group campaign remains required before normal admission and `main` promotion.

Universal Setup draft [PR #237](https://github.com/Julesc013/universal-setup/pull/237)
is now at `4cd3dac3`. Its [current CI run](https://github.com/Julesc013/universal-setup/actions/runs/38525077743)
has six successful jobs and a failed `native-windows` job, checked on 14 October.
This is hosted CI status, not independent Setup qualification. DiskEd's full
0.1.0 scope and owner/storage/platform/release gates remain unfinished.

## Failed full command qualification: 14 October 2026

Keep the five source owners and the 283-file source map. The clean `60376a0e`
campaign built successfully but passed only 132 of 140 native groups. Eight
existing retention, extraction, acquisition and report groups failed; the new
exFAT groups passed. [Original failed evidence](../.aide/evidence/2026-10-14-exfat-command-exact-failed/README.md)
retains the complete results. This does not qualify the normal composition.

Working adapter diagnostics now retain the Windows error code, FAT source pins
survive exception retirement, and retention fixture sessions close before source
cleanup. The [partial repair](../.aide/evidence/2026-10-14-exfat-launch-repair-working/README.md)
passes 68 FAT retention cases, 33 exFAT command cases and two reader headers.
The extended process-launch error 5 and the eight failed groups remain unresolved.
Development checkpoints go to `dev`; `main` remains at its earlier reviewed
checkpoint until a complete applicable campaign and agent review pass.

Universal Setup draft [PR #237](https://github.com/Julesc013/universal-setup/pull/237)
is at `7cf0b5ff`. Its [current CI run](https://github.com/Julesc013/universal-setup/actions/runs/38512737801)
has six successful jobs and a failed `native-windows` job as checked on
14 October. This check did not independently diagnose or execute Setup. Full
DiskEd 0.1.0, owner/storage/platform and release acceptance remain unfinished.

## Working exFAT command checkpoint: 14 October 2026

The source map covers all **283** current files once. Keep the five existing
owners and the separate CLI/TUI/shell models and shared terminal. New
`exfat_inspection.*` and `exfat_reader.*` follow the same ownership split as
their FAT counterparts; no empty future tree or broad naming rewrite is needed.

Automatic transport is locally reviewed at exact `33ee364a`, with four selected
native groups/four headers, 146 observer/89 file/94 worker cases and 242 tooling
tests/two skips. The subsequent shared exFAT command and all five frontends pass
33 working cases; full native build succeeds. Plain-output and independent
full-array hash coverage pass; exact command qualification remains in progress. These
working results do not replace the earlier revision-bound qualifications.

Development proceeds on `dev`; only tested, agent-reviewed checkpoints are
promoted to `main`. The original all-platform/storage 0.1.0 scope, owner
acceptance and release/storage gates remain unfinished. Current programme and
the [exFAT contract](exfat-capture.md) record the next bounded implementation.


## Current contained-reader checkpoint: 14 October 2026

Keep the existing source ownership tree. The source map covers all 279 current
files exactly once; CLI and the consistent GUI/TUI/shell model names remain
appropriate. Existing runtime, image-provider and Windows storage owners now
accommodate W069 without a restructure or additional scheduler.

At exact full clean `cce05d17`, all 139 current native groups pass, alongside
46 standalone headers, 69 reader cases/six methods, 63 file
cases/eight methods and 242 tooling tests with two skips. [Evidence and local
review](../.aide/evidence/2026-10-14-exfat-worker-qualified/README.md) cover confirmed-exit retirement and pre-read
source binding. Actual file-symlink creation remains unverified without privilege.
This private reader does not yet admit normal exFAT frontend commands, complete
tree/content, physical storage, other hosts or the original full0.1.0 release.
Tested and locally reviewed checkpoints can merge from dev to main under the
existing grant; owner/release acceptance stays separate.

The latest read-only Universal Setup observation has main `c048f7f1`, dev
`2b7a4d01` and open draft [PR #237](https://github.com/Julesc013/universal-setup/pull/237)
at `00bb4978`. Its [native Windows CI job](https://github.com/Julesc013/universal-setup/actions/runs/38492214371/job/115619848757) fails;
the other six jobs pass. Both repository release queries are empty. These are
hosted observations, not an independent cause diagnosis or DiskEd lifecycle test.


## Qualified held exFAT image adapter: 14 October 2026

The existing image-provider/local_file and runtime/capture owners accommodate
W068; the source map now covers 275 files. Exact `c73c6870` passes 60 native image
cases/seven methods, 20 selected native groups, one header and 242 tooling tests
with two skips. [Retained evidence](../.aide/evidence/2026-10-14-exfat-file-qualified/README.md)
records unavailable file-symlink creation separately from passing actual
junction/hardlink/held-access checks. This is a private synchronous ordinary-file
adapter, not contained worker/frontend/tree/content or full release admission.
Keep the ownership tree and continue bounded process integration and the original
all-platform/storage0.1.0 with separate owner/privilege/release gates.


## Qualified root/system integration: 14 October 2026

The existing runtime/capture and portable/exfat owners now accommodate W067
without restructuring. Exact clean sparse `bba3d600` passes 121 generated image
cases/9 methods, 19 selected native groups, one header and 242 tooling tests with
two skips. [Evidence and agent review](../.aide/evidence/2026-10-14-exfat-capture-qualified/README.md)
record the complete selected input closure and excluded unused archive. This is
root/active-system supplied-byte agreement; held native source, worker, paged
namespace/tree/content and the full original platform/storage release remain.


## Earlier upcase checkpoint: 14 October 2026

Keep the existing source ownership tree. The [source map](source-map.md) covers
all 273 current files exactly once. CLI has its own folder; TUI, GUI and shell use
`tui_model.*`, `gui_model.*` and `shell_model.*`. Shared runtime semantics and native
terminal/window hosts remain separate. Build-target, header/dependency and shared
presentation improvements from the supplied review have retained tests. Application
routing/test-seam cleanup remains incremental work; no demonstrated defect calls
for a wholesale restructure or speculative future files.

W066 at exact clean `e43f00fb` passes 244 upcase scenarios, 15 selected native
groups, one header, C90/import/context/source checks and 242 tooling tests with
two skips. [Evidence and agent review](../.aide/evidence/2026-10-14-exfat-upcase-qualified/README.md) keep the prior complete
native suite separate. Root/active-FAT/bitmap/upcase source coherence and broader
tree/content/provider/platform/storage work remain. Tested dev checkpoints can
merge to main after local review; full 0.1.0 release is not ready.

A fresh read-only GitHub observation found Universal Setup main at `c048f7f1`,
dev at `2b7a4d01` and open draft [PR #237](https://github.com/Julesc013/universal-setup/pull/237)
at `8b1837ec132363a7c3a3cfe2412b4927e1645b22`.
[Its exact-head CI run](https://github.com/Julesc013/universal-setup/actions/runs/38482259213)
fails `native-windows`; six other jobs pass. This is hosted status, not an
independent cause diagnosis or DiskEd lifecycle qualification. Both public release
queries returned empty lists. Historical observations below retain their original
revisions and results.


## Qualified private exFAT metadata: 14 October 2026

W058 at `1e938369` passes130native groups,42selected headers,242tooling tests with
2skips and all four local criteria. W064 at `44c8b090` passes2316directory cases,
tenfreshparser/guardgroups plus a boundaryfollowup, oneheader and C90/import/
source/context checks. The selective directory build initially omitted its
generated registry; its failed check and passing generator follow-up are retained.
Prior fullregression results apply to unchanged source and are separately labeled.
See [boot/allocation review](../.aide/evidence/2026-10-14-exfat-qualification/qualified-1e938369/REVIEW.md)
and [directory review](../.aide/evidence/2026-10-14-exfat-directory-qualified/REVIEW.md).
The existing source owners accommodate this work; there is no mountedexFAT,
bitmap/upcase/source/tree/provider/writer/otherhost or full0.1.0 release claim.

## exFAT development and Setup status: 14 October 2026

Dev checkpoint `38b6683a` adds a private C90 supplied-byte exFAT boot/checksum,
geometry and allocation-cell decoder under `source/portable/exfat/`. The existing
owners accommodate it without a repository restructure. Working checks passed
2,320 independent cases, seven focused native groups, 32 build-checker fixtures,
strict C90 syntax and protected/read-only input checks. Complete clean-source
qualification is running; this is not mounted exFAT, provider, writer or release
qualification. See [working evidence](../.aide/evidence/2026-10-14-exfat-working/README.md).

The clean campaign subsequently exposed a TUI tree-session fixture failure. Its
Tab wait accepted any render change, allowing stale focus/text to acknowledge the
wrong step. A repair requires the actual focused label to change and the complete
entered value to appear before continuing. The original campaign remains retained;
the repair and W058 full qualification are pending actual frontend validation.

At the boot-decoder checkpoint, the file-by-file [source map](source-map.md) covered 268 source files.
CLI has its own folder, and `tui_model.*`, `shell_model.*` and `gui_model.*` use
consistent private names. Future ownership is specified; future helper filenames
are chosen when their responsibilities are known. Stable command/spec identities
and admitted interfaces carry compatibility obligations independently of private
paths. No naming scheme can guarantee that future implementation needs no refactoring.

Fresh read-only GitHub checks found Universal Setup main `c048f7f1`, dev
`2b7a4d01` and open draft [PR #237](https://github.com/Julesc013/universal-setup/pull/237)
at `1de316e2`. Its [exact-revision CI run](https://github.com/Julesc013/universal-setup/actions/runs/38454057234)
failed `native-windows`; specification, fuzz-smoke, sanitizer, native-macos,
native-windows-win32 and native-linux passed. This is an upstream CI observation,
not an independent diagnosis or live DiskEd lifecycle test. Both GitHub release
queries returned empty lists. The original full-platform/storage 0.1.0 scope,
owner acceptance and release gates remain open. Continue tested dev checkpoints
and reviewed main integration; do not infer release readiness from synchronization.

## Qualified normal recursive commands: 14 October 2026

Exact clean source `087f95b4` passes 128 native groups, 41 standalone header
compilations, generated dependency checks and 242 tooling tests with two skips.
The [whole-unit evidence](../.aide/evidence/2026-10-14-fat-recursive-command-qualification/README.md)
maps all four DE-W057 local criteria to actual common frontend/operation/failure
results and exact source/build/import/context/artifact identities. The ordinary-file
Windows scope has reached implementing-agent review. Existing ownership accommodates
the work; owner, physical/other-host and full0.1.0 release acceptance remain open.

## Normal recursive composition development: 14 October 2026

The normal Windows image prototype now selects recursive ordinary-file FAT
extraction through existing runtime/native owners. Shared typed response schemas
cover preparation, execution, unknown requests and operation observations. Actual
CLI/protocol/GUI/TUI/shell journeys and isolated failure controls pass. A disabled
composition verifies refusal; the former duplicate nonfault test composition is
removed. There is no new source tree or scheduler. Full clean exact-source
qualification remains before DE-W057 review/integration, separate from owner,
physical, other-platform and full all-platform/storage0.1.0 release acceptance.

## Recursive interruption and producer checkpoint: 14 October 2026

Actual closed watch output preserves the independent operation and digest-bound
resumption; unresponsive and abruptly exited writers preserve unresolved history
without replacement. Strict emitted event shape/semantic validation is separate
from compatible additive reader acceptance. A real exit race exposed contradictory
worker/dependency observations; the worker now derives both from one snapshot.
Original failure evidence stays intact. Existing source ownership accommodates
these changes. Normal admission and full exact-source qualification remain before
DE-W057 review; complete all-platform/storage0.1.0 and release remain open.

## Current naming and release assessment: 14 October 2026

Read-only GitHub checks at this assessment find DiskEd dev at
`3df3732d6f8ee5ac30025bbf15dea645271b05e2` and main at
`fed4a71b767a92db13b0fd0a1b692c937fdacd93`. These are observed bases, not floating
claims about future heads. The supplied 12 October review describes an earlier
revision and supplies recommendations, not execution authority or acceptance.

Keep the source ownership tree and current names. TUI, GUI and shell retain
interaction state and use qualified model basenames; CLI formats one invocation
in its own folder. Shared command grammar belongs in runtime; concrete console
input/rendering/restoration belongs in the Windows terminal host. The complete
[source map](source-map.md) explains each current file; its growth table assigns
future responsibility families without pretending to enumerate future files.
Private filenames can evolve; admitted public interfaces and retained formats
need explicit compatibility policy and tests. No layout guarantees zero future
refactoring. Dependency enforcement and bounded responsibilities make changes local.

The dated review's target split, qualified includes, shared request/view invariants,
dependency checks and live work pointer have already been implemented with retained
evidence. Command-specific application routing and test seams remain incremental
maintenance work; no demonstrated requirement calls for a wholesale rewrite.

Fresh checks find Universal Setup main at `c048f7f1ae2e5922c15a08ee572bdafc29027c63`
and dev at `2b7a4d011a61992970601e8c174b5d9d0298a8cd`.
[Draft PR #237](https://github.com/Julesc013/universal-setup/pull/237) is open at
`1de316e2617e1cbe5d907470d27b227dc3fcbc4a`;
[run 38454057234](https://github.com/Julesc013/universal-setup/actions/runs/38454057234)
reports six successful checks and a failing native-windows check. Its log reports
an owned SYSTEM fixture failure and receipt archive count mismatches; these are
observations, not a root-cause diagnosis. This follow-up has not run Setup's
lifecycle. Both repositories'
GitHub release collection queries return empty lists; that does not inventory
private artifacts or all tags. DiskEd main is still reported unprotected.

Development checkpoints can continue on dev. Integrate the current recursive
command unit after its failure/cancellation/reconnect journeys, producer/reader
contracts, normal composition admission, clean exact-source regression campaign
and recorded agent review. Release additionally requires the selected composition's
platform/storage evidence, licensing, packaging/inventory, required acceptance and
publication authority. The all-platform/storage 0.1.0 objective is unfinished;
there is no evidence-based release date. A smaller preview needs an explicit scope.

## Recursive actual frontend development: 14 October 2026

The gated disked_recursive_test composition now connects the shared service to
actual CLI/protocol, Win32 GUI, TUI and shell. Generated FAT12/16/32 operations
produce exact expected bytes and preserve sources. Actual GUI/TUI/shell review,
submit and completed-operation watch pass; console restoration is retained.
Normal disked still reports extraction unavailable and refuses the tree backend
before paths. Native roles are gated to the development executable.

Compatible reader11methods, finite response/form budgets, parser/request-channel
and GUI/TUI/shared-model regressions pass. Source map266 files and236 dependency
targets have no violations. These are development results. Broader failures,
normal-composition admission and full clean-source qualification remain before
DE-W057 review; complete all-platform/storage0.1.0 and release remain open.

The following [failure checkpoint](../.aide/evidence/2026-10-14-fat-recursive-failures/README.md)
adds actual cancellation after launcher exit through all five frontends, separate
fault composition, retained full/short/flush failure without replay and explicit
source/stale/foreign-resource refusals. Shared definitions stay in the existing
owners; no new directory hierarchy is needed. Selected native tests and dependency
checks pass. Strict producer contracts, broader interruption tests, normal admission
and full clean-source qualification remain before the current work-unit review.

## Recursive shared command service development: 14 October 2026

Active DE-W057 now has canonical closed parameter/review schemas and shared
runtime command semantics, with native action ports in the existing Windows
owner. Seven methods exercise CLI parsing, form conversion and protocol dispatch
through a private probe using actual FAT12/16/32 preparation/detached execution.
Exact outputs/source preservation, all grants, stale/duplicate execution,
provider-call boundaries and independent schema/digest/receipt checks pass.

The operation identity is allocated before dispatch and later bound by the same
retained request. Pending acknowledgement preserves that proposed ID for inspect;
it proves no admitted operation. Five focused groups pass across retained runs,
tooling236pass/two skip, source map266 files and235 dependency targets. Actual
product frontend admission, compatible readers and full exact-source qualification
remain. The product command stays planned; full0.1.0 and release remain open.

## Recursive bounded wait/watch development: 14 October 2026

Active DE-W057 now projects validated recursive control records into bounded
events. Event sequences start at one; original control indices stay zero-based.
Exact header/review/worker and raw-record digests bind resumption. Changed/shrunk
prefixes, torn history, invalid options and rejected sinks preserve uncertainty
and the last admitted cursor. Native wait/watch opens only the existing store;
it neither reads extraction sources nor restarts/cancels the operation.

Ten focused methods cover pure event/cursor budgets and actual detached
following/cancellation/resumption. A live wait test observes its first snapshot
before requesting cooperative stop and follows the same owner through exit.
Three selected native groups pass; tooling236pass/two skip, source map262 files
and dependency checks230 targets. These are development results. Shared public
bindings, actual frontend journeys, compatible readers and full exact-source
qualification remain. Full all-platform/storage0.1.0 and release remain open.

## Detached recursive controller development: 14 October 2026

Active DE-W057 now has an explicit same-executable dispatch handoff independent
of caller lifetime. Actual FAT12/16/32 tests complete exact generated outputs
after caller exit. Closed-gate abandonment, all five grants, stale source/code,
separate-caller cancellation, owned hang retirement, repeated launch/dispatch,
published-before-exit and unresolved controller exit pass ten test methods.
The input/output channel and query-only job handles retain finite native owners;
caller-handle closure does not kill a dispatched controller or start another.

Three selected native groups pass: controller, reconnect and admission. Tooling
runs238 tests:236 pass/two skip. The source map covers260 files and generated
dependency checks cover228 targets without violations. These are focused
development results. Native wait/watch, actual public frontend journeys and full
clean-source qualification remain; full0.1.0 and release are unfinished.

## Recursive retained-history and reconnect development: 14 October 2026

Active DE-W057 now passes 38 focused cases/ten methods for bounded retained
control histories and native cross-process inspection/cancellation. The pure
reader stays under runtime/acquisition; actual NTFS/process/code observations
stay under platform/windows/storage. Request1 remains readable; request2 binds
controller/writer births. Consistency, current liveness and authority are
separate facts. Torn or contradictory histories grant no cancellation/replay.
Published outcomes before exit and a second live caller have actual evidence.

Native admission regression passes 41 cases/eleven methods. Tooling runs 238
tests: 236 pass and two skip. Source map covers 258 files and generated dependency
checks cover 223 targets without violations. These are development results;
detached controller ownership, native wait/watch, public command/frontends and
full clean-source qualification remain. No full 0.1.0 or release claim follows.

## Native recursive admission development: 14 October 2026

Active DE-W057 now passes 41 native cases/11 methods over actual pinned stores,
independent child IDs/hash chains/output bytes and separate preparation/execution
processes. It compares fresh native source/store/code/namespace facts against
immutable review before five exact grants and create-only store reservation.
Dispatch intent is flushed before the old private-plan grant; publication and
actual exit are separate observations. A 33,000-cluster file, missing/stale
grants/reviews, foreign resources, cooperative cancellation, hangs, store-write
failure and store pinning while a completed child remains alive have retained
results. A failed state write/flush freezes the ledger; no uncertain-tail append.

The store joins the existing worker dependency owner before launch, including
unknown retirement. There is no new scheduler or retention subsystem. The source
map covers 254 files; selected headers and normal/fault dependency checks pass.
Three selected native groups and 236 tooling tests pass with two skips.
These are focused development results. Independent retained-state/reconnect,
actual common frontend commands and full exact-source qualification remain.
The public command remains planned; full original 0.1.0/owner/storage/release
acceptance is not implied.

## Recursive effect review development: 14 October 2026

Active DE-W057 begins common-command/durable-operation admission. Its immutable
supplied-data review layer passes 45 cases/six methods, including two actual
owned preparations whose process-bound identities change while intended effects
remain equal. Source/store/code/policy/footprint changes withdraw equality;
unknown mutation-critical fields, inconsistent identities and missing grants
are refused. This layer opens no path and authorizes no native effects.

The source map covers 250 files once. The new runtime target depends only on
JSON/hash, with its standalone header and generated dependency check passing.
The canonical command registry records filesystem.tree.extract as planned,
spelled filesystem extract-tree; nesting under existing operand-taking commands
was refused by the registry. No alternate parser or registry is introduced.
Native store/admission, durable lifecycle, actual frontend journeys and full
clean-source qualification remain before whole-unit review or main integration.

## Qualified recursive backend: 14 October 2026

Clean source 243f748e passes 120 native groups, 32 selected standalone header
compilations, generated dependency checks and 236 tooling tests with two skips.
The [whole-unit evidence](../.aide/evidence/2026-10-14-fat-recursive-qualification/README.md)
maps all five DE-W056 criteria to actual results, launch/configuration/import
observations, exact source/blob/artifact identities and context/manifest freshness.
The private recursive backend, owned controller and independent history reader
have reached their agent review boundary in the recorded ordinary-file Windows
lane. Existing source ownership remains; no further restructuring is justified.

DE-W056 remains pending owner acceptance. Public recursive commands and their
operation lifecycle, other host/provider profiles and production/storage/release
gates remain work within the full original 0.1.0 goal. A tested agent-reviewed
repository merge is authorized separately from release publication.

## Retained recursive history inspection: 14 October 2026

The private supplied-byte inspector passes 78 cases/13 methods over 16 direct
and three owned-worker histories. It distinguishes recorded complete/partial,
unresolved prefixes and truncated tails. Complete source-free inspection after
withdrawal of the recorded source path, actual interrupted process histories,
FAT12/16/32, deep directories, a 33,000-cluster file, metadata results and
independently rehashed contradictory records have actual retained results.

The inspector belongs in the existing runtime evidence owner and depends only
on JSON/hash targets. It opens no recorded path, authenticates no actor and
grants no replay. The source map covers 248 files once; the generated dependency
check passes. No new root, scheduler or public protocol is introduced.

Tooling runs 238 tests: 236 pass and two skip. These are focused dirty development
results. Full clean-source native/header/import/artifact qualification remains
before whole-unit review and main integration. The full all-platform/storage
0.1.0 and separate owner/storage/release gates remain unfinished.

## Partial contained-writer checkpoint: 14 October 2026

The recursive controller now reuses the owned process host and existing quotas
for separate preparation, exact grant and execution. [Development evidence](../.aide/evidence/2026-10-14-fat-tree-extraction-worker/README.md)
records 29 cases/11 methods, eight selected native groups and 236 tooling
passes/two skips. Actual child/code/request/capture identities bind copied
definitions/results. Hangs and late publications retain dependencies until exit;
cooperative cancellation, startup failures and four-worker launch limits pass.

Two files stay under the existing Windows storage host owner. The [source map](source-map.md)
covers 246 files. No scheduler, new public command or root restructuring is
introduced. Independent retained-history inspection and a complete clean-source
native/import/artifact campaign remain in active DE-W056; full 0.1.0 and separate
owner/storage/release gates remain open.

## Partial recursive-writer checkpoint: 14 October 2026

The private ordinary-image/local-NTFS backend now prepares a complete namespace,
requires exact effect grants, creates children atomically under held parents,
copies and reads back content, and records original versus applied native
metadata in a flushed hash chain. [Development evidence](../.aide/evidence/2026-10-14-fat-tree-extraction/README.md)
records 46 cases/11 methods, seven selected native groups and 236 tooling
passes/two skips. Cases include 300-file FAT12/16/32 trees, a 33,000-cluster
noncontiguous file, deep parents, distinct Unicode forms, collisions, actual
process exits and durable completion despite a later notification failure.

The [source map](source-map.md) covers 244 current files. Two new files stay in
the existing image-provider owner; completed source reinspection gets a fresh
capture identity. No source-root overhaul, new public recursive command or
production ABI is introduced. This synchronous dev checkpoint still requires
contained writer/controller admission, hangs/late-response dependency and actual
exit qualification, independent history inspection and a complete clean-source
campaign. DE-W056 and the full original 0.1.0 programme remain active.

## Partial metadata-preparation checkpoint: 14 October 2026

DE-W056 now maps original FAT names/times/attributes explicitly and reobserves
metadata from its own held-source traversal. [Development evidence](../.aide/evidence/2026-10-14-fat-metadata/README.md)
records 631 mapping/Windows-code-page cases, 12 actual-file cases retaining 980
metadata frames, six selected native groups and 236 tooling passes/two skips.
The [source map](source-map.md) covers 242 current files. Original representations
stay separate from output candidates and actual future metadata application.

The existing runtime/acquisition and image-provider owners suffice. Preparation
creates no destination effects. This partial dev checkpoint does not qualify the
unfinished recursive writer or full 0.1.0. Immutable effect grants, destination
creation, ordered metadata evidence, native application/readback, contained
writer lifetime and complete exact-source qualification remain in active DE-W056.

## Partial recursive-content checkpoint: 14 October 2026

DE-W056 now has a supplied-reader file-content continuation and an adapter that
selects content only from its own held-source directory traversal. The existing
runtime capture and image-provider owners remain appropriate; no new repository
root or frontend abstraction is needed. The [source map](source-map.md) describes
all 238 current source files and their responsibilities.

[Development evidence](../.aide/evidence/2026-10-14-fat-recursive/README.md) records
39 supplied-byte cases, eight held-file cases and passing existing tree-worker
and frontend regressions. These are working-tree observations, not a clean full
native qualification. DE-W056 remains active: recursive destination creation,
immutable effect grants, original metadata preservation and explicit native
restoration policies still need implementation and qualification.

This partial checkpoint belongs on `dev`. The previous qualified checkpoint is
already integrated into `main`; merging this unfinished work or publishing 0.1.0
would overstate the evidence. The full original platform/storage programme and
the separate owner, physical-storage and release gates remain open.

A read-only hosted check on 14 October found Universal Setup main `c048f7f1`
and dev `2b7a4d01` unchanged. Draft
[PR #237](https://github.com/Julesc013/universal-setup/pull/237) now has head
`f4442867`; [run 38386640408](https://github.com/Julesc013/universal-setup/actions/runs/38386640408)
fails `native-windows` while the other six jobs pass. Both public release queries
still return zero entries. [Retained responses](../.aide/evidence/2026-10-14-fat-recursive/hosted-setup-status.json)
are hosted observations, not a local diagnosis or Setup integration qualification.

## Qualified tree-session checkpoint: 13 October 2026

Source `19aca432` qualifies process-lifetime FAT tree sessions and explicitly
negotiated NDJSON streaming through the common command system. [Exact-source
evidence](../.aide/evidence/2026-10-13-fat-tree-sessions/README.md) records
113 native groups, 26 selected standalone headers, 236 tooling passes and two
skips. Actual CLI/protocol/GUI/TUI/shell journeys and contained worker faults
pass. Complete 17,601-entry trees publish 12,346,398 frame bytes across 138 pages;
one input request carries more than 256 output envelopes while the existing
transport input caps stay unchanged. Four supplemental startup/late cases use
the same frozen binaries and retain their precise observation limits.

The [source map](source-map.md) covers 236 current files. The runtime session
service owns reservation, copied page/record retrieval and stream semantics;
the Windows adapter owns file/ancestor/process lifetimes. They reuse the
traversal and existing contained worker, with normal/fault isolation checked.
The application now groups its observation services explicitly. No new source
root, competing command registry or universal frontend framework is introduced.

This is a qualified ordinary-file prototype in the recorded Windows lane.
Recursive extraction and destination metadata restoration, further formats and
hosts, production/physical/owner/release gates and the full original 0.1.0 scope
remain open. Integration into main is distinct from acceptance or publication.

## Qualified held-file tree checkpoint: 13 October 2026

Source `54376be5` connects directory pages to a held ordinary file and the existing
owned observation-process host. [Exact-source evidence](../.aide/evidence/2026-10-13-fat-tree-file/README.md)
records **111 native groups**, **24 selected headers**, **232 tooling passes**
and **2 skips**. Nine methods cover 57 actual file/process cases. Larger complete
trees publish **12351932 bytes** across up to **138 pages** through one
2 MiB slot, with independent parent replay and actual process/code/request/epoch
binding. Source hashes stay unchanged; sharing, cancellation, late/hung children,
retirement and changed page/reply refusals have retained results.

The [source map](source-map.md) covers **232 current files**. Six new files own
native source lifetime, pure page/input replay and the concrete page channel.
They reuse the runtime traversal and existing process host. The latter gains
only an immutable private binding accessor; no new scheduler, root hierarchy or
raised host limit is introduced. Normal and fault libraries remain separate.

This is prototype contained observation. Public traversal, recursive extraction
and destination metadata restoration remain subsequent work. Retained pages are
historical; source agreement supplies no atomic snapshot, future access or
mutation authority. The full all-platform/storage 0.1.0 remains active and
incomplete, with owner/production/physical/elevation/customer/install/sign/release
gates separate. Tested reviewed dev checkpoints may be synchronized to main
under the existing user grant; synchronization does not accept or publish a release.

The first candidate at `8548b1f2` failed four native groups. Its original results
remain retained. The repaired probe restores the existing parent memory-budget
admission; progressing logical-copy tests use the established finite 90-second
total/30-second no-progress policy, retaining byte, hash, outcome and actual-exit
assertions. The complete passing campaign above belongs to the repaired source.

A read-only GitHub check on 13 October found Universal Setup main `c048f7f1`
and dev `2b7a4d01` unchanged. Draft [PR237](https://github.com/Julesc013/universal-setup/pull/237)
has head `b7db8469`. [Its head's CI](https://github.com/Julesc013/universal-setup/actions/runs/38381202008)
fails `native-windows`; the other six jobs pass. Both public release queries
returned zero entries. These are dated hosted observations, not local Setup
qualification or a diagnosis of its failure. The exact responses are retained
with this checkpoint. No full-release date is supported by the current evidence.


## Qualified directory-paging checkpoint: 13 October 2026

Source `b770b3fe` adds private source-bound directory pages in the existing runtime
capture owner. [Exact-source evidence](../.aide/evidence/2026-10-13-fat-traversal/README.md)
records **110 native groups**, **21 selected headers**, **232 tooling passes**
and **2 skips**. Independent tests cover 17,601 entries, a 1,100-cluster
directory chain, deep parents and lossless names across pages/sectors/clusters.
All page digests and reassembled event streams are independently checked.

The [source map](source-map.md) now covers **226 current source files**. The two
new files own stateful paging, source applicability and resource outcomes;
existing portable FAT allocation/directory decoders retain format ownership.
No new root, competing decoder or artificial frontend hierarchy is introduced.
Source-ID/epoch checks, malformed-directory refusal and output/queue/bitmap
budgets stay explicit. Original deleted/name/boot fragments remain data.

This qualifies a private supplied-region controller. Actual held ordinary files,
contained paged workers, public tree operations and recursive destination metadata
effects remain subsequent work. Old captures/selectors/plans keep their versions.
Source callbacks and hashes prove neither identity authentication nor an atomic
snapshot. The unchanged all-platform/storage 0.1.0 goal is active and incomplete;
owner, production journal, physical/elevation/customer/install/sign/release gates
remain separate. Tested dev checkpoints may be merged to main under the existing
grant; integration does not publish or accept the full product.


## Qualified allocation-continuation checkpoint: 13 October 2026

Source `112aa1e9` adds a private resumable FAT allocation cursor in the existing
`fat.h` and `allocation.c`. [Exact-source evidence](../.aide/evidence/2026-10-13-fat-walk/README.md)
records 109 native groups, 20 selected headers, 232 tooling passes and
2 skips. Independent cases walk 33,000-cluster chains with different page sizes;
cross-page cycles emit no repeated cluster. Capacity/addressability and terminal
versus pending outcomes remain explicit. No product directory or public command
is added, and the source map still covers 224 source files.

Keep the CLI folder and explicit `shell_model`, `tui_model` and `gui_model`
names. Shared terminal/host mechanisms retain their platform owner; shared
semantics retain their runtime owner. [The file map](source-map.md) explains
every current file, and [the structure guide](code-structure.md) records future
responsibility slots. Neither promises that all future private filenames are
known or that no future decomposition will be needed.

The unchanged all-platform/storage 0.1.0 goal remains active and incomplete.
Source/epoch-bound directory pages, recursive extraction/metadata fidelity and
further formats/hosts remain implementation work. Owner, production journal,
physical/elevation/customer/install/sign/release gates remain separate. Tested
agent-reviewed dev checkpoints can be integrated into main under the existing
user grant; that integration does not publish or accept a release.

The read-only GitHub recheck during this checkpoint found Universal Setup main
`c048f7f1` and dev `2b7a4d01` unchanged. [Draft PR237](https://github.com/Julesc013/universal-setup/pull/237)
still has head `0fc1f90d`; [its exact-head CI](https://github.com/Julesc013/universal-setup/actions/runs/38252891691)
fails `native-windows`, with six other jobs passing. Both public release queries
returned zero entries. This is hosted metadata, not a Setup build/install test
or a diagnosis of that failing job. There is no justified full-release date.


## Qualified logical-evidence checkpoint: 13 October 2026

Source `a7041767` qualifies logical extraction evidence/export, independent
destination/map verification and historical joined support. [Exact-source evidence](../.aide/evidence/2026-10-13-logical-extraction-evidence/README.md)
records **107 native groups**, **20 selected headers**, **232 tooling passes**
and **2 skips**. Eight logical verification journeys include actual native
GUI/TUI/shell. All 16 policies and joined exports are independently checked.
Original-source changes do not invalidate the narrower destination/map claim;
later mismatching output does not rewrite the earlier retained observation.

The [source map](source-map.md) still covers 224 source files. Existing evidence,
verification and export owners now explicitly distinguish raw version1 from
logical version2. The verifier also compares backing-resource declarations.
These changes reuse the existing engines and preserve raw formats; they add no
product directory or competing canonical source tree.

The unchanged all-platform/storage 0.1.0 remains incomplete. Larger coherent
traversal, recursive/metadata fidelity, further formats/hosts and production,
owner, physical and release gates remain. Repository integration is separate
from acceptance or publication.

## Earlier shared-command checkpoint at8d1905b9: 13 October 2026

Source `8d1905b9` qualifies `filesystem extract` through the shared CLI, protocol,
native GUI/TUI/shell and existing acquisition worker. The [source-bound evidence](../.aide/evidence/2026-10-13-fat-extraction-command/README.md)
records **106 native groups**, **20 selected headers**, **229 tooling
passes** with **2 skips**, 11 complete verified files and real cancellation/resume.
The initial full candidate failed two exact build-information comparisons; those
expected fields were corrected from the declared logical-provider contract. The
original failed source and terminal logs remain retained.

The [source map](source-map.md) still covers **224 source files** with the existing
owners. No new product directory or duplicate extraction engine was introduced.
The metadata comparison helper moved to the runtime owner needed by inspection
and native acquisition. Compiled catalogs now have a separate finite parsing
budget; external wire request limits remain unchanged and have native boundary
tests. These are demonstrated responsibility/dependency changes, not a wholesale
reorganization or a guarantee against every future refactor.

This qualifies the current prototype, not a frozen production API or full 0.1.0.
Larger coherent traversal, recursive/metadata fidelity, logical evidence export,
other formats/hosts and production/storage/release gates remain open. Branch
integration remains distinct from owner acceptance and publication.

## Earlier qualified backend checkpoint at20ecddbd: 13 October 2026

The [source map](source-map.md) covers **224 current source files**. CLI has its
own folder; shell, TUI and GUI use their explicit model names. Keep the existing
ownership tree and module-qualified includes. The new complete-file acquisition
backend reuses existing owners rather than adding another source hierarchy.

DE-W047 is qualified at source `20ecddbd`: **104 native groups**, **20 selected
standalone headers**, 226 tooling passes and
2 skips. [Exact-source commands, artifacts and evidence](../.aide/evidence/2026-10-13-fat-extraction/README.md)
retain complete mapped FAT12/16/32 byte-content extraction, destination/checkpoint
and resume results in the recorded Windows lane. This is a private backend;
public command/frontend admission, larger coherent traversal and the unchanged
all-platform/storage 0.1.0 remain unfinished. These results do not qualify
metadata restoration, physical writers, production recovery or other hosts.

The first full campaign at `a40c7b43` failed three groups because a normal FAT
provider entered the fault-test executable through a new dependency. Same-handle
metadata capture removed that dependency; the existing build checker now forbids
normal file/snapshot/worker providers in that composition. Old failures retain
their terminal outcomes; the repaired source has its own fresh full campaign.
This is a concrete dependency correction, with no need to move the source owners.

The authorized workflow integrates tested, agent-reviewed `dev` checkpoints into
`main`. Integration is separate from owner acceptance and release. The earlier
upstream observations below are dated; they do not constitute DiskEd/Setup
installation qualification or an estimate for the full release.

## Earlier checkpoint at f8a3eb84: 13 October 2026

Rechecked at `f8a3eb842b68fe0666d01711ce95b5dbc5a6a70f`. Remote `dev` and
`main` both name that revision. The assessment below is retained at its original
base; its references to unfinished DE-W044 and the then-latest native campaign
describe that earlier checkpoint.

GitHub still reports `main` as unprotected. Repository-side enforcement of the
intended protected-main/check policy remains governance work; this documentation
pass does not change repository settings.

The current source map covers **220 source files**. The frontend names and CLI
folder are already consistent. JSON, command and invocation have distinct build
targets; module-qualified includes, generated header visibility checks and shared
GUI/TUI request invariants are implemented. Remaining composition-policy/test-seam
work is SR-05 below. These facts support keeping the ownership tree and improving
individual responsibilities as needed; they do not establish an optimal design
for every future requirement or complete API/ABI portability.

DE-W044 now has retained, implementing-agent-reviewed results at source
`4d3dc0a3cb1597289926cb6e010c57f7156b285d`: **101 native test groups**, 18
standalone header compilations, 68 capture command/frontend cases and 91 store
checks; the tooling suite ran 226 tests, with 224 passes and two skips. See the
[exact-source evidence](../.aide/evidence/2026-10-13-fat-retention/README.md).
Those native results were audited here rather than rerun. The first full native
campaign failed five groups; retained serial diagnostics and a subsequent full
campaign passed with the same source and criteria. The initial failures remain
in the evidence; their underlying cause has not been established.

This adds bounded retrieval of retained FAT metadata in the current process.
It does not implement file-payload extraction, qualify physical writers or
production recovery, or complete the owner-selected all-platform/storage 0.1.0.
The programme's next work remains coherent larger traversal, extraction and
further platform/storage implementation.

Fresh read-only GitHub checks still find Universal Setup main at `c048f7f1` and
dev at `2b7a4d01`. [Draft PR #237](https://github.com/Julesc013/universal-setup/pull/237)
remains open at `0fc1f90d`, with `native-windows` failing and six checks passing
in [run 38252891691](https://github.com/Julesc013/universal-setup/actions/runs/38252891691).
Both repositories' GitHub release collections are empty. Setup runtime/installation
was not tested in this follow-up.

The authorized `dev` to `main` workflow has already integrated the qualified
checkpoint. A release has a separate finish line: exact candidate composition,
applicable platform/operation evidence, packaging and content-inventory checks,
licensing/provenance, required acceptance and publication authority. There is no
evidence-based date for the complete 0.1.0 scope. A smaller preview requires an
explicitly selected scope and version; branch synchronization does not select it.

## Earlier assessment at 607d68a7

Assessment: 13 October 2026, against local `dev` at
`607d68a7c6edefeea93bf17218c2685e787683e2`. Keep the five source owners and make
changes at demonstrated responsibility boundaries. The supplied 12 October review
describes an earlier revision; its embedded recommendations are advisory material,
not execution authority, acceptance or current test results.

The [complete source map](source-map.md) explains and links every current source
file. The [growth table](source-map.md#planned-growth-without-a-second-source-tree)
assigns the specified future capability families to owners and work gates. The
[coding guide](code-structure.md) explains implementation conventions. These serve
different purposes; this dated assessment does not replace any of them.

## Why these names and directories

| Location | What it owns | Why it belongs there |
|---|---|---|
| `apps/disked/main.cpp` | The native product entry function | `main` is the conventional entry name. It delegates startup; it does not own every command. |
| `apps/disked/app.*` | Composition, selected services and frontend routing | All interfaces enter the application. Calling this unit `cli` would misdescribe its scope. |
| `apps/disked/cli/cli.*` | Human formatting for one invocation | CLI is an interface with its own owner. It presently needs no persistent `cli_model` class. |
| `apps/disked/shell/shell_model.*` | Editing, history, completion and a persistent DiskEd command session | A shell model owns session state. This shell parses DiskEd commands; it is not a general OS command executor. |
| `apps/disked/tui/tui_model.*` | Text navigation, forms and result-view state | The explicit basename matches the shell/GUI models. The old `tui/model.*` names have already been replaced. |
| `apps/disked/gui/gui_model.*` | Host-neutral graphical interaction state | The model contains no Win32 window ownership. There is currently no reason to put it under a `win32` child. |
| `runtime/presentation/` | Shared actions, forms, request correlation and presentation rules | Multiple interfaces need the same meaning; none should own that shared meaning for the others. |
| `runtime/command/` | Descriptor parsing, protocol handling, shell grammar and bounded JSON | Parsing a product command is a runtime contract, independent of a CLI, console or particular storage backend. |
| `runtime/invocation/policy.*` | Frontend/output/interaction selection | Policy consumes host observations. It does not open native handles to infer them. |
| `platform/windows/console/terminal.*` | Console keys, rendering mechanics, event loops and owned mode restoration | Shell and TUI both need this concrete Windows host. Neither frontend owns the console mechanism. |
| `platform/windows/ui/gui.*` | Win32 windows, controls, events and lifetime | Native window APIs differ from the shared GUI model's semantics. |
| `platform/windows/invocation.*`, `output.*` | Native launch observations and standard-stream writes | Handle operations belong to the host. Human text formatting belongs to the CLI. |
| `portable/<format>/` | Checked storage-format algorithms over supplied bytes | Decoding MBR/GPT/FAT does not acquire a file, enumerate a disk or select an OS. |
| `providers/<backend>/` | Concrete byte acquisition, observations and effects behind ports | Backend responsibilities differ from format algorithms and process lifetime. Current image-provider code can be Windows-specific; placement does not assert portability. |

Directories name owners; basenames name responsibilities. Use short, descriptive
names and module-qualified cross-module includes such as
`apps/disked/tui/tui_model.h`. `main.cpp`, `policy.cpp` and `snapshot.cpp` are
reasonable within a clear owner. A repeated basename in different modules is not
ambiguous when its include path and target ownership are explicit.

The current tracked source inventory has 218 files; its longest repository-relative
source path is 57 characters. The follow-up checks case collisions and Windows
reserved path components. These observations do not qualify every legacy
filesystem, build-output path or compiler.

A header declares types, ports or functions; its implementation file supplies
behaviour. Header-only value declarations such as `text_input.h` need no empty
`.cpp`. Private headers are not automatically SDK exports. Functions name actions
or observations within their namespace/type; public C symbols follow their
admitted ABI prefix. Keep byte/sector/epoch units, lifetimes, limits and outcomes
explicit. Avoid broad `common`, `utils` or generic frontend base classes without a
real shared responsibility.

## Disposition of the supplied review

| Finding | Current disposition | Evidence and remaining scope |
|---|---|---|
| SR-01: TUI names and CLI owner | Already resolved | `tui_model.*`, `shell_model.*`, `gui_model.*` and `cli/cli.*` exist. No further rename needed. |
| SR-02: misleading JSON target | Implemented and tested | JSON, command/protocol/lexer and invocation have distinct private targets. [Build-boundary review](../.aide/evidence/2026-10-12-build-boundaries/REVIEW.md). |
| SR-03: include ambiguity | Bounded enforcement implemented and tested | Qualified cross-module includes, target-owned headers and generated compile-usage visibility. [Header review](../.aide/evidence/2026-10-13-qualified-headers/REVIEW.md). No wrong-header runtime defect was demonstrated by the supplied review. |
| SR-04: repeated frontend invariants | Shared request/view rules implemented and tested | Pending identity/view epochs and command-view eligibility now have shared owners. [Presentation review](../.aide/evidence/2026-10-12-shared-presentation/REVIEW.md). This does not assert that all form/rendering duplication has disappeared. |
| SR-05: application composition policy | Follow-up remains | `app.cpp` still contains command-specific routing/limits and test hooks. Extract a named service binding or test seam when its contract and consumers justify it; do not create a second command registry. |
| SR-06: map does not enforce dependencies | Separate checks implemented | Source-map coverage remains inventory-only. CMake-derived build/header checks and negative fixtures independently check the selected native lane. They do not establish complete preprocessing, SDK/ABI or every-platform conformance. |
| SR-07: stale first-task pointer | Resolved | Root `AGENTS.md` routes current work through the programme and owning work record. Historical bootstrap and acceptance records remain historical. |
| SR-08: Setup maintenance qualification | Still an upstream blocker | Fresh read-only GitHub observation is below. No Universal Setup repairs or promotion were performed by this follow-up. |

Historical reports keep their original counts and limitations. This follow-up
corrects stale current-guide counts and the overbroad phrase “a parser belongs in
portable”: storage-byte decoding and command/protocol parsing have different
owners. It does not rewrite old evidence to describe newer tests.

## Growth and compatibility

Plan owners and interfaces now; choose new concrete files when their behaviour is
specified. Before adding a file, identify its responsibility, input/output contract,
resource/lifetime owner, allowed dependencies, target and applicable tests. Add its
source-map explanation, build/context inputs and tests together. Split an existing
unit when distinct contracts, effect ownership, consumers or target requirements
make that useful. Line count or visual symmetry alone is insufficient.

The growth table covers filesystems, journals/recovery, operation planning,
privileged execution, acquisition/evidence, specialized media, pools/shared storage,
historical/current hosts, GUI toolkits, integrations, SDKs and delivery. It is not a
claim that those implementations exist. Listing every future function or creating
all possible folders would freeze guesses without proving compatibility.

Stable commands, schema/requirement/target IDs and admitted public/durable formats
carry compatibility obligations. Private paths, classes and build targets can
evolve with updated references, tested consumers and retained revision-bound
evidence. The current C++14/Win32 composition does not qualify DOS, legacy Windows
or other platforms merely because some algorithms use C90. No truthful design can
promise zero future refactoring or universally optimal filenames.

## Development, branches and releases

At the 13 October review, the retained native campaign was source `543826fe`: **99 native groups**, 17
standalone headers, 34 FAT allocation-window cases and 44 window command cases;
tooling recorded **222 passes and two skips**. Those are
[retained exact-source results](../.aide/evidence/2026-10-13-fat-window/summary.json),
not a fresh native campaign for this documentation follow-up. The executable has
real Windows interfaces and bounded ordinary-file capabilities. Product physical
writers, production recovery and full all-platform/storage **0.1.0 remain unfinished**.

At the initial read-only branch check, remote `dev` was `607d68a7` and `main` was
`f9f85dac`. The difference defines DE-W044 retention/retrieval; its implementation
is unfinished and unqualified. The authorized workflow is to push checkpoints to
`dev` and promote tested, reviewed checkpoints to `main`, without force pushes.
Repository synchronization does not itself accept an implementation or publish a
release. Follow the programme for subsequent branch/work state.

On 13 October, Universal Setup main was `c048f7f1` and dev was `2b7a4d01`.
[Draft PR #237](https://github.com/Julesc013/universal-setup/pull/237) had advanced
to `0fc1f90d`; its [exact-head CI run](https://github.com/Julesc013/universal-setup/actions/runs/38252891691)
still failed `native-windows` while six other jobs succeeded. The failed-job log
reports failure of the owned SYSTEM standard fixture and later receipt-count
errors. These are observed diagnostics; this follow-up did not independently
diagnose the underlying cause or run Setup.
DiskEd's fixture/source-consumer work is not live lifecycle qualification. Both
GitHub release collection queries returned empty lists.

There is no evidence-based release date yet. The full 0.1.0 scope selected by the
owner remains unchanged. A smaller preview would need its own explicit scope.
Release requires exact candidate artifacts, applicable target/operation tests,
packaged consumer and content-inventory checks, honest capability limits, licensing
and provenance, required acceptance and publication authority. A naming change
does not supply these results.

The review then selected DE-W044; subsequent work is recorded in the dated
updates above and the current programme. Preserve the current source owners;
address the remaining composition/test seams during implementation and qualify
each capability against its actual contract.
