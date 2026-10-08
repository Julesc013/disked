# W033 worker implementation findings

The first implementation held the parent's read-only resume handles until after
child admission. Independent cancellation/resume testing observed a refused
exclusive reopen with Windows error 32. Preparation now releases those handles
before launch. The child separately revalidates the exact reviewed definition
under its own pinned handles before any data effect; it cannot mint a new plan.

Review found that a provider-supplied capture_epoch would be overwritten by the
core. A new independent case rejected this behavior. The corrected port accepts
exactly clock, started and attempt_id; only the core adds the immutable plan epoch.
The retained superseded native run failed that new case and two stale build-
identity checks after inputs changed. Do not qualify the final source from it.
The corrected core run passes 218 cases. Clean reproduction remains decisive.

The test harness originally required image-path queries during process teardown,
when Windows may have withdrawn query access before signaling exit. It now checks
PID creation time, requires image-path matching for live/termination observations,
and waits on the retained handle after a terminal record. One short fixture
observation deadline expired under host load; later inspection saw a complete
finished record and exited worker. The observation bound is now 30 seconds.
Failed fixtures are retained without cleanup or replacement-worker launch.
These are harness/environment findings, not a guarantee of an execution deadline.

The shared Windows file/job/capability helpers preserve the fake worker's existing
behavior and fault macros. The private real acquisition worker joins the same
four-process aggregate budget, carries only four explicit inherited capabilities,
and uses no standard handles. Failed/short/flush operation-record writes retain
unknown admissions without data outputs or automatic retry. Checkpoint-observer
failure retains the actual verified prefix and a failed operation outcome.

Tests use generated ordinary files and exact explicit definition/effect grants.
Owned-child termination is process interruption; per-file flush observations are
API-level evidence. None qualifies physical media, power loss, real failing media,
public command/frontends, other platforms, owner acceptance or a finished 0.1.0.
