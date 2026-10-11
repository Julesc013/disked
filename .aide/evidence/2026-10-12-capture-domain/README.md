# DE-W030 coordinator-local capture epoch domains

Verified source: `f1edd134cccfe08d1393c72e2c1354b0e5d11458`. Final evaluation uses a checked clean task clone,
with a verified local origin/path before exact checkout. Commands, source/blob/
byte bindings, build configuration, launch/import observations, receipts and
hashes are retained. Large receipts use lossless gzip with decoded hashes and
lengths. Images are reconstructed from pinned recipes and hashed manifests.
The inventory binds 26 local PE copies; binaries and images are outside Git.

```text
python .aide/evidence/2026-10-12-capture-domain/reproduce.py --source-revision f1edd134cccfe08d1393c72e2c1354b0e5d11458 --output .aide-local/capture-domain-reproduction
python .aide/evidence/2026-10-12-capture-domain/audit_retention.py
```

Use the recorded Windows compiler/SDK/Python dependencies. Read `REVIEW.md` and
`validation-summary.json` for applicability. This run rebuilds/launches dev.41
and reruns all 77 product groups; the reducer's 25 tests are retained from that
same run. Twenty-two x64/x86 private campaigns pass. Full unit, owner acceptance,
physical/provider/public/reconnect admission and the entire all-platform/storage
goal remain incomplete. Source dev/main synchronization does not publish a release.
