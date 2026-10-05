# DE-W010 native evidence

The executable was built from a clean independent clone of
`e08a12f620beb5e21efd56e153e256f6efeee625` on Windows 10 x64 build 19045,
under `BLACKGLASS-WIN1\Jules` with a non-elevated token.

- Local artifact: `.aide-local/artifacts/DE-W010-e08a12f6/disked.exe` (repository root relative).
- SHA-256: `f66737a8437b8a79e2ac050daf0194908b52cef0a9d05e297a42fa12163cda7c`.
- Compiler: MSVC 19.44.35228.0; SDK: 10.0.19041.0; Release, C++14, static CRT.
- Three CTest checks passed: two native suites (130 process invocations each) and
  the poison-provider positive control. Separately, 155 specification tests ran:
  153 passed and two symlink tests skipped.

[native-results.json](native-results.json) binds the source inputs, build settings,
artifact, host and limitations. [clean-commands.json](clean-commands.json) records
the exact configure/build/test/audit commands, working directories, exit codes and
log hashes. [clean-build.log](clean-build.log) includes actual compiler/linker
flags. [clean-tests.log](clean-tests.log) retains native assertion results.

The executable provides human help, build identity and command discovery. The fake
component is an inert identity/initialization boundary; there is no disk graph.
All storage commands, full machine output, TUI, GUI and shell remain unavailable.
Discovery reports 2 implemented human subsets and 32 planned commands; the complete
public command contracts remain planned. No disk, image or device operation ran.

The only direct DLL import is KERNEL32.dll. The embedded manifest requests
`asInvoker`. [dependency-closure.json](dependency-closure.json) records the static
host DLL graph, including delay-load dependencies and host API-set contracts. This
is not a trace of all loaded modules or system calls and does not prove another
Windows version works. [identity-freshness.json](identity-freshness.json) records
source and revision changes detected without reconfigure. The executable above
was preserved before those disposable probes.

The specification manifest also verifies in the clean clone. The 36 AIDE exports
pass passive validation at the existing pin; no live AIDE worker ran. Earlier
working-tree results and corrected fixture/configuration failures are retained
separately. No skipped check is counted as a pass.

Owner baseline and implementation acceptance remain pending. There is no XP/7/11
or clean-VM qualification, no full DE-W012 grammar execution, no GUI/console-launch
matrix, and no storage/recovery/installer/release qualification. Builds are
functionally reproducible, not claimed byte-for-byte identical across paths/times.

Review this bounded result next; the subsequent tasks are DE-W011 launch/console
observations and DE-W012 shared CLI/machine semantics under their own work scopes.
