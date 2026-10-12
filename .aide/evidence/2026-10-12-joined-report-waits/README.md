# Joined-report exit-wait diagnostic

One isolated diagnostic exercises the unchanged native joined-report test at
`f7b4376fe4ec4a88d07252f3feb25ee97e654a14`. All 281 checks pass. Six creation-verified report handles complete the
existing 3000-ms waits; the largest observed wait is 0.0418 seconds.
One additional report process is already absent. This does not reproduce or
explain the earlier parallel failure, and does not establish a reliability rate.

The [wrapper](reproduce.py) runs the exact Git-bound test, validates the clean build
identity and hashes the product, separate fault executable and parameter probe.
It calls the original wait once with its unchanged duration, then records returned
value/timing/creation-bound identity. Closed handles are removed from the tracing
map so reused handle values cannot inherit old observations. It changes no product
code, test criterion, retry policy or exit inference. Trace overhead itself changes
timing, so these observations cannot diagnose the original uninstrumented event.

[Current diagnostic](validation-summary.json), raw test results, PNGs, transcript
and wait trace are retained. Three exact PE copies remain local. The clean build,
compiler/import/source-input facts are independently retained by inventory-completion
at this same source revision; this diagnostic adds no full-build qualification.

The original generated TUI fixture remains present. Exact request/history/cancel
and output bytes are copied with their original path/digest provenance. Its three
records show prepared/executing/finished, original PID25268/creation134362312549654869,
and the output hash matches the retained parallel failure at 6e4c2059. They contain
no historical stack or actual-exit timing. Finished/quiescent remains effect state,
not proof of process exit. Original failure cause is still unestablished.

```text
python .aide/evidence/2026-10-12-joined-report-waits/reproduce.py --repository .aide-local/owned-layout-clean-2c731a1c/checkout --source-revision f7b4376fe4ec4a88d07252f3feb25ee97e654a14 --output .aide-local/joined-report-new-diagnostic
```

Use the recorded clean checkout and Windows compiler/Python environment. Next:
add bounded wait-result/timing diagnostics to the owning private tests, preserving
all existing deadlines and exact worker identity checks; use a finite instrumented
parallel campaign if needed. No production fix, owner acceptance, live/storage/
other-platform/release admission or complete 0.1.0 claim follows from this run.
