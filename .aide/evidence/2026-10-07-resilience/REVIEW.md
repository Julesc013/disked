# DE-W017 partial local agent review

Reviewed source `ee7cfb6984c1049cad3b3bdc53fa615687c4f244` against `4b1be0facb5648da49557337609c503573f0b72c` and the amended DE-015/024/045
contracts. This is implementing-agent review under the user's continuation grant,
not independent security review or owner acceptance. The acceptance ledger stays
empty. This checkpoint can feed continued local DE-W017 work; it does not complete
the unit or the 0.1.0 programme.

- Background calls own immutable request data and shared channel state; they do
  not capture GUI, session, view or host objects destroyed on frontend exit.
  The channel has one callback and one completion slot and no replacement retry.
  The three frontends consume completion on their own event loop and retain the
  same correlated request and operation semantics.
- Review remains consumed before dispatch. Pending is private state, not an
  accepted-running response. View/selection/form changes guard GUI/TUI late
  outcomes; shell input remains inert and secret-marked replies remain suppressed.
- Failure receipts are prepared before callback admission. Malformed, oversized,
  exception and actual per-thread C++ allocation denial paths preserve unknown
  status. Protocol frame limits remain unchanged; larger GUI limits apply only
  to the two-response private display, with lossless compact whitespace fallback.
- Both Windows jobs are applied during CreateProcess via JOB_LIST. Detached
  creation removes the hidden console host observed in the first aggregate probe.
  Existing job limits are verified, never reset; no breakaway or kill-on-close
  policy is introduced. Named-job/accounting scope and same-user limitations are
  explicit. Post-claim platform failures retain unknown state and platform code.
- Tests observe exact process creation identities, retained immutable claims,
  worker lifetime after frontend/client exit, actual committed-memory denial and
  exact current/earlier payloads. CTest serializes fixtures sharing the worker job.
  Initial failing observations remain available; test-harness repairs did not
  lower the 250 ms criterion, disable product validation or delete failed evidence.

Remaining engineering: synchronous CLI/stdio file waiting, slow consumers and
backpressure, frontend memory, full destinations and combined provider faults.
The detached thread is not process isolation or proof that Windows can retire a
stuck I/O. Memory testing covers the compiled fake worker and channel failure
receipt, not all GUI/runtime allocations. The current tests make no physical-media,
production-journal, legacy-platform, owner-acceptance or release qualification.
