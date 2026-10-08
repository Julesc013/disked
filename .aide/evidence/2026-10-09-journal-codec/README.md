# DE-W040 proposed native journal framing

Clean source `ce9ae70f28e6e8c7d6408563fd3508d51d263164`, work base `2e63bbabf75129acb5c6b67e0fa3c54ce2f4fca8`. The private C++14 codec implements
the exact DE-043/profile byte proposal: a 192-byte identity-bound header, bounded
112-byte record prefixes and SHA-256 payload/chain/context checks. It scans one
record at a time through a bounded source port. It is not linked to disked.exe.

Fresh-checkout verification passed **48 native groups**, **175 specification
tests** (173 pass, two existing symlink skips), **923 structural checks**, and
**784 independent codec vectors**. These cover exact little-endian framing,
every cut/one-byte corruption of a small fixture, target/plan/provider swaps,
flags/critical kinds, compatible unknown observations, u64 boundaries, 64-KiB
payloads, source/visitor failures and the 4096-record streaming ceiling.

Exact commands, logs, source/input identities and artifact hashes are in
[commands.json](reproduction-ce9ae70f/commands.json) and
[clean-results.json](reproduction-ce9ae70f/clean-results.json).
All 230 build-input hashes match the clean source. Five development artifacts
are retained in `.aide-local/artifacts/DE-W040-codec-ce9ae70f/`. Generated
product linker dependencies exclude the prototype; PE/import tables are retained
for the product and codec probe. They describe static imports, not complete
loaded-module inventories.

The initial clean campaign at `5293cf4e` failed the shared-image group, with its
callback slot still occupied after forty probes. An unchanged timed probe and
three repeated groups passed; the original cause remains unestablished. The
private stdio fixture now holds/releases a test-owned local event gate and
observes slot availability. The ordinary product ignores that hook. This clean
campaign and a separate schema-validated image journey passed; timings are in
[gated-image-cases.json](reproduction-ce9ae70f/gated-image-cases.json). See
[initial failure](INITIAL-CLEAN-FAILURE.md).

At `ce9ae70f`, the initial native campaign also missed the acquisition
fixture's unchanged 30-second deadline. Retained worker history showed completed
copy at 30.837 seconds. Subsequent read-only reconciliation verified all 16 MiB,
the sealed map chain and an absent recorded worker; the fixture was preserved.
The unchanged clean revalidation campaign passed. The initial failure remains
in `commands.json` and [reconciliation](reproduction-ce9ae70f/resume-deadline-reconciliation/result.json); later
completion does not retroactively satisfy its deadline. I/O latency variability
and the original image-callback failure's causes remain unestablished.

```powershell
cmake --preset windows-bootstrap
cmake --build --preset windows-bootstrap
ctest --preset windows-bootstrap --output-on-failure
python tests/journal/test_codec.py --probe build/windows-bootstrap/Release/journal_codec_probe.exe --root .
```

The probe uses only memory byte sources and stdout. No journal files, target
effects, tail repairs or recovery attempts are issued. A verified prefix or an
observed terminal-kind record does not authorize effects or establish a completed
logical operation. Expected bindings require independent authority/freshness.

Tested on non-elevated Windows 10 Enterprise 10.0.19045 under BLACKGLASS-WIN1\Jules,
MSVC 19.44.35228.0, toolset 14.44.35207, SDK 10.0.19041.0, x64/C++14 and /MT.
Other platforms, physical/sector/power-loss persistence and owner acceptance are
unverified. This is implementing-agent component evidence. DE-W040 and DiskEd
0.1.0 remain incomplete; DE-DEC-004 remains proposed. Payload definitions,
separate receipts, composable recovery traits and guarded flush/effect models
follow before production writer admission. See [REVIEW](REVIEW.md).
