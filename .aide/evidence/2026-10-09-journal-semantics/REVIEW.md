# Implementing-agent review of semantic binary declarations

Reviewed source `0aed6f813a58947a413d73a51c0c4f12e005f84e` against base
`3c948562cff7580e3598056784629a698a345139`, the DE-W040 work record and DE-042/043/041/045.
This supports continued local fake-model implementation under the user's recorded
policy. It is not owner acceptance, authenticated writer admission or independent
safety qualification.

Expected plan/resource/provider digests are checked against the independently
supplied definition before source reads. Expected journal identity binds framing;
every record matches an externally supplied binary publisher and epoch. Publisher
and worker identities remain separate. A definition payload must equal the exact
expected canonical bytes. Critical schemas, fields, canonical encoding, receipt
references and scope are checked; compatible observations remain opaque and do
not alter mutation declarations. Standalone v1 receipt idempotency is unchanged;
this stricter private journal rejects repeated critical IDs.

The state projection enforces one pending intention, admitted predecessor closure,
whole-plan resource state/identity/epoch capture, contiguous per-attempt event
sequence and increasing capture domains. Completion requires a matching intention,
qualified fake flush declaration and a newer after-state capture. Cancellation
blocks later intention without closing uncertainty. Recovery checks declared exit,
flush/capture order and exact states. Before-state evidence does not itself admit
replay, and a prior intention on a nonreplayable step blocks checkpoint retry.
A checkpoint references the exact binary recovery-record digest, retains original
admission scope and requires a new attempt, newer worker and capture; v1 basis
observations do not become new authority.

Seal validates declared completed/cancelled scope and a post-exit capture. Its
terminal observation remains historical data. Every projection, including a
well-formed terminal one, retains false authentication, effect/replay/retirement
authority and durability qualification, and requires live reconciliation. Native
code has no effect or file-writing port. It copies semantic state for each visited
record and commits only after full validation. Independent valid-prefix controls
check that refusals and torn/corrupt inputs do not partially promote receipts,
captures, completions or terminal outcomes.

Retention is limited by receipt count and cumulative canonical definition/receipt
bytes, with separate event, attempt, source, record and read limits. These are
structural bounds, not measured allocator or elapsed-time guarantees. Receipt
inspection currently revalidates the bounded retained ledger and copies its
projection per record; a later production reader needs its own performance and
failure evidence rather than assuming this prototype's limits qualify it.

This reader validates consistency of assertions, not their origin or truth. It
does not inspect live resources, prove OS worker exit, establish flush guarantees,
implement locks/fencing or authorize effects. The closed guarded model's event
producer still needs explicit typed binary integration; its 131072-byte wrappers
are not this profile's 65536-byte payload ABI. All four private libraries stay
outside the product link closure. Scoped current tests do not replace the other
43 native groups or historical platform/hardware qualification. DE-W040 remains
incomplete, and owner acceptance plus DE-DEC-004/008 remain pending.
