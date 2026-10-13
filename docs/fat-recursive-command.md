# Recursive extraction command development

DE-W057 is active. Its [expected contract](../spec/catalog/fat-recursive-command-prototype.json)
requires common-service and actual CLI/protocol/GUI/TUI/shell admission plus a
durable ordinary-file operation lifecycle. The qualified private
[DE-W056 backend](fat-recursive-extraction.md) supplies the create-only effects.
This task preserves the original full platform/storage programme.

The sole proposed command registry records `filesystem.tree.extract`, with CLI
spelling `filesystem extract-tree`. The Windows native image prototype composition
now selects its implemented handler; global contract acceptance remains pending.
Its provisional parameter bindings and shared native command ports serve all
product frontends. Neither `filesystem extract tree` nor
`filesystem tree extract` can be added without reinterpreting operands of an
existing command. The existing file extraction and tree inspection keep their
identities and grammar.

`runtime/acquisition/fat_tree_review.*` is the first implemented prerequisite.
It validates an immutable private review definition over supplied data. Its
stable backend projection retains source/epoch/window/copy, namespace commitment,
locations, resource identities/epochs/access/aliases/footprints, verification,
metadata policy, budgets and execution generation. Worker PID, capture ID and
capture sequence remain in the original process-bound definition and later
receipts. The qualified private plan1 keeps its existing digest and meaning.

The review also declares an operation-store dependency. Its current prototype
control footprint names `recursive-request.json`, `recursive-cancel` and
`recursive-state.ndjson`; state records are bounded to 16KiB, history to 1MiB
and 64 records. The original metadata ledger has its own independent budget.
The store, source, destination, ledger and declared host effects require separate
exact-review grants. Admission must observe actual store/source/code ownership,
freshly prepare the backend and compare the complete intended effects before
creating any output. No incidental state path is implicit.

The pure review layer opens no path and grants no effects. A valid supplied
store identity or matching hash is no proof of native ownership or operator
authentication. Its comparison and grant checks are semantic prerequisites;
they do not themselves implement native admission, reconnect, cancellation or
frontend exposure. The native prerequisites described below remain separate.

The private Windows `fat_tree_store.*` and `fat_tree_admission.*` adapters now
observe an actual pinned NTFS store and prepare a fresh owned backend. Execution
validates all five grants before native paths are touched, compares the actual
store and freshly prepared intended effects, claims the request name with
`CREATE_NEW`, and creates cancellation/state files without clobbering.
Current-user ACLs, retained file/ancestor identities and declared reserved names
bound that control footprint. Foreign and partially initialized resources stay
in place.

The flushed request binds the immutable review, operation ID, actual process/
attempt/worker identities, private preparation digest and created file identities.
A state hash chain records admission and dispatch intent before the worker grant.
Publication and actual exit are separate facts. Progress may coalesce; terminal
record slots are retained. A request header is limited to 512KiB, a state record
to 16KiB, and request/cancel/state together to 1MiB and at most 64 state records.
The original extraction metadata ledger remains a separate resource.

The store joins the existing worker's dependency closure before launch. If
retirement cannot establish exit, the same passive retained owner keeps store
handles along with source/code/ledger dependencies. No new scheduler or automatic
cleanup/replay is introduced. These private native controller tests do not yet
provide common-service reconnect or actual frontend/public-command admission.

The focused native fixture prepares the same generated image in two real
owned processes without output. Their process-bound digests differ, while the
stable effect review agrees. Independent tests cover exact review hashing,
every grant, intended-effect changes, strict shapes, aliases and finite bounds.
Run `acquisition.fat_tree_review` with CTest after building its probe, the
owned preparation probe and selected standalone header. Full DE-W057 native,
interface and clean-source qualification remain separate.

The pure `runtime/acquisition/fat_tree_operation.*` reader now validates the
retained request and canonical bounded state chain. It binds operation, review,
attempt, worker identity and progress; checks grant ordering and outcome
conservation; and preserves incomplete tails as uncertainty. It reads both the
original request1 and the new request2, which records controller and writer
process births. A hash chain is consistency evidence, not authentication.

The Windows `fat_tree_reconnect.*` adapter independently opens an existing
pinned NTFS store and checks actual control-file identities, host, process
births and executable generation. It reports retained history separately from
current controller/writer observations. It neither opens the acquisition source
or destination nor restarts, replays or repairs an operation. Cancellation only
writes the existing flag after an intact request2 history and matching live
controller/writer are established. The owner forwards that request to its worker;
the flag alone proves no acknowledgement or exit.

Focused reconnect validation passes 38 cases in ten methods, including a live
second caller, cooperative cancellation, published outcomes before child exit,
torn histories, changed identities and contradictory rehashed records. The
existing admission group also passes 41 cases in eleven methods. Two selected
new headers and generated dependency checks pass. These are development results
on the current Windows host, not full work-unit or release qualification.

