# FAT namespace and name-model evidence: 2026-10-13

Native source `330c223c6f184cce9cb8a922f1364118a039def6`; base `9e1e400a54d603990743cb451ce52a550b823d55`. DE-W036's expected contract was committed
at `b9151eb7` before implementation. Output-reserve and conservative component
rules were reconciled before qualification at this source. Standing local
implementation/testing/implementer-review and dev/main synchronization grants apply.
Owner acceptance and the full all-platform/storage 0.1.0 finish line remain separate.

The private runtime namespace observer uses typed original entries, directory
coverage and explicit decode/eligibility/comparison callbacks. Original 11 OEM
bytes and UTF-16 units remain separate from derived aliases. A short and long
alias of one entry produce one lookup candidate; cross-entry collisions remain
ambiguous, and different parents have independent namespaces. Exact stored OEM
duplicates are observed even without successful conversion. Returned IDs are
local to this capture, not durable file identities or access grants.

The Windows adapter requires an explicit installed CP437/850/932. It applies
the FAT 0x05 lead escape, trims only fixed-width byte padding, converts base/ext
independently with strict invalid-byte handling, and compares eligible UTF-16
using CompareStringOrdinal(ignoreCase=true). It performs no Unicode normalization,
source-name path construction or file opening. Its conservative component rules
reject traversal, controls, separators, invalid surrogates and reserved device
forms/extensions, including superscript digits and CONIN$/CONOUT$. Short fixed
fields have their separately declared shape restrictions. These APIs/rules are
a recorded-host model, not qualification of a mounted FAT driver or every host.

Queries return unique, ambiguous, not_found, incomplete, query_rejected or
directory_not_observed. Unknown/throwing/malformed callbacks, nonreflexive or
asymmetric comparisons, partial directory records/chains and exhausted comparison/
output budgets cannot qualify unique lookup. Detail omissions and total findings
are retained separately. Late byte overlap and ordinary-file recapture failures
withdraw unique/not_found applicability without erasing measured names/matches.

Limits remain finite: 128 entries/directories, 256 aliases, 16 single-component
queries, 65,536 comparison calls, 128 finding details and <=512 KiB model output.
Capture namespace mode reserves 512 KiB and requires >=768 KiB total observation
output. Querying adds no source reads. These are payload/work limits, not an exact
RSS or scheduling guarantee. Default capture and dev.42's public command surface
remain unchanged; the FAT/name-model libraries remain outside disked.exe.

The focused suite passed 14 methods/171 cases, including 21 actual ordinary-file
observations. Independent ASCII candidate-set and raw/Unicode fixtures cover
short/long/cross-form/same-entry collisions, separate parents, code pages, lead
escape, DBCS trail bytes, device/control names, invalid long forms, Unicode case
and composed/decomposed forms, every callback fault family, maximum shapes,
all budget families and late overlap/recapture denial. A separate ctypes API
caller checks native conversion/ordinal behaviour; it does not independently
qualify the FAT driver. Generated file whole hashes remain unchanged.

An initial added late-overlap test assumed a nonexistent three-sector read. The
actual reader deliberately issues bounded sector/header reads. The test now
targets the later 8-byte header overlapping earlier 4-byte FAT32 cells; the
expected withdrawal remains unchanged. The original failing harness log is retained.
Warning/error policies, source checks and expected outcomes were not weakened.

The clean, unprivileged Jules Windows x64 campaign passed all 95 native groups,
including prior 1,335 allocation, 6,790 directory/name, 149 capture, 86 global
allocation and 257 auxiliary cases. Twelve independent headers compile.
Tooling: 213 passed, 2
skipped (215 run). Structural/index/manifest/context/source-map,
actual build/product launch/imports and generated dependency checks pass.
MSVC 19.44.35228/toolset 14.44.35207, SDK 10.0.19041.0, CMake 4.2.3,
Python 3.14.7; GCC 15.2 strict C90 syntax only for the four FAT C sources.
511 SHA/Git-blob bindings/465 build
inputs and 139 targets/3585 quoted
include edges are retained. Input hashing is not semantic review of every input.

Raw commands/logs, source/blob bindings, context, CMake projects/codemodel and
12 executable/library hashes are retained here. Local artifacts are at
`.aide-local/artifacts/DE-W036-fat-namespace-330c223c/`; no executable publication,
signing, physical storage, elevation, image mount or installation was performed.

```text
.aide-local/venv/Scripts/python.exe -X utf8 .aide/evidence/2026-10-13-fat-namespace/reproduce.py --source-revision 330c223c6f184cce9cb8a922f1364118a039def6 --existing-clone .aide-local/owned-layout-clean-2c731a1c/checkout --output .aide-local/fat-namespace-clean-new --gcc-executable PATH_TO_EXISTING_GCC_15_2
.aide-local/venv/Scripts/python.exe -X utf8 .aide/evidence/2026-10-13-fat-namespace/audit_retention.py
```

Use a fresh output and clean owned clone. Retention audit is not a fresh native
test run. Integration commits add metadata/evidence; native source remains the
revision above. Continue larger/chunked volume/name coverage, explicit contained
worker/frontend inspection, extraction and further consumer/host qualification.
Production journal/recovery, owner/physical/elevation/customer/install/sign/release
and the full all-platform/storage 0.1.0 programme remain unfinished.
