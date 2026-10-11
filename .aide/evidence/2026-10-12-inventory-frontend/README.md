# Actual cached native inventory renderer evidence

Qualified source: `a72454e9bfc2aecb8d576b4bd8a8cbbc9279381d`. Partial private implementation and implementing
worker review; owner/full-unit/provider/public/product admission remain open.

- [Review and limitations](REVIEW.md)
- [Actual validation summary](validation-summary.json)
- [Exact byte inventory](inventory.json)
- [Lossless compression bindings](compression-map.json)
- [Clean source-bound recipe](reproduce.py)
- [Retention auditor](audit_retention.py)

Six x64/Win32 campaigns: 546 controller/readers, 31208 assertions.
New actual renderer campaign: 59/36/916 per architecture, including 15 native
GUI/TUI/shell cases and 44 launcher rejections. Fresh dev.41 x64 build/launch/imports
and 77 product groups; 213 tooling passes/2 skips,
1073 structural checks. 486 exact source/blob inputs, eight local PEs.

```text
python .aide/evidence/2026-10-12-inventory-frontend/reproduce.py --source-revision a72454e9bfc2aecb8d576b4bd8a8cbbc9279381d --output .aide-local/inventory-frontend-reproduction
python .aide/evidence/2026-10-12-inventory-frontend/audit_retention.py
```

Use the recorded toolchain and Python environment. Screenshots, console controls,
complete receipts and original bytes are retained; larger files use lossless
gzip. PEs stay under .aide-local/artifacts, outside Git and release publication.
This composition renders frozen observation data, without fresh-media authority.
The full all-platform/storage 0.1.0 goal remains active and incomplete.
