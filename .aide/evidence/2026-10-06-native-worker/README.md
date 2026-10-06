# DE-W016 native fake-worker evidence

Source: `3e790d51cb96b4b6e2c779d4a482a8172ab44dfe`. Clean clone/build/native launch evidence is retained in
`reproduction-3e790d51/clean-commands.json`, `reproduction-3e790d51/clean-results.json` and their linked logs. The artifact is
`.aide-local/artifacts/DE-W016-3e790d51/disked.exe` (690176 bytes),
`sha256:86a90469fbf520d683e44b2ce349bfde0e3b8aac0e22d8d08e6cdabcf3e474c7`. This is a local development artifact, not a release.

All 17 native CTest groups passed in the independent local clone. The operation
suite contains nine reducer tests and fifteen real-worker tests. Producer-schema
validation of actual responses/states/records passed. The retained specification
suite ran 169 tests: 167 passed, two Windows symlink-privilege checks skipped.
Structural validation reports 897 checks; passive AIDE validation covers 36
exported records at the existing pin, not live integration.

The worker tests exercise actual same-file launch and process creation identities,
killed client survival, exclusion of an extra inherited client handle, exact
image hashes, duplicate/conflicting admissions, early/late cancellation, verification
failure, worker death, corrupt/torn history, unreadable claims and bounded admission
timeout without automatic kill/retry. Retained worker observations include memory,
module closure and user-only protected record DACLs. Direct PE dependencies and
imports are recorded separately from dynamic system DLLs and host-injected modules.

Working-tree logs precede the source commit and identify dirty inputs. Final focused
checks followed a completion-race correction. Clean logs bind the built local
artifact to the exact source commit. Historical logs are not relabeled as fresh runs.

The host is Windows 10 x64 build 19045, non-elevated BLACKGLASS-WIN1\Jules. Windhawk
injection prevents a clean-loader claim. No physical device, elevation, customer
data, production journal/recovery, installation, release signing, publication,
live AIDE worker or other-platform qualification is supplied. File API hangs and
aggregate-operation ceilings remain later work. Same-user DACL/hash checks are
not authentication or a sandbox. Owner acceptance is still pending.

DE-W019: implement the bounded interactive shell using the shared parser/dispatcher and qualified terminal channels; then DE-W017 combines all frontend and worker resilience transcripts. DE-W017 depends on DE-W019.
