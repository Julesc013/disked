# Exact source transport

The first real-repository trial used source `5a66bed951bda0a7e263730b47580cc6ae629328`:
931 selected files, 12,303,264 content bytes and a 3,873,896-byte pack. Export
succeeded; materialization failed the exact `.gitignore` byte check because
Windows used native CRLF for `text=auto`. The initial attempt's raw diagnostic
was lost with its disposable workspace; the diagnostic retry is retained in
`result.json` and its verified compressed input manifest. Neither attempt was
reported as qualified. Both generated packs/checkouts were removed.

The reusable implementation is now `tools/source-snapshot.py`; the earlier
dated helper and its seven-fixture evidence remain unchanged. The canonical
helper explicitly selects `core.eol=lf` as well as `core.autocrlf=false`, and its
fixture includes the real `.gitignore`/`text=auto` case. It batches selected blob
reads to avoid launching one Git process per input. It still checks every exact
object identity/length/content hash and keeps the same admission bounds.

All 113 tooling tests pass, with one expected skip. The fresh full-repository
transport check passed at `de8cd70440fb0d97844feafe1356da9e6d41c7ce`:
931 files/12,303,264 content bytes, 3,251 exact Git objects and a 3,873,415-byte
pack. The materialized checkout reported the exact source revision and clean Git
state; every selected file matched its original Git blob bytes and SHA-256.
`qualification.json` and `qualified-manifest.json.xz` retain those observations.
The managed run peaked at 31,305,723 disposable bytes and removed its workspace,
pack and checkout. This is bounded host
Git/source metadata validation, needed before guest transfer; it mounts no media
and runs no DiskEd product or privileged process.

`tooling-observations.json.xz` preserves the full tooling log exactly once; the
readable receipt retains counts and source hashes. Both source manifests retain
their distinct reviewed Git revisions, so the earlier refusal remains history.
Actual guest snapshot materialization, pinned CMake File API configure and the
eighteen-group private Win32 build/tests remain the next execution step. All
original product/platform/storage/owner/release criteria remain open as recorded.