The private Windows `fat_tree_controller.*` now hands execution to a detached
same-executable controller. The caller validates the exact review and all five
grants, launches behind a closed gate, then explicitly dispatches. Abandonment
before dispatch admits no source/store/output work. After dispatch, caller exit
does not cancel the controller or its existing admission/store/worker owner.
Only bounded input/output mappings, gate/abandonment events, a parent wait handle
and query-only job handles are inherited. Standard input/output/error are absent.

The controller retains the existing aggregate worker budget and a two-process
job without kill-on-caller-handle-close. Preparation is bounded to ten seconds;
execution has a 30-second progress-stall and one-hour absolute budget. A reached
budget stops and retires the existing owned worker, preserves partial/uncertain
evidence and never dispatches a replacement. An unresolved exit keeps its
dependency owner alive. Test-only shortened stalls and controller-exit injection
are excluded from the normal binary.

Focused native controller tests pass ten methods. They cover actual caller exit
and exact FAT12/16/32 output, closed-gate abandonment, every grant, stale source
and code, repeated launch/dispatch, separate-caller cancellation, hung-worker
retirement, published-before-exit and controller exit after admission. Retained
observations and current process facts remain separate. A matching exited handle
can establish process exit even when Windows no longer exposes its image path;
only a live matching code generation can authorize cancellation.

The pure `fat_tree_watch.*` projection and native reconnect adapter now provide
bounded wait/watch prerequisites. Cursor zero includes the admission record as
event one; retained state records keep their existing zero-based indices. Every
event carries the exact raw-record digest (canonical JSON plus LF), immutable
header/review binding, worker epoch and one fresh observer identity. Resumption
requires the exact prior sequence, digest and worker. A changed or shortened
prefix is a conflict; a torn history is unknown and is never repaired.

Observation admits at most 64 events, 16KiB per event and 1MiB total event bytes.
A rejecting or throwing sink closes only that observer and preserves its last
admitted cursor. Wait begins with a snapshot and follows subsequent records.
Following permits 0–2000ms and at most 81 polls at 25ms intervals. This bounds
following between native calls; public callers still need the existing request
containment for a blocked OS API. A live controller can finish flushing an
already exited worker's record within that budget. Until the retained exit
appears, uncertainty remains explicit.

Focused tests cover exact event/digest domains, resumption/snapshot, cursor and
header conflicts, malformed options before paths, torn histories, stopped sinks,
event budgets, unchanged artifacts, actual detached cancellation/resumption and
publication before recorded exit. These are private development prerequisites.
Product dispatch, compatible protocol readers and actual CLI/protocol/GUI/TUI/
shell journeys remain unfinished. The public command stays planned until those
gates and the full clean-source campaign pass.

The [canonical command schema](../spec/schemas/fat-recursive-command-parameters.schema.json)
now binds `prepare` and `execute`. Preparation takes source/destination operands,
an explicit ledger and existing operation store, selected volume offset/size/copy,
capture epoch and explicit OEM code page 437 or 850. Defaults are
`long_or_short`, `refuse`, `preserve_raw` and offset zero; `fixed_offset` requires
an explicit offset. The review includes the resulting complete policy and finite
backend budgets. Execution takes the immutable definition, exact digest and five
separate grants. It accepts no preparation fields or unknown options.

The digest preserves the private review1 domain: SHA-256 over UTF-8
`disked:fat-tree-extraction-review:1`, LF, then canonical immutable review JSON.
The [closed review schema](../spec/schemas/fat-tree-review-prototype.schema.json)
covers structural fields; runtime review validation and native ownership checks
also enforce resource hashes/aliases, ranges, counters, policies and freshness.
This inline prototype binds at most 32KiB of definition inside the existing
64KiB request frame. Oversized definitions are refused, never truncated. It is
not a permanent storage ABI.

`runtime/acquisition/fat_tree_commands.*` owns shared command checks and outcome
translation. `platform/windows/storage/fat_tree_actions.*` binds the existing
owned preparation and detached execution. Preparation succeeds only after actual
preparator exit. The caller now allocates one proposed operation identity before
dispatch; a delayed acknowledgement can return unknown with that ID for later
inspection. The new controller input2 supplies the same ID to native admission.
A proposed ID proves no claim or accepted operation; the retained request2 and
admission acknowledgement supply those later facts. Existing review/header
formats and unrelated commands retain their meanings.

The private command probe executes the canonical CLI parser, shared form
conversion and protocol handler against actual native ports. It tests generated
FAT12/16/32 preparation/execution, exact destination/source bytes, every grant,
policy and shape errors before provider calls, stale source, duplicate execution,
reply/identity/exit constraints and independent schema agreement. These are
shared-service development results; they are not actual product CLI, window,
terminal, shell or release qualification.

