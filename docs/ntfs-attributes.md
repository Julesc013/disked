# Private NTFS attributes and mapping pairs

`portable/ntfs/attribute.c` restores supplied protected FILE bytes through the
existing record primitive, then traverses the restored used-byte span. It bounds
resident values, original UTF16 names and nonresident metadata/mapping bytes.
`runlist.c` separately iterates supplied mapping pairs with explicit VCN coverage,
volume-cluster and item bounds. `ntfs.h` declares these private C90 interfaces.
The [expected contract](../spec/catalog/ntfs-attributes-prototype.json) precedes
implementation evaluation; no public ABI or storage authority is introduced.

Attribute cursors stop at an observed end marker or retain a diagnosed prefix.
Continuation size fields, unknown types/features, compressed/encrypted content
and post-marker slack keep distinct meanings. Initialized length is not rounded
up into data that was never initialized. Names remain exact encoded units.
Applicable signed size/VCN fields reject negative interpretations while retaining
their original bits; continuation size fields remain explicitly undefined.

Mapping lengths use the selected positive signed profile. Negative LCN deltas
use checked limb arithmetic; zero-width offsets denote sparse runs and leave the
previous LCN intact. A nonzero-width offset mapping to LCN zero denotes mapped
data. The contract records differences between primary readers instead of
silently turning those cases into equivalent data. A terminator must agree with
the requested VCN coverage. No incomplete prefix becomes a complete mapping.

The native probe uses protected read-only original and restored buffers, plus
actual overlapping/capacity/error sentinels. Independent generated logical
records are protected before entering the C implementation. Python integer and
signed-byte oracles check mapping arithmetic and preservation of valid prefixes.

```text
cmake --preset windows-bootstrap
cmake --build --preset windows-bootstrap --target bootstrap_registry ntfs_attributes_probe ntfs_boot_probe ntfs_record_probe disked_ntfs_headers --parallel 4
ctest --preset windows-bootstrap -R "^portable.ntfs_(attributes|runlist|boot|record)$" --output-on-failure
```

These observations do not join attribute-list extensions, validate complete
streams/namespace, decompress/decrypt, open files/devices or admit a provider,
mount/boot capability, writer or recovery operation. Exact results and untested
environments belong in source-bound evidence. Original full platform/storage
scope and owner/release gates remain open.
