# Initial frontend-memory findings

These exploratory observations precede the source checkpoint and clean
reproduction. They are retained failures/iterations, not final qualification.

- `initial-focused.json`: four of six methods passed. The NDJSON fixture used
  nonexistent `graph.list`; the canonical command is `target.list`. A second
  fixture expected a host job's `JOB_OBJECT_UILIMIT_HANDLES` to prohibit nesting.
  On this Windows 10 host the nested assignment succeeded and the restriction
  remained set. The revised fixture records that observation. A separate test
  establishes an actually incompatible hierarchy with live processes under two
  independent host jobs; admission must refuse it. No product limit was relaxed.
- `corrected-focused.json`: all seven methods passed after those fixture
  corrections. Actual commitment denial occurred both under the 256 MiB product
  cap and a stricter 64 MiB inherited host cap.
- `initial-workloads.json`: nine methods passed, adding a full 256-request
  NDJSON session, 128 private-desktop GUI inspections and 64 iterations each in
  hidden test-owned TUI/shell consoles, including transcript eviction/restoration.
- `stale-worker-helper.json`: the worker test was mistakenly run before rebuilding
  every helper. Its delayed executable reported dirty source `e4acbefd...` and
  lacked the new frontend memory ancestor; the membership assertion failed.
  Failure cleanup killed the client while process creation was still in progress.
  The fixture's owned worker remained with one suspended initial thread, locking
  its disposable files and executable; a subsequent build failed with LNK1104.
  The cause of that suspended thread was not established. This host has previously
  observed process injection; neither injection nor a product defect is inferred
  as the cause. Atomic job assignment is not a universal guarantee against host
  process-creation interception or arbitrary kernel failures.
- `stale-helper-suspended.json` records the exact PID, creation time, command,
  binary hash and suspended-thread observation. Cleanup verified that identity
  and terminated only this fixture-owned fake worker, then observed its exit.
  It did not resume the worker, authorize replay or infer safe storage recovery.
  Worker-test cleanup now lets finite client admission return before its fallback
  termination, so an early assertion does not immediately interrupt creation.
- `rebuilt-workers.json`: both worker methods pass after the full helper rebuild.
  Four simultaneous frontends and their independent workers belong to the common
  memory job; worker-specific 128 MiB/512 MiB/four-process limits remain in force,
  including after every frontend exits.

A local documentation helper also encountered a Windows default-codepage decode
error. The partial changes were inspected, the remaining reads used UTF-8, and
three already-corrupt work-range labels were replaced with plain text. This was
an editing-tool error, separate from native runtime behavior.
