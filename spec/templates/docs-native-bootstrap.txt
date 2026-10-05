# Build and run the native bootstrap

DE-W010 provides a console `disked.exe` with help, build identity and static command
discovery. It has a fake provider identity, with no disk graph or storage access.
This is a development prototype. The full CLI, JSON, TUI, GUI and storage commands
remain future work. The exact [execution contract](../spec/development/native-bootstrap.md)
owns the supported subset and diagnostics.

On Windows x64, use a Git checkout with CMake 3.27+, Python 3.10+, Git, VS 2022's
MSVC **14.44.35207** toolset (compiler **19.44.35228.0**) and Windows SDK
**10.0.19041.0** already installed. The checked-in preset chooses that compiler,
SDK, Release configuration, C++14 and static CRT. It downloads no dependencies.
These versions describe the tested prototype lane, not a permanent product floor.

From the repository root in PowerShell:

```powershell
cmake --preset windows-bootstrap
cmake --build --preset windows-bootstrap
ctest --preset windows-bootstrap
& .\build\windows-bootstrap\Release\disked.exe --help
& .\build\windows-bootstrap\Release\disked.exe build inspect
& .\build\windows-bootstrap\Release\disked.exe commands
```

The public artifact is `build/windows-bootstrap/Release/disked.exe`. Test builds
also create two internal provider-guard executables; they are not product
entrypoints. `build/windows-bootstrap/generated/build-identity.json` records the
exact source closure, compiler hash and embedded identity. Source changes and Git
revision changes refresh identity on the next build, without requiring configure.
`source_state=dirty` means the checkout had tracked or untracked changes when the
identity was generated; it must not be represented as an exact clean commit build.

`commands` shows separate public-contract status, subset implementation status and
availability. Only `build.inspect` and `command.list` are implemented in this human
bootstrap. `target list`, JSON, GUI and other unavailable functions return a fixed
diagnostic and exit 3. Invalid bootstrap arguments return 2; output failure returns
4. Neither full machine envelopes nor the complete DE-W012 grammar are admitted.

The tests run predefined cases and every registered command spelling from empty
temporary directories, with closed stdin and no toolchain on the child PATH. They
compare output and status and check for created files. A second linked build exits
97 if a command attempts provider initialization; a positive control verifies that
instrumentation. These checks do not trace every system call made by Windows or
the CRT, and are not physical-storage or process-isolation qualification.

The retained [native evidence](../.aide/evidence/2026-10-06-native-bootstrap/)
identifies the actual source commit, clean-clone commands, host, imports and hashes.
Only Windows 10 x64 build 19045 is exercised here. XP, Windows 7/11, clean VMs,
Explorer launch/console ownership, installation and storage operations remain
unverified. Installed legacy SDK files do not establish XP compatibility.

The build uses CMake's explicit [VS platform/toolset selection](https://cmake.org/cmake/help/latest/generator/Visual%20Studio%2017%202022.html)
and [static CRT property](https://cmake.org/cmake/help/latest/prop_tgt/MSVC_RUNTIME_LIBRARY.html).
Retained PE evidence uses Microsoft's [DUMPBIN dependency inspection](https://learn.microsoft.com/en-us/cpp/build/reference/dependents?view=msvc-170).
