# Global FAT allocation observation: 2026-10-13

Native source `0e414ccd49f5905b0d1ae2ce554fa72d9fe2e04a`; base `4e53d27b96cc78095ec9c8dcab2da152d62c4f70`. DE-W028's expected contract was committed
at `4069eb3e` before implementation; aggregate consistency was clarified at
`4942ddd6` before the corrective code. Standing local implementation/tests/implementer
review and tested dev/main synchronization grants apply; owner acceptance and the
full all-platform/storage 0.1.0 goal remain separate.

## Implemented scope

The existing private FAT capture has an opt-in paged data-cluster scan. Default
tree capture and public command identities/version remain unchanged (dev.42/21).
The same ordinary-file adapter performs read-only capture and repeated-region
verification. No new source tree, target family, frontend, mount or writer exists.

FAT12/16/32 cells come from <=4096-byte declared-table pages, including cells
crossing a page boundary. Only data-cluster entries enter category counts. A
covered cell is published after its complete requested copy-comparison set.
Selected-copy interpretation, raw variants, interpreted disagreements and
uncompared copies stay distinct. Table/header padding is not counted as data.

Linear graph analysis counts links into free/bad/reserved entries, suffix links,
incoming merge points, cycle components/cyclic clusters and allocated cells
without observed tree owners. Missing suffix cells remain unknown. Qualification
of unreferenced allocations against this observation requires complete consistent
tree ownership, allocation coverage, copy agreement and overlapping-byte agreement.
That is metadata applicability, not lost-content recoverability or repair authority.

Tree completion, allocation coverage, copy comparison, prefix graph analysis and
detail completeness have independent fields. Later scan failures preserve tree
outcomes. Finding omissions preserve total counts and covered-prefix analysis.
Both count and output quotas apply. The summary is reserved before tree processing
so a low detail budget cannot silently discard allocation outcome fields.

Selected-cell/workspace cap 262144, finding cap 128; existing <=2MiB captured bytes,
8192 requests and <=1MiB output apply across the entire capture. Geometry/budgets
that exceed one observation produce an explicit prefix, never an all-table claim.
These finite payload/work limits do not establish exact RSS, timing, a coordinated
source snapshot or whole-filesystem health. FSInfo/backup/header semantics,
namespace/consumer rules, extraction and worker/frontend admission remain further
work in the full programme. True storage failures and other hosts are unverified.

## Actual verification

Native build, 92 test groups and tooling results remain at source 0e414ccd.
The first manifest check failed because CRLF working bytes had been hashed before
Git normalized bundle.json to LF. Repair beb48ad5 changes only spec/manifest.json;
the bridge proves every bound source/build input unchanged. Context and manifest
checks run at that clean specification revision, with original binaries preserved.
The original failed receipt remains a failure. No native result is relabelled as
a test of the later revision.

- 13 independent methods/86 cases, including 21 actual ordinary-file cases:
  complete FAT12/16/32 counts at four sector sizes; wide/nonzero origins; cycles,
  merges, damaged targets, ownership gaps, copy choices/raw variants/conflicts,
  page crossing/padding, incomplete suffixes, all scan/detail/read/byte/output
  budget families and exercised callback failure boundaries.
- Generated ordinary-file full hashes stay unchanged. Recapture faults deny
  stability; the normal build ignores test-only controls. No extraction/output
  file is created by capture.
- Prior 149 tree-capture, 1335 allocation and 6790 directory/name cases pass.
- All 92 native groups pass at exact clean source; 10 standalone headers compile.
  215 tooling tests run: 213 pass,
  2 skip. Structural/index/manifest/context/source-map checks pass.
- Windows x64 unprivileged Jules, MSVC 19.44.35228/toolset 14.44.35207,
  SDK 10.0.19041.0/CMake 4.2.3/Python 3.14.7 build, launch and imports are retained.
  GCC 15.2 strict C90 syntax only, with no GCC runtime/ABI or legacy claim.
- 502 source SHA/Git-blob bindings; 456
  build inputs; 135 generated targets/3558
  quoted include edges. Existing 205 source files keep their documented owners.
  Hashing is not semantic review of every input.

One initial negative fixture changed its boot object without changing the supplied
region. The fixture now supplies the damaged bytes; expected refusal is unchanged.
An initial boundary check preceded generation of bootstrap_registry.h. Building
its declared target resolved those missing inputs. Both original diagnostics and
corrected checks are retained; production validators were not weakened.

Review independently reproduced a true aggregate consistency flag alongside two
unreferenced allocated clusters. Source 0e414ccd requires zero such candidates
before the aggregate flag is true; tree completion and unreferenced applicability
remain separate. The regression retains the original expected refusal and graph
counts. The previous f89ef446 campaign predates this correction and is superseded
for current qualification; its source-bound records are archived separately.

## Retention and continuation

Raw commands/logs, independent case batch hashes, generated CMake projects/codemodel,
context, imports, artifact identities and implementer review are retained here.
Local executable/library copies: .aide-local/artifacts/DE-W028-fat-scan-0e414ccd/.
No release artifacts were published/signed and no physical/customer/elevated work
was performed. Owner and independent-person acceptance remain pending.

```text
.aide-local/venv/Scripts/python.exe -X utf8 .aide/evidence/2026-10-13-fat-allocation-scan/reproduce.py --source-revision 0e414ccd49f5905b0d1ae2ce554fa72d9fe2e04a --existing-clone .aide-local/owned-layout-clean-2c731a1c/checkout --output .aide-local/fat-scan-clean-new --gcc-executable PATH_TO_EXISTING_GCC_15_2
.aide-local/venv/Scripts/python.exe -X utf8 .aide/evidence/2026-10-13-fat-allocation-scan/resume_manifest.py --existing-clone .aide-local/owned-layout-clean-2c731a1c/checkout --output .aide-local/fat-scan-clean-new --specification-revision beb48ad592d790b5e99481407bfd364623037de5
.aide-local/venv/Scripts/python.exe -X utf8 .aide/evidence/2026-10-13-fat-allocation-scan/audit_retention.py
```

Use a fresh output and clean owned clone. Audit verifies retained applicability;
it is not a fresh native run. Later integration heads carry metadata/evidence;
native qualification remains at `0e414ccd49f5905b0d1ae2ce554fa72d9fe2e04a`.
The first reproduction command retains its known manifest failure; the second
finishes verification using the exact manifest-only repair and unchanged inputs.
