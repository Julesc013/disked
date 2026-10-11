# Active native inventory frontend evidence

Primary product source `6e4c20591afb31389b95afe91dfc4037cde2a4e4`; private port fixture source `8cf67f0db2b3d0a507f1ce578dded86f3a1272f9`.
Per-artifact and per-campaign identities are recorded; all 404 production inputs
are unchanged by the fixture correction. Partial private DE-W030 implementation; implementer
review only. The full all-platform/storage DiskEd 0.1.0 programme remains active.

- [Actual validation](validation-summary.json)
- [Review, initial diagnostics and limitations](REVIEW.md)
- [Exact retained byte inventory](inventory.json)
- [Lossless compression bindings](compression-map.json)
- [Clean exact-source recipe](reproduce.py)
- [Read-only retention auditor](audit_retention.py)

Eight x64/Win32 campaigns: 808 controller/readers and 37960
assertions. New advancement campaign: 50 controllers/81 readers per architecture,
20 actual hosts plus 30 inert refusals. Fresh dev.41 x64 build/launch/imports,
77 native product groups, 213 tooling passes/2 skips,
1075 structural checks and 493 source/blob inputs. Ten PE copies stay
under .aide-local/artifacts; no release published. Larger retained files are
lossless gzip; console receipts/control observations and GUI captures remain.

```text
python .aide/evidence/2026-10-12-inventory-advance/reproduce.py --source-revision 8cf67f0db2b3d0a507f1ce578dded86f3a1272f9 --output .aide-local/inventory-advance-reproduction
python .aide/evidence/2026-10-12-inventory-advance/audit_retention.py
```

Use the recorded toolchain/environment. Actual injected reader advancement does
not qualify live storage, production provider/public/product admission, other
hosts/platforms, accessibility, owner/full-unit or release/storage privileges.
The command above reproduces the current corrected tree. It builds new binaries
whose identities will differ from the retained primary-source binaries. The retained
continuation scripts record the actual two-source qualification. Original parallel
joined-report and pre-correction Win32 fixture failures remain retained and discussed
in the review; the joined-report exit-delay cause remains unestablished.