The gated `disked_recursive_test` development composition now connects that same
service to actual CLI/protocol, native Win32 GUI, TUI and interactive shell.
Normal `disked` still reports extraction unavailable and refuses a recursive
operation selector before native paths. Only the development target registers
the capability-bound same-executable controller/writer roles. No release or
physical authority is added by that compile-time selection.

Actual journeys prepare and execute generated FAT12/16/32 trees, preserve source
bytes and verify exact output. Native GUI/TUI/shell journeys require separate
review and submission, then watch the retained completed operation. Owned console
fixtures verify restoration. Protocol watch negotiates
`org.disked.fat-tree-operation-events/1`, emits exact record events, and ends with
one response containing the final cursor and an empty event array. Wrong features
and missing grants refuse without output.

Recursive responses have an explicit two-MiB wire lane (including LF); existing
response lanes retain their bounds. A separate request-channel regression sends
an envelope larger than one MiB through that lane and verifies smaller/invalid
lanes refuse. Object forms accept the declared 32KiB definition budget. Existing
request/output timeouts and occupied-slot retention remain.

The compatible event reader preserves outer/payload additions while checking
required features, exact header/review/worker/request/observer bindings, raw
record digests, contiguous sequences and transition consistency. Full replay
checks the entire retained prefix. An explicitly requested snapshot validates
its actual record and later continuity, but reports
`omitted_prefix_verified: false`; it cannot prove omitted history or authenticity.

The separate `disked_recursive_fault` fixture executable adds execution-only
worker controls and three retained-store write/flush controls. They enter the
bounded private controller fixture; public parameter schemas reject them. The
ordinary development composition ignores those environment controls, and normal
`disked` continues to refuse this backend. Shared inline file fault definitions
must be consistent within the fixture composition; its controller transfers the
selected store control explicitly rather than weakening the child environment.

Actual CLI/protocol/GUI/TUI/shell callers now request cooperative cancellation
after the launching client has exited. Tests require the same retained operation,
recorded partial outcome, cancellation observation and unchanged source bytes.
Store full/short/flush failures preserve created resources and refuse repeat
execution. An intact prefix can be successfully inspected while the logical
operation remains unresolved; request completion is not operation completion.
Changed source generations, stale digests, injected public fields and foreign
control resources refuse before extraction effects.

Actual interrupted NDJSON output now proves that a closed watch pipe seals its
caller, preserves the same live controller/writer and permits digest-bound cursor
resumption without cancellation. Unresponsive and abruptly exited generated-image
writers retain unresolved exit histories and refuse replacement execution. These
are actual product composition journeys under the existing controller budget.

The [strict event producer schema](../spec/schemas/fat-tree-operation-event-prototype.schema.json)
closes emitted envelope, payload, record, worker and outcome fields. Automatic
semantic dispatch checks bounded integers/frames, original-record SHA256 plus LF,
sequence domains, process/dependency/grant/phase and outcome bindings. Native
history validation additionally checks complete transitions, exact header/resource
constraints and actual native facts. Compatible Reader acceptance remains separate:
it can preserve additive outer/payload observations while rejecting unknown required
features. A conforming event neither authenticates a producer nor grants replay.

The actual frontend campaign exposed an exit race: two process observations could
produce `worker.observation=running` with `dependencies_retained=false`. The worker
now derives both facts from the same observation; the original contradictory ledger
is retained and per-observation consistency has explicit native regression checks.

The normal `disked` Windows image prototype now links those nonfault action,
controller and worker implementations and selects recursive extraction in its
build profile and generator allowlist. The separate disabled executable verifies
unavailability before paths; the separate fault executable retains bounded fixture
controls. There is no longer a duplicate nonfault recursive test composition.
Historical gated reports above keep their original scope and revisions.

The [strict response producer schema](../spec/schemas/fat-recursive-response-prototype.schema.json)
defines preparation, controller execution, unresolved requests, inspection and
watch results separately. It binds review hashes, response/receipt/admission IDs,
controller births, process/grant/store facts, terminal worker outcomes and finite
history/cursors. Refusal before admission may carry a null admission receipt;
accepted and completed operations require the corresponding actual receipt.
Help/discovery uses its own response contract and never initializes this backend.
Native resource freshness/full-history verification and actor authority remain
separate. No schema freezes this prototype as a production public or journal ABI.

Actual normal CLI/protocol/GUI/TUI/shell success and fault journeys now pass typed
response validation and independent mutated-response refusals. Full clean-source
qualification remains before DE-W057's review boundary; full0.1.0 and owner,
physical, other-platform and release qualification remain open.
