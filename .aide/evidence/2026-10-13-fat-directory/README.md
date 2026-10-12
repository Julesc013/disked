# Lossless FAT directory/name metadata: 2026-10-13

Exact native source `205e6cd851c8e1b8c34af4bb5113299aa46a077c`, base `f9fc873c530b48a7dc3f9e8752fe744725d8fc11`.
The DE-W026 contract was committed before implementation at
`8c624f9eef3532fe237bd40e198c95d751823890`. The standing grant permits local
implementation/tests/implementer review and tested dev/main synchronization.
Owner acceptance, complete filesystem capability and release are separate.

## Result

The existing private `portable/fat/fat.h` adds directory/name APIs implemented
by `directory.c`. Original 32-byte records, OEM short-name bytes, case hints,
cluster words, DOS time fields and UTF-16LE units remain distinct observations.
No code page, case conversion, normalization, UTC or lookup key is guessed.
End/deleted markers do not turn stale bytes into live file metadata. Unknown
attributes, reserved fields, cluster/size and calendar/time contradictions are
reported alongside exact raw values.

Complete caller-supplied contiguous long-name sets are bounded to 20 slots and
260 raw units (255 name units). Exact reverse order, critical slot shapes and
the stored short-name checksum govern structural correlation. Encoding validity,
character/canonical issues and escaped display are separate. Surrogate pairs
may cross slots; invalid units are retained. ASCII display escapes controls,
bidi/non-ASCII units and backslashes without changing originals or creating
paths. Error/budget/capacity outcomes preserve output and immutable inputs.

The eight-bit checksum is format correlation, not authentication. An independent
collision fixture demonstrates different short records can match one set.
Provider identity/freshness, adjacency capture and lookup/namespace admission
are future responsibilities. The pure reader has no allocation, host I/O,
traversal, file extraction, mount or mutation. The generated product closure
still excludes disked_fat; shipping command/version remains dev.42/21.
All 200 current source files are documented once, without another source tree.

## Actual evidence

- Clean unprivileged Windows x64 build/launch/imports with pinned MSVC 19.44.35228,
  toolset 14.44.35207, SDK 10.0.19041.0, CMake 4.2.3 and Python 3.14.7.
- 19 independent directory/name test methods execute 6,790 supplied-byte cases:
  raw record kinds/fields, Gregorian date/time boundaries, all name lengths,
  Unicode/normalization distinctions, original OEM bytes, malformed sets,
  checksum/order/collision dimensions and reversible display/capacity rules.
- Actual protected read-only/end-of-page records and full 20-slot/255-unit name
  set pass; oversized/incomplete/capacity checks preserve output without reading
  inaccessible bytes. C/C++ linkage and eight independent headers pass.
- All 89 native regression groups pass, including the previous 1,335 allocation
  cases and existing image/recovery/frontend/resilience behavior. Generated
  checks cover 127 targets/3466 quoted edges.
- 215 tooling tests run: 213 pass,
  2 skip. Structural/index/manifest/context/source-map checks pass.
- Existing GCC 15.2.0 accepts all three FAT C sources under strict C90 syntax;
  no GCC runtime/ABI, historical compiler or other-host qualification follows.
- 492 SHA/Git-blob source bindings and 446
  build inputs retained. Hash binding does not semantically review every file.

Exact commands/logs, input/output batch hashes, raw CMake projects/codemodel,
header usage, context archive and executable/library identities are retained.
Local artifacts: .aide-local/artifacts/DE-W026-fat-directory-205e6cd8/.
These are unsigned/unpublished test/build artifacts. reader_host_io=false
describes the C reader, not source/build/test/stdio/log I/O by the harness.

## Diagnostics and limits

The first 18 methods passed. An added collision generator attempted to match
one fixed checksum using a restricted decimal-name family and found none; that
fixture assertion is retained. A pigeonhole search for two distinct generated
names sharing a checksum fixed the fixture, preserving the expected correlation
outcome. All 19 methods then passed. No reader guard, budget, expected outcome
or privilege/effect rule was weakened.

This is implementer review, not owner or independent-person acceptance.
Directory traversal and cross-cluster streaming, whole allocation/cross-links,
file extents/extraction, lookup/consumer compatibility, provider capture and
frontend commands remain unfinished. No healthy FAT, mount/boot compatibility,
all-target, physical/power-loss/production-recovery or complete 0.1.0 claim follows.
The production journal, owner, physical/elevation/customer/install/sign/release
gates remain separate. Earlier evidence retains its exact source/fixture/host.

## Reproduce and audit

```text
.aide-local/venv/Scripts/python.exe -X utf8 .aide/evidence/2026-10-13-fat-directory/reproduce.py --source-revision 205e6cd851c8e1b8c34af4bb5113299aa46a077c --existing-clone .aide-local/owned-layout-clean-2c731a1c/checkout --output .aide-local/fat-directory-clean-new --gcc-executable PATH_TO_EXISTING_GCC_15_2
.aide-local/venv/Scripts/python.exe -X utf8 .aide/evidence/2026-10-13-fat-directory/audit_retention.py
```

Use a clean owned local clone, fresh output directory and recorded dependencies.
The audit checks retained applicability; it does not rerun tests, authenticate
names/operators or grant acceptance. Metadata integration can have a newer head;
native qualification stays at the exact source revision.
