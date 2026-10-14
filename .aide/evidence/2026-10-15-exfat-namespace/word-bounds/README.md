# Namespace probe word-size boundary checks

Code review found unchecked u64-to-size_t conversions in the private supplied-data
probe. A 32-bit build could narrow oversized budgets or capture-local IDs before
the runtime validates them. The probe now rejects unrepresentable values first.
This does not alter product code or qualify the full x86 product or historical OSes.

The retained runner derives the six-library source closure from the actual
qualified CMake codemodel and checks its unchanged sources. It builds only the
supplied-data probe and two standalone headers for x64 and Win32, runs the existing
303 independent namespace cases plus 13 decimal-boundary cases per architecture,
and records compiler/configuration/import/source/artifact facts. An old-probe-only
Win32 baseline measures the previous conversion against the unchanged kernel.

Execution is pending. Finish the isolated full142 campaign before starting this
supplement. Use the pinned modern compiler; no product preset or legacy claim is
weakened. Run from the repository root:

```text
.aide-local/venv/Scripts/python.exe .aide/evidence/2026-10-15-exfat-namespace/word-bounds/qualify-namespace-word-bounds.py --source . --revision <bounds-source-revision> --codemodel-build .aide-local/exfat-namespace-exact-2545d078/build --output .aide-local/namespace-word-bounds-<short-revision> --cases .aide/evidence/2026-10-15-exfat-namespace/word-bounds/namespace-size-cases.py
```

No native result or regression reproduction is claimed until actual execution.
