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

All 113 tooling tests pass, with one expected skip. A fresh full-repository
transport check follows from a clean committed checkpoint. This is bounded host
Git/source metadata validation, needed before guest transfer; it mounts no media
and runs no DiskEd product or privileged process.
