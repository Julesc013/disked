# Supplied-byte FAT allocation metadata: 2026-10-13

Native source `97a377d7f88c20372c8308874c9831c389d9a91e`; starting base `0814187f2a7b27a15807cfc4160d898cdbffb5c1`.
The execution contract was committed before implementation at
`6ac9d1455fa5938b4d8d6285a6d549154c34edd5`. DE-W025 uses the existing local
development/testing/implementer-review and dev/main synchronization grant.
Owner acceptance, complete filesystem capability and release admission are separate.

## Result

Private `portable/fat/fat.h`, `volume.c` and `allocation.c` implement C90 supplied-byte
FAT12/16/32 boot geometry, packed allocation entries and bounded chain prefixes.
They use existing byte views and checked integers, with no allocation or host I/O.
Informational labels cannot select the format. Exact FAT32 raw/high-nibble values,
FAT12 packed neighbors, caller-selected copies and content issues are preserved.
Signature/geometry/region/capacity/version/feature contradictions prevent a usable
layout. Volume byte extents can exceed 32 bits without native long-long dependence.

Chains have caller workspace and a maximum of 1,024 steps. Empty/end/free/bad/reserved,
invalid start, cycle, missing entry, host width and budget outcomes remain distinct.
A known cycle precedes exhaustion of the next unseen-cluster budget. Error arguments
and insufficient capacity refuse before reading FAT bytes or publishing output.
The library does not choose an authoritative mirrored copy or grant effects.

The compiler builds a private disked_fat library and test probe; neither enters
disked.exe's generated dependency closure. Its public command set remains unchanged
at 0.1.0-dev.42. CMake owns/exports the one private header under the existing namespace;
one additional independent translation unit checks self-contained inclusion.
All 199 current source files are documented once; no alternate source tree was added.

## Actual verification

- Exact clean unprivileged Windows x64 build, launch and import/dependency observations
  with the existing pinned MSVC 19.44.35228, toolset 14.44.35207, SDK 10.0.19041.0,
  CMake 4.2.3 and Python 3.14.7.
- 19 independent Python test methods execute 1,335 supplied-byte cases. Fixtures cover
  threshold counts, sector/cluster units, wide extents, contradictory/unknown metadata,
  packed cells, all marker classes, conflicting explicit copies and bounded chains.
  Deterministic fixture seeds and input/output batch hashes are retained.
- Actual Windows protected read-only/end-of-page and inaccessible-input capacity
  checks pass. The C library is linked from C++; eight headers compile independently.
- All 87 native groups pass, including the existing image/recovery/frontend/resilience
  regression. Generated checks cover 126 targets and
  3461 quoted edges with no violations.
- 215 tooling tests run: 213 pass,
  2 skip. Structural/index/manifest/context/source-map checks pass.
- Existing MinGW GCC 15.2.0 accepts the two C sources with -std=c90, -pedantic-errors,
  -Wall, -Wextra and -Werror. This is syntax checking, not GCC execution/ABI or DOS,
  OS/2, other compiler, historical host or hardware qualification.
- 488 source SHA/Git-blob bindings and 442
  build input identities are retained. Hashing is not a semantic review of every file.

Exact commands, logs, raw CMake projects/codemodel, header ownership, context archive,
GCC identity and artifact hashes are retained. Local EXE/LIB copies are in
.aide-local/artifacts/DE-W025-fat-97a377d7/; no release is published or signed.
`reader_host_io=false` describes the C reader, not the build/test runner's ordinary
source, executable, stdin/stdout or log I/O.

## Diagnostics and limits

The first development boundary check followed a FAT-only target build; unrelated
generated bootstrap headers did not yet exist. Those unresolved-include diagnostics
are retained. Building the complete composition generated them; the same checker
then passed. No dependency or expected output was weakened.
Visual Studio's formatter directory did not contain the assumed clang.exe; discovery
found the already installed GCC. No Clang syntax/runtime result or installation is
claimed. All tested commands in the clean campaign have their own actual receipts.

Primary format facts come from Microsoft's 2005-08-30 specification (sections 3/4),
with Linux v6.12 definitions as corroboration. The profile records links. No supplier
implementation was copied or fetched code executed. Selected strict observation
rules and conservative usability do not reproduce every operating system's mount rules.

Directory entries and lossless long names, global allocation/cross-link verification,
file extents/extraction, FSInfo/backup validation, provider capture, frontend commands,
all target environments and writers remain unimplemented by this slice. A usable
layout or completed chain is not a healthy filesystem or mount/boot compatibility.
Production journal, recovery, owner, physical/elevation/customer/install/sign/release
gates stay separate. The full all-platform/storage 0.1.0 goal remains active.

## Reproduce and audit

```text
.aide-local/venv/Scripts/python.exe -X utf8 .aide/evidence/2026-10-13-fat-allocation/reproduce.py --source-revision 97a377d7f88c20372c8308874c9831c389d9a91e --existing-clone .aide-local/owned-layout-clean-2c731a1c/checkout --output .aide-local/fat-clean-new --gcc-executable PATH_TO_EXISTING_GCC_15_2
.aide-local/venv/Scripts/python.exe -X utf8 .aide/evidence/2026-10-13-fat-allocation/audit_retention.py
```

Use a clean owned local clone, fresh output and the recorded dependencies. The audit
checks evidence applicability/hashes without rerunning tests or granting acceptance.
Later metadata integration has a newer head; native qualification stays at the exact
source. Older evidence remains immutable and tied to its own source/fixture/host.
