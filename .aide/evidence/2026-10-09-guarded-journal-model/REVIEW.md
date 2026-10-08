# Implementing-agent review of the guarded component

Reviewed source `09bb6cb5c39f75a3fb81a3678ebf258930656419` against base
`5d9039db5d05613623082419a20bbf66a1b6012c`, DE-042/043/041/045 and the selected
DE-W040 contract. This review permits continued local fake-model implementation
under the recorded user policy. It is not owner acceptance or independent safety
qualification, and does not admit a storage writer.

The model orders durable admission, fresh resource capture, intention append and
acknowledged journal flush before dispatch. A reported after-state does not close
the step: qualified target flush, newer capture, matching postconditions and
acknowledged completion follow separately. All participating resources keep their
plan-basis or latest completed state; future targets cannot silently change while
another step executes. Target identity/epoch/availability and journal dependencies
are checked at their barriers. Late results cannot write a replacement target's
current fake alias or promote stalled work to completion.

Operation, attempt, worker, capture, effect, cancellation and recovery states stay
separate. Timeout keeps uncertainty and dependencies; explicit worker exit does
not establish postconditions. Reconciliation needs exit, newer capture, qualified
recovery flush and another capture. A before-state may propose replay only when
declared replayable if a stable intention might have authorized an effect. The
closed fake flush/dispatch assumption can prove an unstarted step from a complete
prefix without intention; this is expressly not a rule for missing physical
journal evidence. A replacement receives a distinct attempt, newer worker epoch,
durable checkpoint-bound model admission and fresh capture. The original v1
admission's observations are not reinterpreted as current authority.

Cancellation request, durable request, checkpoint acknowledgement and final seal
are distinct. Client attachment does not affect execution. Partial tails and old
journal generations are retained with independent digest checks; forking never
restarts a worker by itself. Crash recovery quarantines even a sealed prefix until
live fake resource observations qualify it. Dependency retirement eligibility is
only a reported model predicate; resources remain retained and no unload port
exists. Illegal actions preserve the entire snapshot, while injected environment
failures explicitly record unresolved state.

Independent Python fixtures choose outputs, resource states and crash fates before
running native code, hash every returned history, and check all refusal states
unchanged. They cut healthy execution at every action boundary and exercise
volatile/stable prefixes, late/stale workers, failure barriers, cancellation,
retained generations and selected byte/count/u64 limits. The exact 65536-byte
definition regression covers the larger event wrapper and recovered history.
Exploratory fixture defects and five native defect categories remain recorded
with failed logs, JSON and selected source snapshots. Expected safety outcomes
were not changed to conceal native failures.

This remains a closed fake-memory model, with explicit stable/volatile flush and
worker-exit assumptions. It has no file/device/process port or authenticated
authority. Resource identities changed by fixtures remain quarantined; old/new
device contents and real fencing are not simulated independently. Its hash-chained
JSON events have a private 131072-byte bound and are not the binary codec's
65536-byte payloads. A future bridge must bind and validate actual bounded binary
payloads, not wrap these model events as an assumed production ABI. Real durability
adapters, trustworthy process/observer evidence, physical power-loss qualification
and independent safety review remain required. All three private libraries stay
outside the product link closure. DE-W040 remains incomplete, and DE-DEC-004/008
and owner acceptance remain pending.
