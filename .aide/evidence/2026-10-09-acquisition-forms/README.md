# W033 native acquisition forms checkpoint

Clean source `7bb3eb4b58fe7976a36fd005a40d37e7ac5c20af`, work base `670e1075bbf1b8dee68c6c593cfecc427cc2bac2`. DiskEd 0.1.0-dev.20 adds
phase-specific GUI/TUI acquisition forms, a bounded structured definition editor,
and a shared Windows acquisition command adapter. Actual prepare/review/submit
journeys use the explicitly marked `disked_acquisition_ui_test.exe` composition.
The public `disked.exe` still reports `image.acquire` as planned/unavailable.

Fresh-checkout verification passed **46 native groups**, **175 specification
tests** (173 pass, two existing symlink skips), **921 structural checks**, and
**21 form checks**. Five actual native GUI/TUI journeys
include phase editing, review and separate submission; two completed copies were
independently checked against the source bytes and map hashes. Public observation
and the existing command, worker, file and core acquisition suites also passed.
Counts containing timed inspection/reconnect polls may vary.

Exact commands, logs, source/input identities and development artifact hashes are
in [commands.json](reproduction-7bb3eb4b/commands.json) and
[clean-results.json](reproduction-7bb3eb4b/clean-results.json).
Actual review screenshots and console observations are retained in that directory.
All 224 build-input hashes match the clean source. The 17
artifacts are in `.aide-local/artifacts/DE-W033-forms-7bb3eb4b/`.
PE/import tables for 11 executables describe their
static dependency closure; they are not a complete loaded-module inventory.

```powershell
cmake --preset windows-bootstrap
cmake --build --preset windows-bootstrap
ctest --preset windows-bootstrap --output-on-failure
python tests/frontend/test_acquisition_forms.py --exe build/windows-bootstrap/Release/disked_acquisition_ui_test.exe --product build/windows-bootstrap/Release/disked.exe --gui build/windows-bootstrap/Release/gui_model_probe.exe --tui build/windows-bootstrap/Release/tui_model_probe.exe --root .
```

The harness owns its generated ordinary files, inactive Windows GUI desktop and
hidden console. Preparation and review do not start copying or create outputs.
Execution submits the exact definition/digest with four separate effect grants.
Tests observe completion and owned process termination before removing fixtures.
They also verify console state restoration and the public unavailable response.

The tested host is non-elevated Windows 10 Enterprise 10.0.19045 under
BLACKGLASS-WIN1\Jules; MSVC 19.44.35228.0, toolset 14.44.35207,
SDK 10.0.19041.0, x64/C++14 and static release CRT. No physical devices,
customer data, installation, signing or remote writes were used.

This is implementing-agent component evidence, not owner acceptance or independent
storage safety qualification. Structured shell execution, interactive acquisition
watch rendering and public copy admission remain next. Other platforms, real
failing media, power-loss recovery and production writer decisions remain open.
W033 and the full DiskEd 0.1.0 programme remain incomplete. See
[REVIEW](REVIEW.md) and [FINDINGS](FINDINGS.md).
