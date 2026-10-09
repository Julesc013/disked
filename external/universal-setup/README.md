# Pinned source and schema inputs

Nine unmodified schemas and the original MIT license are retained here.
`source-lock.json` binds the first five product-package/recipe inputs.
`native-source-lock.json` binds four read-only request/report schemas and the
84-file original CoreStatic source/build/license closure. Each record retains
the exact upstream Git blob, byte count and SHA-256.

No upstream runtime or scripts are committed to DiskEd. The DiskEd-owned
exporter reads pinned Git blobs into a new disposable directory. A separate
DiskEd CMake project compiles the unmodified 22 core and six Zlib sources for a
private C ABI probe. It never executes upstream CMake, Python or other scripts.
The disposable export includes original MIT and Zlib notices and provenance.
This is a source consumer candidate, not an installed SDK or CoreShared test.

The pin is an observed local source identity, not a claim about current remote
`main` or `dev`. Launcher is optional background at its own exact revision.
Schema conformance does not qualify a live Setup integration, grant lifecycle
authority, ratify DiskEd's license, or authenticate a publisher.
