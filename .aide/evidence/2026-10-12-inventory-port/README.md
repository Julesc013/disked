# DE-W030 mixed native inventory port

Qualified source: `2e2f1fb84a21c7f0d92d51e72e8d89e33880ce61`. Partial private implementation and implementing
worker review only; owner/full-unit/provider/public/product admission remain open.

- [Review](REVIEW.md)
- [Actual validation summary](validation-summary.json)
- [Exact byte inventory](inventory.json)
- [Lossless compression bindings](compression-map.json)
- [Clean source-bound recipe](reproduce.py)
- [Retention auditor](audit_retention.py)

28 x64/Win32 campaigns: 2390 controller/readers and85412 assertions;
new inventory port23/88/7503 per architecture. Fresh x64 dev.41 build/launch/imports
and 77 product groups; 213 tooling passes/2 skips and
1071 structural checks. 482 exact source/blob inputs, 32 local PE artifacts.

```text
python .aide/evidence/2026-10-12-inventory-port/reproduce.py --source-revision 2e2f1fb84a21c7f0d92d51e72e8d89e33880ce61 --output .aide-local/inventory-port-reproduction
python .aide/evidence/2026-10-12-inventory-port/audit_retention.py
```

Use the recorded toolchain/Python environment. A retained snapshot is frozen
observation data; it is not current media identity, a durable resolver or a
storage grant. The full 0.1.0 programme remains active and incomplete.
