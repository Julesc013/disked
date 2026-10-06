# Native Win32 frontend evidence

Clean source: `b4774f03d739c5a932a9f4343c37d26dcc7bdda7` on `goal/disked-0.1.0`.
Executable: `.aide-local/artifacts/DE-W015-b4774f03/disked.exe` (577536 bytes).
SHA-256: `sha256:089040f913930fc193a7448c3acc91394a2df2112c98317c6190ea142b6e32f0`.

A fresh local clone built and passed all 15 native CTest groups, strict producer
schema checks, structural validation and manifest verification. Exact commands,
results and logs are in `clean-commands.json`; `clean-results.json` binds the source
closure, compiler/configuration, Windows 10 x64 host and executable. Direct PE
imports remain KERNEL32.dll only. Explicit GUI initialization dynamically uses
System32 user32/gdi32. Runtime module observations include host-injected Windhawk
modules, also seen in the headless test, and do not establish clean-VM behavior.
The host was BLACKGLASS-WIN1\Jules, non-elevated, Windows build 19045.

The six GUI-model tests compare shared-service outcomes with actual CLI/stdio and
TUI reduction, including stale review, removed selection and refused commands.
Seven actual-window tests cover native roles, keyboard traversal, explicit review
and submission, inert Enter, bounded rejected input, minimum layout, host settings
and a named unavailable-dependency/provider trap. Existing CLI, TUI, graph and
protocol checks remain active. Working specification validation recorded 163
passes and two symlink skips, 888 structural checks and 36 passive AIDE records.
Live AIDE and native storage qualification remain unrun.

Actual captures from the clean executable:

- [Inventory](clean/inventory.png)
- [Inspector](clean/inspector.png)
- [Exact request review](clean/request-review.png)
- [Request result](clean/request-result.png)
- [Minimum window](clean/minimum-window.png)

`clean/window-observations.json` retains native control/module observations and
keyboard traversal. Tests place their own windows on an inactive private desktop,
never switch the user's desktop, and restore their thread association on cleanup.
These captures show the actual native program, not a mockup.

Reproduce with the pinned toolchain in [the build instructions](../../../docs/native-bootstrap.md):

```powershell
cmake --preset windows-bootstrap
cmake --build --preset windows-bootstrap
ctest --preset windows-bootstrap
& .\build\windows-bootstrap\Release\disked.exe gui
& .\build\windows-bootstrap\Release\disked.exe --gui target inspect fake:alpha@1
```

The last two commands intentionally open the interactive product window. No
physical storage, installation, elevation or persistent preference file is used.
The GUI's structured inspector and typed command forms use the existing service;
no proposed storage plan or writer is invented by the interface.

High contrast was observed off. High-contrast-on, screen-reader, per-monitor DPI,
old Windows, remote/Explorer and clean-VM checks remain unqualified. The
[review](REVIEW.md) records defects and fixture repairs; the
[handoff](../../handoffs/DE-W015-native-gui-2026-10-06.json) retains owner acceptance
as pending. Local continuation to DE-W016 is covered by the programme grant.
The complete DiskEd 0.1.0 goal remains active.
