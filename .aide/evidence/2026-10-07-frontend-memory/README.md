# DE-W017 frontend-memory checkpoint

Source `07fd5dc67670a75dc0eeb6a7031953289ee268c1`; work base `271706b0213e5b15b96e8794f82ce2ede2019a13`. The fake-only native development executable
is version 0.1.0-dev.12 at `.aide-local/artifacts/DE-W017-memory-07fd5dc6/disked.exe`, 839680 bytes,
`sha256:8bad4abd42cd10c855b5bc364b734d7e04acf9035facc652c0597f8f89ca4682`. Exact clean clone/build/test/launch commands, source closure,
compiler/SDK/runtime configuration, host and imports are in
`reproduction-07fd5dc6/`. This is a partial DE-W017 checkpoint, not a release
or owner acceptance.

Valid frontend invocations join one protected current-user/Windows-session job
with a 256 MiB per-process commitment limit before command dispatch. Existing
limits are inspected, never reset. Initialization has a 250 ms mutex wait; missing
APIs, contention, configuration mismatch and incompatible inherited job hierarchy
produce typed refusals. A stricter host limit remains effective. The common
ancestor lets all frontends' workers retain their stricter four-process,
128 MiB/process and 512 MiB aggregate quotas without kill-on-close or breakaway.

All 27 native CTest groups pass from a fresh local source clone. The working
specification suite ran 169 tests (167 passed, two existing Windows symlink skips).
All 900 structural checks, generated indices and manifest checks pass. Exact
producer-schema checks include 17 retained new response
observations. Passive AIDE schema validation covers 36 records at the unchanged
pin; live integration remains not run.

Nine new methods measure a full 256-request NDJSON session, 128 cached GUI
inspections on a private desktop, and 64 iterations each in hidden test-owned
TUI/shell consoles, including transcript eviction and caller-state restoration.
Two worker-budget methods additionally verify simultaneous frontend/worker job
membership, actual worker memory denial, full worker quota and worker survival
after every client exits. Raw samples and module observations remain in JSON.

The separate test executable attempts actual committed allocations until Windows
denies them, then releases them before emitting the refusal. On this clean run:

- Effective 256 MiB: peak process commitment 254603264 bytes; allocation error 1455.
- Effective 64 MiB: peak process commitment 52891648 bytes; allocation error 1455.

The product ignores that private allocation control. Other tests retain a
mismatched named test job, bound initialization contention, preserve inherited
UI restrictions and refuse an actually incompatible pair of independent host
hierarchies. The first fixture mistakes, stale-helper failure, suspended owned
worker and explicitly verified cleanup remain in `INITIAL-FINDINGS.md`.

Only non-elevated BLACKGLASS-WIN1\Jules on Windows 10 x64 build19045 is tested.
Memory admission dynamically uses system advapi32 for token/SID/DACL operations,
including essential commands; direct imports and observed/injected modules are
separate evidence. Loader/fixed parsing precedes assignment. Commitment is not
working set or total host memory, and this is not an aggregate frontend quota,
hostile-same-user security boundary or universal graceful allocation-failure
guarantee. No production storage, journal/recovery, older host, installation,
signing/publication or owner acceptance is qualified.

Continue DE-W017 with the combined healthy/denied/malformed/slow/crashed-provider campaign and explicit public event-stream scope. Preserve the verified memory/worker/transport/store boundaries; real full-filesystem, power-loss and other-host qualification remain unverified. Then continue the canonical dependency programme toward the full user-selected 0.1.0 scope.
