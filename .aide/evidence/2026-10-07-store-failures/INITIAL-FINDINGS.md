# Store-failure findings

The injected baseline used production control flow at base e4acbefd76ecff4daf3c3ed5f2fb7f419fc9ef15,
plus the retained test-only adapter patch. The baseline build identity and exact
fault executable hash are retained. The original product control check used the
prior clean a30313c0 executable. This is not a test of a physically full volume.

All three claim write cases returned refusal/exit 2 with no operation ID despite
leaving an exclusively created request.json. A subsequent same-store start was
unknown, with no replay. Those inconsistent receipts are a production defect.

The first cancellation fixture mistakenly used `operation cancel request` instead
of canonical `operation cancel`. Its three parser refusals are not evidence of a
storage defect. After correcting only the fixture, all three write failure cases
returned refusal/exit 2, dropping the operation ID and prior state. In the flush
case the actual worker had observed the written flag and recorded cancelled.
The corrected baseline transcript establishes the production receipt defect.

All fifteen record-failure combinations already stopped transitions and prevented
automatic replay. A complete terminal record after a failed final flush remains
readable synthetic truth; it does not establish successful persistence. The fake
contract now states that limitation explicitly. Partial tails and nonterminal
records with exited workers remain unknown.

Repair: allocate claim identity/header bytes before exclusive creation, move its
write/flush inside the unknown-admission guard, and guard cancellation write/flush
with an unknown receipt retaining the operation ID and preceding observation.
Capture GetLastError before exception construction and use ERROR_WRITE_FAULT for
a successful API call reporting an incomplete write, rather than a stale error.

The repaired initial run passed all six test methods and 26 retained scenarios.
Clean source-bound checks follow separately. No host volume was filled, no physical
device accessed, no cancellation acknowledgement fabricated, and no failed claim
deleted or retried.

A subsequent test-owned shared 256MiB process-memory job admitted two frontends
and both of their workers under the existing shared worker/private jobs. The
workers remained running after client exit and then completed once. The probe
and exact observed memory/job evidence are retained separately. This establishes
one viable local hierarchy for further work, not product enforcement, workload
qualification, inherited-host compatibility or a selected frontend budget.
