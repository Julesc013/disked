# Private raw-layout comparison over generated images

Clean source `4400cb7119f36a9159b647e809e1fa76f766167f` passes 109 native raw-layout processes and 1342
assertions per x64/x86 binary (218 processes/2684 assertions combined).
The two existing injected query campaigns also pass: 472 processes and
7052 assertions across all six campaigns. Tooling: 215 run, 213 passed,
2 skipped; 1057 structural checks. All 461 selected source inputs match
exact Git/checkout bytes; source-map/index/context/manifest checks pass.
Tested host: non-elevated BLACKGLASS-WIN1\Jules, Windows 10 Enterprise
19045 x64. x86 binaries ran on this x64 host, not a qualified x86 host
or historical Windows platform.

Runtime capture parses supplied immutable image bytes using the portable
MBR/EBR/GPT implementations. The Windows provider compares a separately
injected IdentityLayout /2 frame. There is no shipped-product link.
Both GPT copies must agree; complete EBR topology, format/capacity/logical
units and unique partition extents/common metadata remain explicit.
Full 36-unit name representations are preserved. More than eight rows,
64 active records, long EBR chains and 4096-byte units are exercised.
Corruption, missing coverage, duplicates, contradictions, exact content/
subject/capture binding failures and exhausted budgets cannot become
an agreement by truncation. Unknown CHS geometry and source consistency,
metadata coverage and source-prefix completeness are separate properties.

The result is a caller-declared fixture pairing, not authenticated owned
reader provenance, physical association, acquisition consistency or media
identity. Original frame claims remain immutable. No physical access,
provider/product/public admission, owner acceptance, storage mutation or
full-unit/release qualification is claimed.

All 404 product inputs equal the dev.40 source `3f648127`. Its prior
77-group result remains at that original revision, with no new product
build or suite rerun. See the retained product reuse proof and the linked
[earlier evidence](../2026-10-10-source-layout/README.md).

Reproduce using the selected Windows toolchain and repository Python:

```text
.aide-local/venv/Scripts/python.exe .aide/evidence/2026-10-10-raw-layout/reproduce.py --source-revision 4400cb7119f36a9159b647e809e1fa76f766167f --output .aide-local/raw-layout-reproduction
```

Use a new output directory. The runner records MSVC 19.44/v143
14.44.35207, SDK 10.0.19041.0, C90/C++14, static CRT, native build commands,
actual processes, PE headers/imports/dependents, image recipes/byte hashes,
source identities and unmodified results. Ordinary generated images and
PE binaries remain outside Git; Python recipes are bound to exact source.
Large receipts are lossless gzip with decoded hashes in compression-map.
The receipt-local Git attributes preserve exact observed bytes; the first
index audit caught JSON line-ending normalization before the retention commit.
Initial diagnostics retain the compiler failure (string-address comparison)
and malformed test name (36 nonzero units without a terminator). The
implementation was repaired and the invalid name remains a rejection case.
Those preliminary runs were uncommitted and do not replace clean-source evidence.

Qualify IdentityLayout /2 observations in the existing cached frontend models, then bind the raw comparison to owned image-reader and storage-frame provenance. Preserve separate composite physical identity, live/provider/product/public/platform and owner/storage/release gates; all specified platforms/storage 0.1.0 remains active.
