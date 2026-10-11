# DE-W030 composite reported identity and epoch comparison

Verified source: `8ca6053d038928dc83ad1a6115b0df27fb403ba8`. Final evaluation uses a clean task clone, with its
local origin/path/cleanliness checked before checkout. Commands, original
diagnostic attempts, exact source/blob/byte bindings, build configuration,
launch/import observations, test receipts and hashes are retained. Large
receipts use lossless gzip; `compression-map.json` binds their original bytes.
Generated images are reconstructed from pinned recipes and hashed manifests.
The inventory identifies 23 local PE copies; binaries and images are outside Git.

Reproduce on Windows with the recorded compiler/SDK and Python dependencies:

```text
python .aide/evidence/2026-10-12-composite-identity/reproduce.py --source-revision 8ca6053d038928dc83ad1a6115b0df27fb403ba8 --output .aide-local/composite-identity-reproduction
python .aide/evidence/2026-10-12-composite-identity/audit_retention.py
```

Read `REVIEW.md` and `validation-summary.json` for applicability. This run
rebuilds/launches dev.41 and reruns all 77 product groups because a bound
specification changed. Twenty private x64/x86 reader campaigns pass.
Full unit, owner acceptance, physical/provider/public admission and the entire
all-platform/storage goal remain incomplete. Source synchronization to dev/main
does not publish a release.
