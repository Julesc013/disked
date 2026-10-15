# Private NTFS boot geometry

`source/portable/ntfs/boot.c` interprets supplied boot bytes using the existing
checked C90 integer layer. `ntfs.h` declares its private observation alongside the
FILE-record primitive. The [expected contract](../spec/catalog/ntfs-boot-prototype.json)
defines observable fields, limits and diagnostics before evaluating the code.

The BPB sector field, checked data bound, extra last-backup sector and outer
available window are distinct quantities. Cluster and record encodings are
decoded from unsigned bytes, with no implementation-defined signed-char cast.
Large-cluster observations and record budgets stay distinct from format validity.
Missing boot markers and optional checksum disagreement remain advisory facts.

Geometry, record/index size knowledge, FILE-record budget support, seed address
validity and usable bootstrap are separate properties. Seed candidates must fit
complete allocation clusters, stay inside the data bound and avoid the primary
boot sector and each other. Boot metadata cannot locate arbitrary later MFT
records: that requires the MFT's validated attributes and runlist.

The [boot fixture](../tests/property/test_ntfs_boot.py) uses Python signed-byte,
struct and arbitrary-precision integer oracles. Both native NTFS probes use
`tests/unit/ntfs_probe_support.h` for unchanged bounded JSON input and protected,
read-only input pages. This is a test helper shared by two actual consumers,
not a new runtime support layer.

```text
cmake --preset windows-bootstrap
cmake --build --preset windows-bootstrap --target bootstrap_registry ntfs_boot_probe ntfs_record_probe disked_ntfs_headers --parallel 4
ctest --preset windows-bootstrap -R "^portable.ntfs_(boot|record)$" --output-on-failure
```

No boot code is executed, file/device opened or storage changed. The prototype
does not establish a complete NTFS volume, coherent acquisition, current source,
mount/boot capability, attributes/runlists, provider/frontend availability or
writer authority. Actual compiler/test results and unverified environments belong
in retained evidence; the guide does not assert a passing campaign.
