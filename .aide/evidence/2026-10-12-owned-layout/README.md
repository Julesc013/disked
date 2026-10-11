# DE-W030 owned ordinary-image/layout provenance

Verified source: `c30b68343bbd2a1d073d0c661dc6705a9e885c48`. Final evaluation uses a clean task clone,
with its origin/path/cleanliness checked before checkout. Actual commands,
original diagnostic attempts, exact source/blob/byte bindings, build settings,
import observations, test receipts and hashes are retained. Large receipts use
lossless gzip; `compression-map.json` records original hashes and lengths.
Generated image bytes are reconstructed from pinned test recipes and their
independently hashed manifests. Eighteen local PE copies are identified by
`inventory.json`; binaries and images are outside Git.

Reproduce from Windows with the recorded compiler/SDK and Python dependencies:

```text
python .aide/evidence/2026-10-12-owned-layout/reproduce.py --source-revision c30b68343bbd2a1d073d0c661dc6705a9e885c48 --output .aide-local/owned-layout-reproduction
python .aide/evidence/2026-10-12-owned-layout/audit_retention.py
```

Read `REVIEW.md` and `validation-summary.json` for applicability and limitations.
Product dev41 evidence is reused through all 404 exact unchanged inputs; the
product was not rebuilt or rerun for this slice. Full unit, owner acceptance,
physical/provider/public admission and the all-platform/storage goal remain
incomplete. Source-only dev/main synchronization does not publish a release.
