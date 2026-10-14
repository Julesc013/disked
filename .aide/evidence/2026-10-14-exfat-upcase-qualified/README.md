# Exact-source exFAT upcase qualification

Clean source `e43f00fb494cd12727fc52fcf82cb040a85cde2c` passes 244 independent
scenarios in nine methods, 9,503,025 mapping-unit comparisons and 263 name pairs.
All 15 selected native regression groups and one private header compilation pass,
along with strict C90, PE/import, build-boundary, context and source-hash checks.
The immutable checkout runs 242 tooling tests with two skips and no failures.

Commands, logs, exact inputs, artifact hashes and four acceptance mappings are
retained here. `reproduce.py` records the executed runner and its original paths;
use a new output directory when reproducing. It refuses an existing output path.
The complete 130-group native suite at `1e938369` is prior evidence, not a fresh
full-suite result for this revision. The source delta is recorded explicitly.

This qualifies a private supplied-byte algorithm. Root/cardinality, active FAT,
bitmap/upcase chains, source/capture binding, namespace/tree/content and native
provider integration remain. Owner acceptance, other platforms, physical writers
and the original full 0.1.0 release are separate and unfinished.
