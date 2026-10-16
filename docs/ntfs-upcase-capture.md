# NTFS uppercase-table capture

DE-W100 acquires the table's actual logical bytes through the existing supplied
region reader, MFT mappings and attribute-list/stream closure. Its
[execution contract](../spec/catalog/ntfs-upcase-capture-prototype.json) defines
expected behaviour before evaluation. It adds no native source opener or command.

FILE 10 must be a valid observed base record, with its full sequence/reference
retained. The selected unnamed data stream must provide the complete initialized
131,072-byte table under the existing finite budgets. Fragmented mappings and
supported list extensions use the same qualified closure as other NTFS metadata.
The collector rejects selected metadata aliases and preserves exact table bytes,
their digest, source-region identities and volume/capture context.

Final rereads qualify only the finite observation. Supplied source/window/epoch
assertions do not prove native identity, atomicity or future freshness. A table
retained before a failed reread remains evidence; it confers no applicability.
There is no default host table, Unicode normalization or lookup admission.

This belongs in the existing `ntfs_capture` owner because that owner already
manages acquisition and coherence. The C90 table mechanics remain in
`portable/ntfs/upcase.c`. No production file or directory is added. Native held-file
and worker binding, namespace/index/alias policy, lookup/content, all original
platforms/storage and owner/release gates remain required.

The [agent review](../.aide/evidence/2026-10-17-ntfs-upcase-capture/REVIEW.md)
links exact source,complete current x64 and selected private Win32 results,retained
fixture failures and unverified capabilities. Owner acceptance remains pending.
