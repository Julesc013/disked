# DE-W017 observation-capture checkpoint

Source `eb042ca0172920182b3427378adab13c18802e40`; work base `d468dad06425371a884a862ef8fc5bf341799dc1`. The fake-only native development executable
is version 0.1.0-dev.13 at `.aide-local/artifacts/DE-W017-capture-eb042ca0/disked.exe`, 868352 bytes,
`sha256:02c879dc4384be683f8430b13adad0697cc61004248f3ed517986f0739a7ae1b`. Exact clean clone/build/test/launch commands, source closure,
compiler/SDK/runtime configuration, host and imports are in
`reproduction-eb042ca0/`. This is a partial DE-W017 checkpoint, not a release
or owner acceptance.

The private capture coordinator validates disjoint source fragments and their
aggregate before publication. Failed sources retain cached stale data; unrelated
healthy fragments stay available. Timeout does not retire an attempt. Exact
capture/worker epochs reject superseded or duplicate completion, while a valid
late result in the current capture can publish. The eight-notice retention limit
requires a complete snapshot after a gap or capture reset. Identity retention is
bounded to 1,024 bindings even after valid empty results remove observations.

Publication failures leave old snapshots and pending updates available. Native
allocation injection exercises both the coordinator and frontend session. The
session polls once at admission and does not rebase staged actions. The ordinary
product still exposes the same deterministic compiled fake graph; it does not
launch external producers or expose private campaign diagnostics.

A separate native test composition starts synthetic denial, malformed JSON,
1,800 ms delayed success and native exception 0xE000D17D producers. Parent
observations retain exact process IDs/creation identities, actual exit codes and
job membership/limits. The 400 ms observation timeout leaves the delayed producer
outstanding; its eventual valid result appears without replacement. Each producer
has a one-process/64 MiB job below a four-process/256 MiB per-campaign job. These
are test observer limits, distinct from the product's fake-operation worker quota.

The combined tests use the actual stdio frontend, Win32 controls on a private
desktop and hidden test-owned TUI/shell consoles. They inspect healthy data during
failures, preserve staged revision and inert shell input, reject stale actions,
measure the 250 ms cached-input target, observe late success and restore console
state. Synthetic denial is not OS permission qualification; malformed pipe input
and native exception are actual process failures. Initial fixture mistakes and
review corrections are retained in `INITIAL-FINDINGS.md`.

All 29 native CTest groups pass from a fresh local source clone. Nine reducer and
four native campaign methods also retain detailed observations separately. The
working specification suite ran 169 tests (167 passed, two existing Windows
symlink privilege skips); 900 structural checks and the generated manifest pass.
Strict producer validation covers 15 retained new
responses and 13 graphs. Passive AIDE schema validation
covers 36 records at the unchanged pin; live integration remains not run.

Only non-elevated BLACKGLASS-WIN1\Jules on Windows 10 x64 build19045 is tested.
Private source notices are not public event streaming. Per-campaign observer
budgets are not a host-wide observer quota, production provider admission or a
hostile-same-user security boundary. Selected allocation injection is not a
universal graceful memory-failure guarantee. No real storage, production journal,
power-loss recovery, older host, installation, signing/publication or owner
acceptance is qualified.

Continue DE-W012/017 with the bounded public operation.watch execution contract, typed event payloads, exact operation/attempt/worker sequence domains, negotiation, gap/resnapshot and reconnect tests. Preserve the verified capture, memory, worker, transport and store boundaries. Then continue the canonical dependency programme toward the full user-selected 0.1.0 scope; owner/storage/release and unavailable-platform gates remain separate.
