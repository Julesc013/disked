# DE-W017 interactive and worker containment checkpoint

Source `ee7cfb6984c1049cad3b3bdc53fa615687c4f244`; work base `4b1be0facb5648da49557337609c503573f0b72c`. DE-W017 remains active and partial.
The local development executable is `.aide-local/artifacts/DE-W017-slice-ee7cfb69/disked.exe`, 815104 bytes,
`sha256:a791a2ab4695b18e8457b1cf1529638db7c3f5a4e748bfeed09a85ddef2f2f8d`. Exact clean clone/build/test/launch commands, source inputs,
host and dependency/import observations are retained in `reproduction-ee7cfb69/`.
The executable is fake-only, version 0.1.0-dev.9; no release or owner acceptance.

The clean checkout passes 23 native CTest groups and 169 specification tests
(167 passed, two existing Windows symlink-privilege skips), 900 structural checks,
generated freshness and manifest verification. Actual response, graph, terminal
and fake-operation producer-schema checks pass. Passive AIDE schema validation
covers 36 records at the unchanged pin; live AIDE integration remains unrun.

The baseline GUI froze during delayed admission. One owned callback/completion
slot now lets the GUI, TUI and shell process cached navigation during that wait.
A second concurrent fake-operation request is refused without creating its store.
View epochs and shell input ownership retain late results separately. Malformed,
oversized and throwing callbacks produce unknown outcomes; an allocation-denial
probe verifies that reporting that outcome requires no allocation on the failing
thread. A two-response display regression preserves both complete payloads.

Clean synthetic GUI message samples: 0.151, 3.009, 0.062, 0.056, 0.020 ms.
Cached shell/TUI key observations: shell 10.962 ms, tui 4.280 ms.
These samples meet the selected 250 ms fixture criterion on this host. They are
not human-input, other-host, arbitrary-workload or kernel-stall qualification.

Workers now use an explicit state-store CWD, no console, and atomic creation with
private and aggregate Windows jobs. Actual membership queries show four workers;
a fifth cannot launch. Existing unresolved claims are not retried when capacity
frees. All four slots remain occupied after clients exit until the original
workers finish. Limits are 128 MiB committed memory per process and 512 MiB per
aggregate job, scoped to cooperating workers in the current user/Windows session.
The memory-denial fixture observed 120492032 peak committed bytes
and Win32 error 1455; inspect retained an unresolved operation.
These are job accounting limits, not total frontend/host memory or an adversarial
sandbox. Initial failures and their repairs remain in `INITIAL-FINDINGS.md` and
working logs; clean evidence identifies the final committed bytes.

The tested host is non-elevated BLACKGLASS-WIN1\Jules, Windows 10 x64 build19045.
PE/import observations are distinct from host-injected Windhawk modules. Real
storage, privileged brokers, production journals/recovery, other targets, human
usability, clean-VM, accessibility, Setup/signing/publication and owner acceptance
remain unverified or separately gated.

Continue DE-W017: bound synchronous CLI/stdio file calls and slow-consumer behaviour, measure whole-frontend resource limits, and execute full-destination plus combined provider faults. Preserve immutable claims, unknown effects and worker/capture epochs; do not repeat admitted work.
