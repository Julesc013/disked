# Supplementary tree review corpus

The full143 exact-source campaign at bf26a4a4 remains running. The supplementary
corpus is prepared and not yet executed. It uses independent existing generated
image/NameHash builders to check custom volume mappings, surrogate/original units,
different names sharing NameHash, invalid stream geometry, timestamp separation,
invalid API limits, directory self-reference and inactive-bitmap aliasing.

Run only after the isolated full campaign completes:

```text
.aide-local/venv/Scripts/python.exe .aide/evidence/2026-10-15-exfat-tree/review-cases.py --source .aide-local/exfat-tree-exact-bf26a4a4/source --probe .aide-local/exfat-tree-exact-bf26a4a4/build/Release/exfat_tree_probe.exe --output .aide-local/exfat-tree-exact-bf26a4a4/review-cases.json
```

No result, new product admission or owner acceptance is inferred from this corpus.
