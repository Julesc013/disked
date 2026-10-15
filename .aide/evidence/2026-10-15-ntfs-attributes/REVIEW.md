# DE-W078 implementing-agent review

The available supplied-byte scope reaches its review boundary at exact clean
`6daed9fd9dd2a642e04d727000e31b8b70253dda`. This is the implementing agent's
review, not owner acceptance or independent storage safety qualification.

Attribute traversal reuses the existing FILE restoration before borrowing only
the restored used-byte span. It bounds common/variant headers, original names,
resident values and mapping bytes. Bounded unknown/malformed variants retain
diagnostics; unsafe lengths stop. An observed end marker, missing marker and
budget stop remain distinct. Continuation size fields are not treated as current
stream sizes. Values/names remain raw bytes rather than normalized presentation.

Review independently reproduced signed-negative size and VCN false-positive
envelopes at ab33609d. The correction diagnoses applicable signed fields while
retaining their raw bits and the special empty-stream sentinel. Baseline and
corrected observations remain in signed-correction/. Existing passing checks
were not erased; the contract clarification and strengthened expectations were
recorded before evaluating the correction. Undefined continuation sizes remain
opaque, including high-bit patterns.

Mapping iteration uses checked limb arithmetic for signed deltas and exact
VCN/LCN ends. Sparse runs are explicit zero-width offsets; mapped LCN zero is
data. The selected compatible positive signed length profile is documented
against the differing primary readers. Standalone run coordinates are explicit
unsigned bounds; they do not establish applicability of arbitrary signed NTFS
header fields or source authority. Prefixes, budgets, terminators and coverage
remain separate; stopped/terminal calls preserve output and cursor state.

Exact native results pass 259 attribute, 632 mapping, 1,729 boot and 964 record
cases, including protected/read-only original/restored bytes, actual overlap and
error sentinels, API misuse, signed boundaries, empty/continuation attributes,
negative/zero deltas and all width/range/coverage failures. Fourteen selected
portable groups, one standalone header, the build/header audit, attributes-probe
imports/security, strict GCC/Clang C90 syntax for all four sources, 242 tooling
tests/two skips and structural/manifest/context freshness pass. All declared
source inputs remain unchanged through the run.

The clean sparse checkout contains all 1,004 registered/build inputs and complete
current source/tests/spec/docs/tools/external trees, excluding unused historical
evidence. This is not a full archive checkout or complete native/product campaign.
Retained context files are receipts; recreate the pack at the exact revision.

There is no attribute-list extension joining, payload-specific interpretation,
decompression/decryption, complete stream/namespace, coherent held-source/provider
or frontend, mount/boot or writer/recovery admission. The prior W075/report
failures remain unresolved; whole-branch integration is not qualified here.
Continue coherent supplied-reader NTFS collection and the original target/storage
programme with owner, licensing, physical and release gates intact.
