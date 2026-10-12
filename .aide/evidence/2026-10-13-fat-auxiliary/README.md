# FAT auxiliary metadata evidence: 2026-10-13

Native source `87e7e246bc66a0429e93b2cebf83b1d6f61a91f0`; base `a7165e05cad7052418c72c026d31a80aebe9e05a`. Expected DE-W029 contract was committed
at `41e44f2c` before implementation. Standing local development/tests/implementer
review and tested dev/main synchronization grants apply. Owner and all-platform/
storage 0.1.0 acceptance remain separate.

## Implemented scope

`portable/fat/auxiliary.c` adds private C90 borrowed header/FSInfo observations.
Header shape, media binding, exact packed values and supported/present recorded
driver flags are distinct. Dirty/prior-I/O flags need attention without proving
current damage. FSInfo preserves signatures, reserved-byte issues, unknown versus
known count/hint values, declared-sector truncation and opaque padding. No heap,
host I/O, normalization, mount or authority is introduced in this C stratum.

Optional `auxiliary_checks` extends the existing supplied-region volume and
ordinary read-only Windows file capture. Default tree/allocation behavior and
dev.42/21 public commands remain unchanged; FAT libraries stay outside disked.exe.
All current 206 source files retain existing owners, with one actual C source added.

Headers are observed per requested copy. Primary FSInfo uses its explicit reference.
A present three-sector backup record must fit the reserved region before record
reads. Primary/backup raw offsets and bytes, independently decoded BPB, exact/BPB/
structural equality and advisory shadow differences remain distinct. No backup
BPB is followed as a new source, and no authoritative copy is chosen. Nonstandard
or absent locations remain explicit, with unsupported shadow interpretation unknown.

Known primary counts compare against complete agreed allocation observations only;
otherwise applicability is false. Valid known next hints are independently checked
in selected/requested FAT copies. Shape, coverage, advisory disagreement and prior
driver state are separate. A later overlap conflict withdraws earlier derived
allocation applicability while preserving measured counts and coverage. No metadata
agreement value certifies current health, a snapshot, recovery or repair authority.

Existing <=2MiB reads/8192 requests and <=1MiB observation output apply. Auxiliary
mode requires >=128KiB output and reserves 80KiB before tree work for bounded raw
metadata/results. These are finite payload/work limits, not exact RSS/timing bounds.
Actual file identity, parent pins and repeated-byte/metadata checks preserve the
existing live-uncoordinated consistency qualification.

## Actual verification

- 14 independent methods/257 cases, including 24 actual ordinary-file cases:
  all media/header/driver states and sector sizes, FSInfo shape/ranges/unknowns,
  incomplete/protected inputs, raw preservation, stale shadow hints, conflicting
  records, explicit references/bounds, combined budgets, partial trees and every
  exercised callback boundary with short/null/oversized/throw/change cases.
- Protected/read-only/end-of-page header and FSInfo prefixes pass; oversized
  inaccessible inputs and API errors preserve output. Generated actual image
  whole hashes stay unchanged; separate recapture controls deny stability, while
  normal builds ignore them. Out-of-range private file copy selectors refuse.
- A supplemental MSVC C90 program linked against this exact FAT library verifies
  unaligned FAT12/16/32 headers and FAT32 FSInfo. Its source, commands, logs and
  hashes are retained; its executable remains local. No broader ABI claim follows.
- Prior 149 tree, 86 global-allocation, 1335 allocation and 6790 directory/name cases
  pass. All 94 native groups pass; 10 independent headers compile.
- 215 tooling tests: 213 pass,
  2 skip. Structural/index/manifest/context/source-map checks pass.
- Clean unprivileged Jules Windows x64, MSVC 19.44.35228/toolset 14.44.35207,
  SDK 10.0.19041.0/CMake 4.2.3/Python 3.14.7 build, launch and imports retained.
  GCC 15.2 strict C90 syntax for four FAT C sources only, not runtime/ABI/legacy.
- 505 SHA/Git-blob bindings/459 build
  inputs; 135 targets/3559 quoted edges.
  Hashing does not semantically review every bound input.

The initial protected-fixture build exposed an int-to-byte narrowing warning.
The fixture now uses its explicit unsigned-byte value; warning/error policies were
kept. Review reproduced an earlier allocation-applicability flag staying true
after a later overlap conflict; the derived flag is now withdrawn with a regression.
Original diagnostics remain retained; expected outcomes and validators were not
weakened. Broader/real hardware failures and other hosts remain unverified.

## Reproduction and remaining work

Raw commands/logs, case-batch hashes, CMake projects/codemodel, context, import
observations and executable/library identities are retained here. Local copies:
.aide-local/artifacts/DE-W029-fat-auxiliary-87e7e246/. No executable release or
signing was performed. Owner and independent-person acceptance remain pending.

```text
.aide-local/venv/Scripts/python.exe -X utf8 .aide/evidence/2026-10-13-fat-auxiliary/reproduce.py --source-revision 87e7e246bc66a0429e93b2cebf83b1d6f61a91f0 --existing-clone .aide-local/owned-layout-clean-2c731a1c/checkout --output .aide-local/fat-aux-clean-new --gcc-executable PATH_TO_EXISTING_GCC_15_2
.aide-local/venv/Scripts/python.exe -X utf8 .aide/evidence/2026-10-13-fat-auxiliary/audit_retention.py
```

Use a fresh output and clean owned clone. Audit validates retention/applicability,
not a fresh native run. Integration heads add evidence/metadata; native source
remains `87e7e246bc66a0429e93b2cebf83b1d6f61a91f0`. Continue namespace/consumer rules, larger/chunked coverage,
extraction and actual contained worker/command/frontend admission. Preserve full
platform/storage, production journal/recovery, owner/physical/elevation/customer/
install/sign/release gates. The full 0.1.0 goal remains active and unfinished.
