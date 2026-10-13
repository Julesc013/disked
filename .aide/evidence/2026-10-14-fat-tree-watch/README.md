# DE-W057 bounded wait/watch development

At baseacc23df3 with retained changes, ten watch methods pass. Three selected
native groups pass: watch, reconnect and controller. Tooling runs238 tests:
236 pass/two skip. Source map262 files; two selected headers build. Generated
checks cover230 targets,542 compiled source entries and5685 quoted include
edges without violations. Observation counts include repeated polling; they
are not that many independent test scenarios.

Cursor0 emits admission as event1; retained indices remain zero-based. Exact
canonical raw record bytes plus LF retain their old SHA256 meaning. Events bind
header/review/worker/operation/request/observer identities and one explicit
sequence domain. Replay/resume/snapshot and changed/shrunk/conflicting prefixes
have independent JSON/hash oracles. Event/aggregate limits and stopped/throwing
sinks preserve the last admitted cursor; closing observers has no writer effect.

Native following permits0..2000ms,25ms poll intervals and at most81 observations.
That bounds following between native calls, not an unavailable/blocked file API;
public request containment still must be connected. Validated retained exit
declarations stay distinct from present-day process facts. Unavailable facts stay
unknown; known identity conflicts cannot authorize cancellation. The controller
may finish flushing a just-exited worker. Matching held process births/positive
exit waits are rechecked when image queries disappear during teardown.

Actual separate callers follow an existing detached owner, reach a live boundary,
cancel cooperatively and resume exact records through retained partial exit.
A deterministic streamed wait observes its first snapshot before cancellation,
then follows publication/exit records. Completed reads preserve source/ledger/
control bytes. Torn history is retained without repair. No new writer or source/
destination access occurs in an observer.

Failed logs/cases are retained: initial process-query/exit-flush races, a test
assuming a500ms publication hold would always still be live after process
startup, and a later teardown query race. The test now waits for an actual first
event from a live fixture before cancellation. Native facts and retained history
are reconciled separately. Final tests retain their requirements; failure runs
are not relabelled as passes. No test owner was replaced while live.

The final controller regression initially crossed its15s test-helper cutoff:
retained timestamps show10.291462s from controller birth to admission and
4.7945905s from admission to recorded exit, total15.0860525s. The existing
controller continued to completion. The helper now allows90s, within the finite
CTest harness; runtime budgets and exact output/source assertions are unchanged.

These are dirty-development private prerequisites. Public descriptor/ports,
compatible protocol readers, actual CLI/protocol/GUI/TUI/shell and full exact-
source qualification remain. Other hosts/physical storage/production recovery,
owner acceptance, live Setup/AIDE, release and complete0.1.0 are unqualified.

The implementation checked Microsoft’s primary API contracts for
[QueryFullProcessImageNameW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew)
and [GetExitCodeProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getexitcodeprocess).
Observed teardown failures are fixture evidence, not guarantees made by those APIs.
