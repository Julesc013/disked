# Joined-report preparation phase investigation

DE-W034 owns this correction, at base
`89cd7b88691a661cc6d2da53e2af9b19a1f0d234`. The existing user grant permits
local implementation/testing and development pushes; owner/storage/release gates
remain separate. DE-W075's native regression failure remains retained.

Expected checks, established before the build:

- The existing separate fault probe can collect exactly ten observations around
  directory validation, user identity, executable inspection, export review and
  definition validation. Collect monotonic time, process CPU and read/other I/O
  counters; no timing data is emitted by normal product requests.
- The normal probe rejects the trace mode. The standard fault preparation and
  traced preparation yield the same definition/digest after removing trace data.
- Hold the selected inputs and callback before instrumentation. The generated
  source request/history/collection remain byte-identical; destination and state
  outputs remain absent during preparation.
- A trusted test callback attempts to replace every caller input at the first
  phase. The exact original definition remains selected; no changed path opens.
- Streaming fault modes flush each observation before continuing. A controlled
  pause at `image_begin` leaves that exact prefix when the owned test process is
  stopped at its diagnostic ceiling; actual exit and absent outputs are checked.
- Retain actual commands, compiler/configuration, artifact identities, results
  and unavailable checks. Existing report worker, joined export and frontend
  behaviour remain subject to their original bounds and tests.

The trace is diagnostic, not a fix or a native qualification. It does not alter
the four-second request boundary, turn an old failure into a pass, add a public
command, or qualify storage/media/recovery/release behaviour. Normal orchestration
is retained; all observations use the existing backend validation functions.
