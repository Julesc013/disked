# DE-W017 partial local agent review

Reviewed `a30313c09f4ba8de5770fea041ae1c71db015f55` against `37d69d2fdcaa9f4bc615b7346322ff9daeec4487` and amended DE-022/028/045. This is
implementing-agent review under the user's local continuation grant, not
independent security review or owner acceptance. The acceptance ledger stays empty.

- CLI/stdio callbacks capture immutable request values only. Timeout preserves the
  original occupied slot and preconstructed unknown receipt; no cancellation or
  replacement callback follows. Completed late results cannot become a different
  request's reply. The existing request channel rejects malformed/oversized replies
  and reports callback allocation failure using a preallocated receipt.
- Known operation identity and explicit state directory remain in timeout results.
  A start whose ID was not yet observed stays unknown. Same-store reconciliation
  uses the immutable claim and does not repeat the synthetic effect.
- Protocol dispatch remains sequential with one bounded response per input. It
  cannot dispatch the next request while blocked on output. The Windows adapter
  duplicates only a supplied standard handle; its output thread owns immutable
  bytes and never takes a FILE stream lock. Wait expiry seals the channel before
  requesting cancellation on that presentation thread. No storage thread is killed.
- CancelSynchronousIo is a request, not evidence of completion. Buffer/handle
  ownership survives the frontend wait. Partial bytes are not erased, retried or
  followed by a replacement machine frame. Process exit 4 describes failed
  delivery, independently of the admitted worker's verified result.
- Human text formatting and machine serialization use the same prior values;
  only the output sink changes. All 25 native groups pass on the clean source,
  including console restoration, GUI/shell state, reader/protocol behavior and
  worker independence. Producer-schema checks include the new unknown receipts.
- Test-only delays remain separate executable definitions. Actual pipe
  backpressure is distinct from the injected ordinary-file delay. The failed
  buffered-prefix test and exact repair are retained rather than hidden.

This slice is suitable for continued local development. Whole-frontend memory,
full destinations, public event streams and combined provider failures remain
open. No full DE-W017 or 0.1.0 completion, new privilege, hardware qualification,
owner acceptance or external publication is recorded.
