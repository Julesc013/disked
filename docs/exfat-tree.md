# Bounded exFAT tree and logical-content observations

DE-W074 implements the [expected private contract](../spec/catalog/exfat-tree-prototype.json).
An opaque move-only `ExfatVolumeCapture` owns the existing root/system observation,
validated geometry, original bitmap/upcase bytes and reread anchors. Its factory
uses the original root validator; tree collection does not trust a supplied JSON
claim that a root or table is valid. The original root-report API remains available.

`exfat_tree.*` collects supplied-reader directories across fragmented or contiguous
allocations. It checks the active allocation bitmap, chain length, cycles and shared
cluster ownership, including declared inactive bitmap allocations. `NoFatChain`
extents do not read FAT cells. Names and entry association use the existing exact
volume map and portable decoder. Zero-length directories are supported.

Logical file observations read only the bytes before `ValidDataLength`, then emit
defined zeroes through `DataLength`. Raw undefined tail bytes are neither read nor
disclosed. The output records source/zero byte counts and the logical content digest.
This is an observation, not extraction or permission to open a native path.

The mandatory applicability callback checks the exact source/epoch/window. The
collector rereads root anchors and new regions and reports failures or withdrawal.
These checks qualify observed regions; they do not establish an atomic snapshot or
current-source/mutation authority. Finite bounds produce incomplete results with
diagnostics and retained directory-record prefixes.

The working x64 Release build currently passes 40 independent cases in nine tree
methods, all seven selected tree/namespace/root/file/worker/frontend/build-boundary
groups and 51 standalone headers. The protected-view case also compares the original
root API's result and exact read trace with the owned capture. Initial failed fixture
addresses and corrected results are retained. The exact full143 campaign at
`bf26a4a4` finished with142 passes and one failed GPT restoration group. Its isolated
rerun also failed, including an unconfirmed termination and attempted cleanup of
an in-use dependency. [Retained evidence](../.aide/evidence/2026-10-15-exfat-tree/README.md)
includes those failures and eleven supplementary passing tree cases. The restoration
harness now retains failed fixtures and captures process/reply diagnostics. Its five
regressions and an opt-in diagnostic run of138 restoration cases pass; the earlier
delay remains unexplained. A fresh full144 campaign, including the new harness
group, is required. Owner acceptance and full0.1.0 remain open.

Paged continuation, bounded stream delivery/backpressure, held-source and contained
worker/frontend admission, other platforms/storage and production writer/recovery
remain at their subsequent gates. No native opening or effects are part of this code.
