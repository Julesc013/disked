# NTFS attribute-list parser development

DE-W084 implements the bounded supplied-byte entry cursor needed for later
attribute-list/MFT extension support. The [execution contract](../spec/catalog/ntfs-list-prototype.json)
defines framing, raw values, EOF and stopped-prefix outcomes before evaluation.
The first working native build passes 561 protected-byte cases. Exact-source
qualification and implementing-agent review remain pending. The retained
reproduction recipe selects list/record/boot/attribute/run, reader/file/worker,
command and dependency regressions; it does not claim the complete product suite.

An entry observation does not establish live reference/sequence validity or a
complete attribute stream. Borrowed names retain exact UTF16LE bytes. The parser
has no source/provider callbacks or storage effects; the existing NTFS command
remains bootstrap-scoped until source-bound joining is implemented and verified.
