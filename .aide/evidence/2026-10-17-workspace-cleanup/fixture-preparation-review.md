# DE-W105 bounded Win32 fixture preparation

Status: tooling prepared and tested; **native qualification not run**.
Base revision: `9dfd587d761c6f016960a29411d76675341e7f8d`.

The historical Win32 supplement reads CMake metadata from an x64 build tree.
Cleanup removed that disposable tree. Recreating whole checkouts or executing
the old orchestration would reintroduce the resource problem. The historical
recipe remains unchanged as revision-bound evidence and a literal expectation
source, not a command to run under the current storage gate.

`tools/ntfs-win32-fixture.py` prepares its scoped CMake fixture from fresh File API
metadata for the same source/build directories. It reads at most 32 MiB of unique
inputs, rejects oversized files, cycles, unsafe paths, missing headers, incorrect
normal/fault definitions and incompatible compiler/runtime profiles, and writes
at most 128 KiB into a fresh owned managed-work directory. Output is fourteen
files: twelve header translation units, CMakeLists and a manifest binding input
and generated-file bytes. It copies no checkout and invokes no compiler/test.
The generated CMake project also includes the workspace guard before `project()`.

Tests independently read the historical recipe's literal declarations with AST
parsing; they do not import or execute that recipe. All eighteen groups, twelve
header names, nine executable targets and exact probe arguments are preserved.
In particular multi-probe commands keep `--pure`, while standalone capture
commands keep `--probe`. A real junction test checks that source aliases are not
followed. The source product's x64 identity is not presented as the Win32 fixture
profile. The manifest explicitly states that its binding scope is preparation,
that its execution-input closure is incomplete, and that it establishes no native
qualification, owner acceptance or hard storage boundary.

Actual verification:

- Initial focused tests: twelve passed. The final suite includes fourteen fixture
  preparation tests, with the later junction and runtime-profile checks.
- Final tools suite: 81 run, 80 passed, one existing Windows PowerShell execution
  policy skip. `fixture-preparation-final-tooling.log` retains the result.
- Specification-tool suite: 253 run, 251 passed, two existing symlink skips.
  `fixture-preparation-spec-tests.log` retains the result. The later profile-label
  clarification received the final tooling run and structural/freshness checks.
- Index, structural validation, manifest generation and verification passed.
- Read-only inspection verified all 32 current repository header/script/profile/
  guard inputs. This is file presence/identity evidence, not compilation evidence.
- The full validation workspace peaked at 52,438,629 bytes and was removed. The
  final tooling/freshness run peaked at 483,130 bytes and was removed. Logs and
  small metadata were retained; no environment or generated native tree remains.

No current-source CMake configuration, MSVC compilation, native launch, Win32
case execution, PE/import inspection or filesystem/worker-isolation proof was
performed. The existing environment selection question is still pending. After
the owner supplies a qualified worker or grants a bounded setup, first prove that
boundary, then generate fresh metadata and use this preparer in bounded native
execution/retention orchestration. DE-W105 and the full 0.1.0 objective are not
complete, and no main promotion or release is claimed.
