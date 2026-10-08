# Retained semantic-reader findings

This campaign uses independently generated in-memory binary journals and fake
definitions/receipts/captures. It tests declarations and prefix consistency;
it does not qualify real storage, process exit, authenticated authority or replay.

The first 174-scenario run failed four fixtures. Two nonreplayable-step fixtures
named the already completed first step in their recovery claim, instead of the
pending second step. Two record-kind mismatch fixtures reused an earlier receipt
ID, so the native reader refused that identity before reaching the intended kind
check. The fixtures now name the intended step and use new IDs for kind mismatch.
The native source and required refusal/consistency behavior did not change.
`working-initial-cases.*` retains the failing inputs/output hashes and diagnostics.

Full valid-prefix controls then exposed a fixture aliasing defect. `Trace.request`
shared the mutable bindings object; altering an expected binding for a negative
case also altered the trace used to build its control. The three controls therefore
failed their independently expected binding check. The fixture now copies expected
plan/bindings into each request. `working-prefix-controls.*` and
`before-fixture-binding-copy.py` retain the old observations/generator. The repaired
174-scenario run passed, including full projection comparisons against controls,
in `working-fixture-bindings-repaired.*`.

Additional exact-65536-byte definition, event/receipt ID, old-worker, capture-domain,
cancellation, attempt-count and critical-compatibility cases passed 187 scenarios.
The maximum-plan generator was moved to the independent definition fixture module
for shared use by guarded and semantic tests; it still constructs exact bytes
without native output. Coupled retained-byte fixtures then passed 189 scenarios:
the last complete grant prefix within 1 MiB is accepted, while the next whole grant
is refused without changing the accepted prefix/projection. The 128-receipt,
1024-event and four-attempt limits are also exercised at and beyond their boundaries.

Each scenario has a separately submitted complete-prefix control. Binary framing,
header/resource/provider hashes, critical payloads, captures and expected outcomes
are chosen before native execution. Rejected records, source failures and torn
tails must preserve the entire projected declaration state and accepted byte/digest
prefix. All outputs retain false authority/durability/replay/retirement flags and
require live reconciliation, including declared terminal outcomes. Unknown
noncritical observations stay opaque without changing mutation declarations.

No native defect was established by the retained exploratory failures in this
turn; they were fixture construction/isolation defects. This does not establish
that the reader has no defects. It validates the selected private contract and
vectors only. The guarded model's native event producer is not integrated with this
reader. Caller-supplied exit/flush/capture declarations remain unauthenticated data.
Real adapters, independent safety review, physical durability and production
decisions DE-DEC-004/008 remain pending.
