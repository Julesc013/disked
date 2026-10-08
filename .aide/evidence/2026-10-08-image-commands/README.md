# W024 shared raw-file command checkpoint

Source `ca9486334e03cb893263a051b2149f765cb1c81c`, base `53227e9d881ecbd648c1f1ab81990bfcc6946ceb`. The Windows 0.1.0-dev.18 image/fake prototype
implements `disked image inspect PATH` and `disked table verify PATH`, including
the optional `--logical-block-bytes 512|4096` parameter (default 512). Only an
explicit ordinary local raw file enters this profile. The existing fake graph
and synthetic operations remain fake. No physical device, mount, elevation,
source modification, installation, signing or remote write is admitted.

Both commands use the existing private bounded map readers and file capture
provider. They return independent MBR/EBR/GPT findings, geometry, source identity,
capture epoch and region coverage. The capture receipt binds the internally
constructed full region manifest; the initial command exports at most eight
details with omitted counts. Full capture retrieval/export remains future work.
Complete bounded observation is exit 0 even if a map is corrupt/disagreeing;
that is not a healthy-image certificate. Incomplete reads return a retained
partial result and exit 4. Changes, source refusal and API/resource failures
have distinct typed diagnostics. Sequential live-uncoordinated reads and equal
rereads are not an atomic snapshot or whole-image verification.

Actual native CLI/stdio, GUI on a test-owned inactive desktop, and isolated TUI/
shell journeys compare stable geometry, findings and diagnostics. Review is inert
until separate submission. Original values are retained while human displays
escape control/non-ASCII data. The one-call asynchronous channel owns inputs
without borrowing a frontend/session. A four-second CLI/stdio expiry leaves the
slot occupied until actual completion; no unsolicited late wire response is
emitted. Real delayed GUI tests preserve responsiveness and a newer view while
retaining the earlier image result separately. Delay/read/change hooks are
separately compiled test controls, absent from the ordinary executable/library.
They do not qualify actual changing-media/hot-removal or power-loss behavior.

Clean reproduction passed all 40 native CTest groups, the 125 command/frontend
cases, 104 private file-capture cases and 75 private map cases within their native
groups, and 171 specification tests (169 pass, two existing Windows symlink
privilege skips). Structural, freshness, strict producer schemas, manifest/context
and passive AIDE validation pass. Live AIDE was not run. Failed development test
expectations and the console observer correction are retained in FINDINGS/logs.

The pinned MSVC 19.44.35228, toolset 14.44.35207, SDK 10.0.19041.0, Release C++14
static /MT lane retains 190 hashed native inputs and exact build configuration.
Clean `disked.exe` imports/dependencies and hashes are tied to its actual source
identity; mandatory loader dependency is KERNEL32.dll. The tested host and
non-elevated identity are in execution-environment.json. Other hosts/platforms,
physical storage, containers, general path/alias profiles and independent safety
qualification remain unverified. Artifacts live under
`.aide-local/artifacts/DE-W024-commands-ca948633/`; identities and exact commands
are in `reproduction-ca948633/clean-results.json` and commands.json.

Reproduce with `cmake --preset windows-bootstrap`,
`cmake --build --preset windows-bootstrap`, and
`ctest --preset windows-bootstrap --output-on-failure` using the pinned installed
toolchain. The repository build/tests do not depend on a model service.

This is the local W024 raw-file review boundary, not owner acceptance or complete
DiskEd 0.1.0. The owner-pasted service notice has no available trigger/request ID;
fresh runner status was active after the previously retained blocked observation.
No service transition is attributed to a particular request or local test failure.

Continue the full 0.1.0 programme with DE-W033 ordinary generated-file acquisition: read the source-bound work context, define typed source/destination/host bindings and no-clobber/resume behavior before implementing the bounded pipeline. Local tests and agent review permit continuation under the existing owner grant; owner acceptance, physical-device/elevation, writer-journal, historical-platform and publication gates remain separate. DE-W030 physical inventory cannot be qualified under the ordinary-file grant.
