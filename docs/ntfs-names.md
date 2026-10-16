# Captured NTFS filename instances

DE-W094 implements the [private contract](../spec/catalog/ntfs-names-prototype.json).
Implementation and qualification are pending. This is a lossless supplied-record
inventory, a prerequisite for checking directory entries against target records.
It does not establish source provenance, current membership, lookup or collation.

`ntfs_names.*` owns filename-instance results; `ntfs_stream.*` joins one ordinary
stream. Their shared private `ntfs_attributes_detail.*` validates captured FILE
identity and attribute-list selection. A repeated filename value does not become
one stream: preserve every distinct record/instance, parent and namespace.

The exact raw UTF16LE name and original value survive independently of display.
Unsupported, malformed, missing and budget-limited evidence cannot produce a
complete typed inventory. Native acquisition, namespace/content and every
original 0.1.0 platform/storage requirement remain later work with their gates.
