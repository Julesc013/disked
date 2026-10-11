# Native screen delivery and callback teardown evidence

Qualified source `b42c23fdebddcff7ba65f5179bb61e3848eaf40b`. Private partial DE-W030 implementation; implementer
review only. Full all-platform/storage DiskEd 0.1.0 remains active.

- [Actual validation](validation-summary.json)
- [Review and limitations](REVIEW.md)
- [Exact retained bytes](inventory.json)
- [Lossless compression bindings](compression-map.json)
- [Clean build/test recipe](reproduce.py)
- [Read-only retention/source auditor](audit_retention.py)

Per architecture: 62 controllers/113 owned readers, 34 inert refusals and 28 actual
hosts. Two campaigns: 350 processes/9190 assertions. Actual screen
TUI updates and GUI/linear/screen TUI/shell callback failures preserve old reviews,
native owners, error4/unavailable final sample, separate retirement and restoration.
Fresh same-source dev.41 x64 build/launch/imports, 77 serial product groups,
213 tooling passes/2 skips and 1075 structural
checks. Four PE copies stay in .aide-local/artifacts; no release published.

```text
python .aide/evidence/2026-10-12-inventory-host/reproduce.py --source-revision b42c23fdebddcff7ba65f5179bb61e3848eaf40b --output .aide-local/inventory-host-reproduction
python .aide/evidence/2026-10-12-inventory-host/audit_retention.py
```

Use the recorded compiler/SDK/Python environment. `--historical` audits the exact
Git source without asserting that current working inputs still match it. Native
PE copies must be available locally; historical evidence alone does not qualify
the latest tree. The earlier parallel joined-report failure remains unresolved.
Normal screen-shell active updates and actual concurrent asynchronous operation
completion are not newly qualified. All owner/live/physical/provider/public/product/
other-host/accessibility/writer/recovery/storage/release admission stays separate.
