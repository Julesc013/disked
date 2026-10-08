# Implementing-agent review of native model-history projection

Reviewed source 028d3c3c3ea20846e07e880b29c0bef9cce8ca2e against base
63554a279a57017d4786f398042b136e15debee8, DE-W040 and DE-042/043. This review
supports continued local development under the recorded user grant. It is not
owner acceptance or independent safety qualification.

The producer is separate from disked.exe. It accepts an expected immutable
definition, journal/publisher bindings and bounded closed-model histories. It
checks fake frame shapes, canonical chains, retained generation counts, entry/
byte budgets and partial candidate binding. Canonical typed payloads include
actual recorded fake capture, flush and exit fields. Per-attempt event sequence
comes from ordered retained frames, and checkpoint references bind the exact
recorded recovery frame through its corresponding binary digest. Definitions and
initial receipts keep their raw canonical payload identities.

A fixed externally supplied binary journal/publisher domain covers the retained
lineage. Diagnostic fake generations remain separate. Copied prefixes keep exact
binary bytes and references. Compatible-reader semantic inspection retains all
produced bytes on a contradictory record, alongside the last accepted projection;
no repair, replay or dependency release occurs. Projection failure returns no
partial successful result. Header bytes are generated for inspection, not observed
persisted evidence. Zero stable entries map to zero stable_bytes; positive extents
are fixture coordinates rather than a durability grant.

Partial JSON tails retain their complete candidate in the model. The producer
uses an explicit half-record binary fixture cut from that candidate; it does not
claim original torn JSON bytes came from a binary writer. Before-append failures
add no record, and failed/unqualified flushes add no acknowledgement. The model's
existing qualified fake stable-memory assumptions remain explicit and separate
from physical/OS claims.

Ordering corrections require newer critical capture claims, post-exit seal
captures, and before-state reconciliation for cancellation with an unresolved
intention. Recovery/seal claims for an already exited attempt retain its original
exit epoch; new admission resets that declaration. Regression fixtures retain the
old rejected paths and supply actual missing actions to healthy histories. Tests
never relax expected budget limits or discard contradictory histories.

The independent Python encoder compares actual native generated payload and
framing bytes, SHA-256 chains, stable coordinates and copied generation prefixes.
Native reader controls cover every healthy record boundary and selected partial
prefix/body/trailer cuts plus retained partial histories. Rejection fixtures check
shape, chain, generation/stable-prefix budgets and a self-consistent contradictory
resource declaration that stays in returned bytes. These tests validate fixtures
and declaration consistency, not the truth or authority of arbitrary input labels.

DE-W040 is still partial. A further fault/prefix audit should cover repeated
crashes after recovery/checkpoint/cancellation, reconstruction of proof dependencies
and repeated resource changes before considering live adapters. Serialized-byte
limits are not measured allocator, time or hardware guarantees. All five journal
prototype libraries remain outside the product link closure. DE-DEC-004/008,
owner acceptance, real observer/flush adapters, independent safety review and
physical/historical-platform qualification remain separate unresolved gates.
