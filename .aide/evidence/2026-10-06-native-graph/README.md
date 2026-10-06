# Native fake graph and frontend service evidence

Clean source: `0d9e82588dfc574dbca168d843cd9195a97bbc30` on `goal/disked-0.1.0`.
Executable: `.aide-local/artifacts/DE-W013-0d9e8258/disked.exe` (456704 bytes).
SHA-256: `sha256:56d4f3a16eac8f42041009c5eec6db5dbf39bcfda272e3e52fffad408a2686fc`.

A fresh local clone built and passed all eleven native CTest groups, strict
producer-schema checks, structural validation and manifest verification.
`clean-commands.json` records exact commands, directories, outcomes and logs.
`clean-results.json` binds compiler/configuration, input bytes, host and artifact.
Direct imports remain KERNEL32.dll only; the host was Windows 10 x64 build 19045,
BLACKGLASS-WIN1\Jules, non-elevated. No real media or installation was used.

The nine direct-service tests exercise retained snapshots, independent revision
hashes, control/Unicode labels, stable selection, stale actions, cloned aliases,
resource cycles, partial observations, invalid refresh atomicity, byte/u64 bounds
and bounded identity history. Six frontend transport tests compare direct,
CLI and stdio success/refusal results; preserve raw machine values; verify safe
human display and provider-init exclusion for malformed input. Earlier parser,
JSON, reader, invocation, console-preservation and provider-trap groups remain
active. Specification tooling recorded 165 tests: 163 passed, two symlink cases
skipped. Structural checks: 888. Passive AIDE schema validation covered 36 records;
live AIDE integration remains unrun.

Reproduce from this source revision with the pinned toolchain described in
[the build instructions](../../../docs/native-bootstrap.md):

```powershell
cmake --preset windows-bootstrap
cmake --build --preset windows-bootstrap
ctest --preset windows-bootstrap
& .\build\windows-bootstrap\Release\disked.exe target list
& .\build\windows-bootstrap\Release\disked.exe topology show --json
& .\build\windows-bootstrap\Release\disked.exe target inspect fake:alpha@1 --json
```

The exact graph and capability launch outputs are retained in `clean-target-list.log`,
`clean-target-inspect.log` and `clean-capability.log`. Initial failures and their
repairs are explained in [the agent review](REVIEW.md). This is a private,
serialized fake service: no physical discovery, writer, GUI/TUI, concurrent
provider publication, durable operation or storage ABI qualification is implied.
The [handoff](../../handoffs/DE-W013-native-graph-2026-10-06.json) leaves owner
acceptance pending while the explicit programme grant permits local DE-W014 work.
The full DiskEd 0.1.0 goal remains active.
