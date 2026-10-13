# FAT allocation continuation qualification

Clean native source `112aa1e980861c050f66fef8d9ea9000658e4cc8`, base `83edbe735784accc7784bf528d210210cc66c4d6`. The recorded Windows lane passes
**109 native groups**, **20 selected standalone headers**, and
**232 tooling tests** with **2 skips**.
Five independent test methods cover 188 supplied-byte cases, including chains to
33,000 clusters, page-size invariance and cycles spanning pages. Native protected
cells/workspaces check exact/short input, untouched error state and workspace tails.

The cursor uses the existing portable FAT owner and entry decoder. It performs
no I/O, allocates no storage, and retains an explicit caller-owned bitmap. No
whole-chain step cap is imposed; memory/addressability and scheduling budgets
remain the caller's responsibility. A paired cursor/bitmap is private process
state, not a serialized/source token. Old capture/selector/chain formats remain.

Commands, logs, exact Git blobs, build configuration, toolchain, product launch,
imports, executable hashes and source-bound context are retained. GCC is syntax
only; this does not qualify GCC runtime, historical hosts, recursive extraction,
physical operations, owner acceptance or full 0.1.0. Reproduce at the source
revision with a fresh output directory. The retention audit verifies history
without rerunning native tests. Source and integration revisions are distinct.
