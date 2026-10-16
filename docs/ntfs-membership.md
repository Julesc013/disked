# NTFS directory-name correspondence

DE-W095's [private execution contract](../spec/catalog/ntfs-membership-prototype.json)
binds directory entries and target filename instances to one supplied source,
window, profile and capture epoch. Implementation and qualification are pending.

The existing capture owner retains reads, target FILE/list closure, overlap
checks and final exact rereads. The membership collector compares full parent
references, original UTF16LE name bytes and namespace codes, preserving separate
instances and opaque source values. Exact correspondence does not establish
collation, lookup, uniqueness, full namespace/tree health or source authority.

Existing bootstrap/directory behavior and native/public command forms remain
unchanged. Native file/worker/public admission, content, all original 0.1.0
platform/storage requirements and owner/release gates remain separate work.
