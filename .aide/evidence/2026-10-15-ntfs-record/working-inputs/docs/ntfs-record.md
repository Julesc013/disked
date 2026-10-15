# Private NTFS record prototype

`source/portable/ntfs/record.c` observes a caller-supplied NTFS3.0/3.1 FILE record
and, after validating its envelope and every update-sequence tail, restores those
tail words into a separate caller-owned RAM buffer. It opens no file or device.
`ntfs.h` declares this private C interface; `record.c` names the implemented
responsibility without reserving filenames for future boot/attribute decoders.

The [expected contract](../spec/catalog/ntfs-record-prototype.json) fixes the
512-byte protection stride,42-byte common header, exact entry count, first-stride
array placement, header relationships and49,152-byte observation budget.
The Microsoft member prose calls the array count bytes while its formula uses
16-bit entries; the contract explicitly follows the formula and corroborating
primary layout. Original signature, sequence, raw flags, identifiers and sizes
remain observations. Unknown flag bits are preserved. A torn record is never
partially restored, and rejected restoration preserves the entire output and
result. Input/output overlap is rejected; restoration writes RAM, not storage.

The [independent fixture generator](../tests/property/test_ntfs_record.py) creates
logical records, protects their tails, and compares the actual native decoder
and restored bytes against Python integer/struct oracles. The
[probe](../tests/unit/ntfs_record_probe.cpp) places supplied input directly before
an inaccessible page and marks readable input pages read-only. It separately
checks API misuse, capacity and overlapping output sentinels.

Use the pinned Windows bootstrap lane:

```text
cmake --preset windows-bootstrap
cmake --build --preset windows-bootstrap --target ntfs_record_probe disked_ntfs_headers --parallel 4
ctest --preset windows-bootstrap -R "^portable.ntfs_record$" --output-on-failure
```

This primitive is not linked into product command dispatch. It establishes no
NTFS volume, MFT addressing, attribute/runlist traversal, atomic acquisition,
provider/source authority, writer, recovery or legacy-platform qualification.
Those original programme requirements remain open. Exact commands, source and
artifact identities belong in the work unit's retained evidence; this guide
does not claim a passing campaign or owner acceptance.
