# Fake operation watch and local resilience review

Source `de67d1f7bcf20127fad219ab7a195e07528cc18e`, base `6793d4a878a3736f5f1dcc072ac5ae0894db10aa`. Version 0.1.0-dev.14 is retained at
`.aide-local/artifacts/DE-W017-watch-de67d1f7/disked.exe` (916992 bytes), `sha256:a31e83621e43ca11c1754779a04a195c03b28bafd97668e73df41663f43841b2`.
Exact clean clone/build/test/launch commands, input hashes, compiler, SDK, runtime,
host identity and PE dependency/import observations are in `reproduction-de67d1f7/`.
This checkpoint closes local DE-W012/017 fake-provider development criteria under
the continuation grant. Their canonical status is needs_review. Owner acceptance
and the full DiskEd 0.1.0 programme remain open.

`operation watch` observes an existing explicit fake store. Typed event records
bind operation, attempt, worker, sequence and digest. Reconnect validates the
retained cursor; an explicit snapshot establishes a new reader position. A fresh
observer identity correlates one request and never transfers writer ownership.
JSON/interactive views receive one bounded batch; direct NDJSON emits live events
and a final response. Protocol clients explicitly negotiate streaming so existing
one-response clients retain their behavior. A terminal read returns completed
even if the observed operation failed verification; its failed outcome remains
visible. Unknown worker/effect state stays unknown.

The 64-event/1 MiB queue does not wait for a consumer. CLI/stdio callback expiry
retains the occupied slot until actual completion; output failure seals the
stream and prevents dispatch of the next queued request. Disconnect does not
cancel, restart or repair the operation. Interactive callbacks return pending
immediately while cached navigation remains available. Win32 pages its bounded
typed fields; GUI and TUI preserve boolean values and omit empty optional fields.
Late results cannot replace newer cached views or inert shell input.

All 31 native CTest groups pass in the clean clone, including the existing worker,
store-failure, frontend memory, combined provider-failure and request/output
containment campaigns. Detailed watch evidence includes five native reader methods
and ten actual-process/frontend methods. Strict validation covers
17 retained responses, 45 events,
58 states and 0 graphs from the new
observations. One GUI presentation response was separately projected and validated;
the combined presentation object is not counted as a wire producer frame. The
specification suite ran 171 tests (169 passed, two existing
Windows symlink privilege skips); 904 structural checks and the manifest pass.
Passive AIDE validation covers 36 records at the unchanged pin; live AIDE was not run.
Initial defects, fixture corrections and failed observations are retained. The
post-run evidence helper initially misclassified a GUI presentation object as a
wire frame; `evidence-classifier-failure.json` retains that failure and correction.
No product code or wire schema changed for that correction.

Only this non-elevated Windows 10 x64 host was exercised. Event/store hashes are
unauthenticated integrity checks and provisional review encodings. A successful
write to an output handle proves neither consumer acknowledgement nor durable
flushing. Selected fault injection does not qualify arbitrary kernel hangs,
all allocation failures, real full filesystems, power-loss recovery or hostile
same-user isolation. No physical storage, privileged broker, production journal,
other host, installation, signing or publication was qualified.

Continue DE-W018 with an exact available-tool inventory and harmless C90 arithmetic/representation/text/loader probes. Record missing historical compilers or launch hosts as scoped blockers, without blocking independent modern development. Then follow canonical work dependencies toward the full user-selected 0.1.0 scope. Owner acceptance, storage privileges and release/other-platform qualification remain separate.
