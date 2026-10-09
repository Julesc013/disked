# Repeated-crash defects and corrections

Base revision: 6422c1801396a4badc4843d396e28e539eb5785d.
Corrected source checkpoint: 5adb71431d3b048eafc04d7de43fdc874f96466b.
The exact baseline probe from source 028d3c3c3ea20846e07e880b29c0bef9cce8ca2e
was checked against its previously retained hash. Initial probes confirmed five
failures establishing two model reconstruction defects; the reader correctly
rejected the contradictory histories. The exact five canonical requests and
baseline native output were retained and the failures were rerun against the recorded baseline.

After a second crash, recover_prefix replaced an exit epoch already declared by
recovery/seal with the newer crash capture epoch. Later typed recovery then
contradicted the retained original exit. Reconstruction now remembers an exit
proof in the selected current-attempt prefix. It uses a new crash observation only
when that prefix has no exit declaration. Checkpoint admission resets that proof
for the new worker attempt.

Applying a restored checkpoint also left the prior attempt's stable intention
flag set. A new attempt with no intention could therefore append after-state
reconciliation, even though the semantic reader correctly rejected it. Applying
admission now clears pending/intention/retry/result and flush/exit state and their
capture coordinates. Cumulative completed steps/resource states remain retained.
The missing-intention probe now rejects without changing any model state.

The five initial cases passed after the fix. An independent action-cut oracle then
expanded the audit through before/after recovery, cancellation and seal/fork traces,
including complete volatile prefixes, partial next records and unflushed dispatched
write fates. Further cases cover failed recovery/checkpoint append and flush,
aborted identity reuse and resource identity/epoch/state/availability changes.
The final audit contains 259 cases, 6370 actions and 326 binary generations.
Every rejected action must preserve its previous snapshot; generated binary bytes
are compared with independent Python encoding. No failing expected outcome was
changed to fit the implementation.

The observed defect belongs to private closed fake-memory models. No product
writer, physical target, elevation, customer media or hardware durability was used
or qualified. Historical publisher declarations still establish no real authority.
Preliminary working-tree logs and retained baseline counterexamples are distinct
from the final clean source-bound reproduction.
