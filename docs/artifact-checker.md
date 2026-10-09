# Check local staging and ZIP completeness

DE-W063 provides a private Python development tool for the current Windows native
prototype. It does not extract or execute ZIP entries. It compares a ZIP against
an inventory generated from separate staging before packaging. A passing check
establishes completeness against that inventory; it does not supply owner
acceptance, authenticity, runtime qualification or permission to publish.

Use ordinary local files in quiescent disposable staging. Select required
entrypoints explicitly and review the staging selection and inventory. Keep the
inventory outside staging and do not generate it from the ZIP being tested.
For the current `windows.native.image.prototype` composition the sole public
entrypoint is `disked.exe`; test probes and private journal libraries are not
product payloads.

After building with the [recorded native commands](native-bootstrap.md), prepare a
new staging directory containing only the intended payload. With that staging
already prepared, run:

```powershell
python tools/release/artifact_check.py inventory --staging .aide-local/package/stage --required disked.exe --output .aide-local/package/expected.json
```

Review `expected.json` before creating `.aide-local/package/disked.zip` from that
staging using a separately selected ZIP producer. Then run:

```powershell
python tools/release/artifact_check.py verify --inventory .aide-local/package/expected.json --archive .aide-local/package/disked.zip
python tests/artifacts/test_artifact_check.py
ctest --preset windows-bootstrap -R '^artifacts.archive_completeness$'
```

The inventory command creates its output exclusively and refuses to overwrite an
existing file or write inside staging. `--required` can be repeated. Both commands
emit JSON results, exit 0 on success and 1 on rejection or I/O failure; argument
usage errors exit 2. Verification reports archive, canonical inventory and exact
inventory-file SHA-256 hashes. Required entrypoints must exist and be nonempty.

The [proposed profile](../spec/catalog/artifact-checker-prototype.json) defines
the strict supported subset: single-volume stored/deflated ZIP, bounded classic
and ZIP64 metadata, ZIP64 extra fields and data descriptors. Unknown extra fields,
other compression, encryption, links, unsafe or colliding paths, missing/extra
content and inconsistent metadata refuse. Actual decompressed length, EOF, CRC and
content hashes are checked; declared sizes cannot hide extra output. Local records
must be contiguous without overlap or hidden data.

The limits include 4,096 files, 4,096 parent directories, 8,192 ZIP entries, a 4 MiB
inventory, 8 MiB central directory, 512 MiB per file/archive and 1 GiB total content.
These are explicit input/read limits, not measured memory or time guarantees.
Exact NFC Unicode names are preserved; unsupported names refuse rather than being
renamed. The conservative case rules can reject archives a particular filesystem
would accept. Quiescent staging is required: change detection is not an atomic
snapshot or hostile concurrent-filesystem sandbox.

Retain source revision, tool versions, commands, results, inventory and archive
identities in work evidence. Product launch/import tests use the trusted native
build separately. Owner review, publication/download comparison, signing,
installation, extraction containment and other platforms/carriers remain separate
checks. No distributed release follows from running this tool locally.
