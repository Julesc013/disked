# DE-W012/017 local implementing-agent review

Reviewed `de67d1f7bcf20127fad219ab7a195e07528cc18e` against `6793d4a878a3736f5f1dcc072ac5ae0894db10aa`, DE-022 and the cumulative DE-015/045
fake-profile contracts. This is implementing-agent review under the user's
cross-unit continuation grant, not independent safety review or owner acceptance.
The acceptance ledger remains unchanged. `criteria.json` maps the work-unit
criteria to current native groups and retained earlier evidence.

- Cursor scalar/relationship errors are checked before opening the directory.
  Worker, sequence and digest comparisons follow validation of the immutable
  claim and complete bounded hash chain. Observation never creates a claim,
  cancellation flag, worker or repaired history.
- Public events retain the exact record. The producer replays the guarded history
  before projection. The compatible reader bounds and validates each record/state,
  matches operation/worker and observer/request identities, and rejects gaps,
  conflicting duplicates and changed domains without advancing its cursor.
  Snapshot admission is explicit. Additive outer observations remain with the
  caller; unknown required features and critical record extensions fail closed.
- The reader is an observational integrity boundary, not authentication or writer
  authorization. The fake record's production ABI is still provisional. Its
  supported immutable attempt/worker domain must not be generalized into retries.
- The producer owns immutable request data and shared bounded queue only.
  Output runs on the frontend thread. Callback timeout closes the observer queue
  but does not retire a blocked callback. A failed output does not dispatch a
  following operation, and no late event leaks into the next exchange.
- Optional boolean form conversion is shared and reviewed before submission.
  Paging is inert; edits invalidate reviewed parameters. Actual Win32 controls,
  TUI and shell tests preserve cached input and late-outcome separation.
- Strict schemas, semantic dispatch, command catalogs, help/syntax vectors and
  input/context closures include the admitted watch contract. Planned commands
  remain unavailable. Native tests retain the no-provider essential boundary.
- The cumulative DE-W017 campaigns cover measured frontend/worker memory,
  process/retry/queue limits, store failures, output/request waits, retained
  observations and combined healthy/denied/malformed/slow/crashed producers.
  Full-suite reproduction guards the earlier outcomes on the current source.
  Unknown cancellation never supplies quiescence or automatic writer retry.

The tested local Windows fake-provider criteria are sufficient to continue to
DE-W018 under the grant. Keep DE-W012/017 at needs_review for owner acceptance.
DE-W011 launch profiles and DE-W019 human ergonomics remain partially qualified;
this review does not close those remaining claims. Production storage, recovery,
release and untested target claims remain at their own gates. DiskEd 0.1.0 is not
complete.
