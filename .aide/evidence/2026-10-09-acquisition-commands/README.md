# W033 private shared acquisition command checkpoint

Clean source: `9a9de03aab09aa87f28e0c445408c719acb281c1`. Work base: `3a2f003fc265b72bc56a76cab17e431735f7b08a`.

The private adapter transfers the canonical prepare/execute parameters through
the common CLI parser, stdio request dispatcher and frontend form decoder.
Preparation observes metadata/header/code; it does not copy source data or create
outputs. Execution requires the exact full definition digest and four separate
effect grants. Typed phase constraints prevent mixed fields and unknown effect
inputs. The definition, inner plan and resolved options are validated before
the execution port runs.

Fresh-checkout results: **44 native groups**, **284 recorded
command checks** including reconnect polls, **six independent byte/map copy
verifications**, **375 worker checks**, **126 file cases**,
**218 core cases** and **173 specification tests** (171 pass, two existing symlink
skips). All 913 structural checks, generated/manifest freshness, context binding
and 213 exact build-input hashes pass. Exact commands and raw logs are in
[the reproduction receipts](reproduction-9a9de03a/clean-results.json) and
[commands.json](reproduction-9a9de03a/commands.json).

Tests cover actual disposable-file transfer, strict structured input across the
three shared decoders, zero provider calls on invalid requests/grants, exact
definition/response binding, incomplete and uncertain outcomes, checkpoint
cancellation, new-attempt resume, late admission without restart and a separate
code/state-directory layout. The code and state parent handles are pinned
separately through launch. The layout test is positive evidence, not exhaustive
concurrent directory-replacement or backing-alias qualification.

To reproduce this source using the recorded MSVC/SDK configuration:

```powershell
cmake --preset windows-bootstrap
cmake --build --preset windows-bootstrap
ctest --preset windows-bootstrap --output-on-failure
python tests/images/test_acquisition_commands.py --probe build/windows-bootstrap/Release/acquisition_command_probe.exe --root .
```

The tested host is non-elevated Windows 10 Enterprise 10.0.19045 under
BLACKGLASS-WIN1\Jules. The recorded toolchain uses MSVC 19.44.35228.0,
toolset 14.44.35207, SDK 10.0.19041.0, x64/C++14 and static release CRT.
Twelve development/test binaries/libraries are retained locally under
`.aide-local/artifacts/DE-W033-command-9a9de03a/`, with exact hashes in the
receipt. Seven executable PE/import observations are static tables and
source-declared system-library loading, not a complete observed module inventory.

`disked.exe` still excludes the acquisition handler/worker. The canonical syntax
is provisional and the public command remains planned/unavailable. Real GUI/TUI/
shell review/submission, operation response/watch integration and product
admission remain unfinished. No physical devices, elevation, customer data,
installation, signing or remote writes were used. This is neither power-loss,
real failing-media, other-platform nor independent safety qualification. Owner
acceptance remains pending; W033 and DiskEd 0.1.0 remain incomplete.

[REVIEW](REVIEW.md) records implementing-agent review; [FINDINGS](FINDINGS.md)
distinguishes superseded working observations from the clean source evidence.
