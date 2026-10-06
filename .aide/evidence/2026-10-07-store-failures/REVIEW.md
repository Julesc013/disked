# DE-W017 partial local agent review

Reviewed `b8de3be9094718c0170f5cd2980abd0b6d3448d5` against `e4acbefd76ecff4daf3c3ed5f2fb7f419fc9ef15` and the DE-015/045 store-failure contract.
This is implementing-agent review under the user's continuation grant, not owner
acceptance or independent security review. The acceptance ledger remains empty.

- Identity and serialized claim bytes are allocated before exclusive file
  creation. Once creation succeeds, its write/flush enters the same unknown
  admission guard as subsequent setup. No failed claim is removed or reused.
- Cancellation open/validation/seek failures remain distinct from attempted
  flag writes. A failed write/flush retains the known ID, preceding observation
  and unresolved cancellation receipt. The real worker decides whether it saw
  the flag; no response infers acknowledgement from a request.
- API error state is captured before exception allocation. A successful API
  call reporting a short write receives ERROR_WRITE_FAULT instead of retaining
  an unrelated last-error value. Store failures never create a force/retry path.
- Test-only boundary injection is compiled solely into disked_store_fault.
  Product tests show its environment control has no effect. Every fault uses
  owned disposable files, finite workers and exact process identity before waits;
  cleanup does not terminate a worker by name or delete a live user's store.
- The 15 record-error combinations preserve transition ordering and no replay.
  Complete terminal content is explicitly distinct from successful durable
  flushing. These fake records remain provisional observations, not a qualified
  production journal or post-power-loss claim.
- All 26 native groups pass from a fresh source checkout, covering prior
  worker/cancellation behavior, transport waits, interactive frontends and
  essential-command isolation as well as the new failures. Strict response and
  fake-operation producer checks retain applicability to their exact artifacts.
- The common-job memory experiment is separate evidence for the next task. It
  adds no product budget, privilege, breakaway behavior or completeness claim.

The checkpoint supports continued local DE-W017 development. Memory admission,
combined provider failures and event-stream scope still need implementation and
evidence. Full 0.1.0 and DE-W017 completion are not established.
