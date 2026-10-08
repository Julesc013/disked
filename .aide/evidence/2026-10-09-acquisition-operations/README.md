# W033 public acquisition observation checkpoint

Clean source `eae515b0d0c4a6fe60eba4e6fe2f4158e08c772b`, work base `3868d05bf488316f999a6e261f27042b33ede898`. DiskEd 0.1.0-dev.19 adds explicit
acquisition inspect/cancel and bounded CLI/stdio watch to the native product.
Copy admission remains private; `image.acquire` remains planned/unavailable.

Fresh-checkout verification passed **45 native groups**, **175 specification
tests** (173 pass, two existing symlink skips), **921 structural checks**,
**197 public observation checks**, and producer
conformance for **68 emitted events**. Private command,
worker, file and core suites also passed, including six command-copy byte/map
verifications. Counts containing timed reconnect polls may vary.

Exact commands, logs, input identities and artifact hashes are in
[commands.json](reproduction-eae515b0/commands.json) and
[clean-results.json](reproduction-eae515b0/clean-results.json).
The executable and thirteen related development/test artifacts are retained in
`.aide-local/artifacts/DE-W033-observation-eae515b0/`. PE/import tables for
eight executables are static dependency observations, not a complete loaded-module
inventory. All 222 build-input hashes match the clean reviewed source.

```powershell
cmake --preset windows-bootstrap
cmake --build --preset windows-bootstrap
ctest --preset windows-bootstrap --output-on-failure
python tests/images/test_acquisition_operations.py --probe build/windows-bootstrap/Release/acquisition_command_probe.exe --disked build/windows-bootstrap/Release/disked.exe --reader build/windows-bootstrap/Release/watch_probe.exe --root .
```

The test harness creates ordinary local files and starts the private acquisition
probe with explicit effect grants. Public product observers inspect those actual
workers and records; they never start or restart a copy. Tests independently
check destination bytes, map hashes, capture/attempt identity, checkpoint coverage,
event chains, cursor replay and persisted checkpoint cancellation. Producer
schema validation is separate from the native reader's exact-definition check.

The host is non-elevated Windows 10 Enterprise 10.0.19045 under
BLACKGLASS-WIN1\Jules; pinned MSVC 19.44.35228.0, toolset 14.44.35207,
SDK 10.0.19041.0, x64/C++14 and static release CRT. No physical devices,
customer data, installation, signing or remote writes were used.

This is implementing-agent component evidence, not owner acceptance or independent
storage safety qualification. Visible acquisition copy review/submission,
interactive result/rendering limits, failing physical media, power-loss recovery,
other platforms and production writer decisions remain open. W033 and the full
DiskEd 0.1.0 programme remain incomplete. [REVIEW](REVIEW.md) records the local
review and [FINDINGS](FINDINGS.md) explains the corrected test assertion.
