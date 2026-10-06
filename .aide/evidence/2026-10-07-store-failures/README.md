# DE-W017 state-store failure checkpoint

Source `b8de3be9094718c0170f5cd2980abd0b6d3448d5`; work base `e4acbefd76ecff4daf3c3ed5f2fb7f419fc9ef15`. The fake-only development executable is
version 0.1.0-dev.11 at `.aide-local/artifacts/DE-W017-store-b8de3be9/disked.exe`, 829440 bytes,
`sha256:ba0a6399596710252061653fc38596250b32b9b43f4d75a8b97e608fbd74ce3c`. Exact clean clone/build/test/launch commands, toolchain, source
inputs, host and imports are in `reproduction-b8de3be9/`.
This remains a partial DE-W017 checkpoint, not a release or owner acceptance.

The clean checkout passes all 26 native CTest groups. The working specification
suite ran 169 tests (167 passed, two existing Windows symlink-privilege skips).
All 900 structural checks, generated projections and manifest checks pass.
Actual protocol/fake-operation producer schemas pass, including
68 retained new response observations. Passive AIDE
schema validation covers 36 records at its unchanged pin; no live integration run.

Six new test methods retain 26 scenarios. Full, partial and failed-flush writes
are injected at claim creation, initial cancellation flag, cancellation request
and five worker-record transitions. The product executable ignores the test-only
control. The tests use ordinary disposable files; they do not fill a host volume
or qualify a real full filesystem or driver failure.

The baseline dropped the known operation ID and returned refusal after leaving
a claim file. It also refused a cancellation request after a failed flush even
though the worker had observed the flag and cancelled. The repaired paths retain
unknown outcomes, original error and identity, preserve residual bytes and never
replay a failed claim. Cached healthy and denied observations remain available in
the same NDJSON stream. Earlier fixture/parser mistakes and corrected baseline
observations remain in `INITIAL-FINDINGS.md` and the baseline JSON files.

Worker-record errors already stopped subsequent transitions. The tests preserve
that behavior through preparation, dispatch, observation and final verification.
Partial tails and nonterminal records with exited workers remain unknown. A
complete terminal record after a failed final flush is still readable synthetic
truth; it is not evidence that the flush succeeded or that data survives power
loss. The exact worker exit and residual bytes are retained separately.

An additional test-owned shared 256MiB process-memory job accommodated two
frontends and their workers in the existing worker-job hierarchy. Both workers
remained alive after client exit and then completed. `prospective-memory-hierarchy.json` and its probe source
retain this experiment. It is not yet product memory enforcement, a selected
workload budget or qualification of inherited host jobs and interactive workloads.

Only non-elevated BLACKGLASS-WIN1\Jules on Windows 10 x64 build19045 is exercised.
Direct/dynamic product dependencies and host-injected modules are separate. Real
storage, privileged brokers, production journals/recovery, other platforms,
installation, signing/publication and owner acceptance remain separately gated.

Continue DE-W017: implement and measure frontend memory admission using the prospective common-job evidence while preserving inherited host restrictions, shared worker quotas and worker lifetime; then complete combined malformed/crashed/slow-provider and public event-stream scope checks. Real full-filesystem and power-loss persistence remain unqualified.
