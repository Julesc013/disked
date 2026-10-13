# Held-file FAT tree worker qualification

Exact clean source `54376be566024e04e1438a3f68fbd4c4646e34a4`, base `7bfa795f341f9fc8681855789a55c9235e731fab`. The recorded Windows lane passes
**111 native groups**, **24 selected standalone headers**, **232 tooling tests**
and **2 skips**. Nine methods cover **57 actual cases** using generated
ordinary FAT12/16/32 files and normal/fault child processes. Aggregate publication
reaches **12351932 bytes**, across up to **138 pages**, using one
**2 MiB slot**. The full large tree retains 17,601 entries; source byte hashes stay
unchanged. Nonzero/conflicting copies and cross-page long names are exercised.

One read-only source handle and ancestor closure remain held across pages.
Native metadata checks and double reads produce separate recorded observations.
Parent replay reconstructs pages from exact regions/checks; only the actual owned
process/code/request/epoch session constructs retained pages. Immutable first
pages survive later processing, cancellation and retirement. Write sharing is
denied while held. Cancel/hang/late and pre/post-spawn tests retain actual
ownership, with retirement established by process exit.

Changed page/region/check/source/process/epoch/digest and final reply claims refuse
without inventing valid pages or current authority. Normal binaries reject test
controls. The page adapter reuses ObservationWorker; no scheduler, raised host
budget, source write, mount or output-file creation is added. Windows read/write
mapping semantics follow [Microsoft's API contract](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-mapviewoffile).

Commands, logs, source/Git blob bindings, context, build/header/import/toolchain
observations and artifact hashes are retained. Reproduce at the frozen source
with a fresh output directory. Audit retention without rerunning native tests.
Source and integration revisions are separate. GCC is syntax only.

The [failed candidate](failed-8548b1f2/README.md) retains 107 of 111 passes and four
failures, plus subsequent diagnostics. Corrected probe parent memory admission
preserves the existing 256 MiB parent and 128 MiB child bounds. A finite progressing
copy wait uses the established 90s total/30s no-progress policy; it does not treat
timeout as quiescence, replace a writer or weaken outcome/byte/exit checks.

These are prototype read observations, not atomic snapshots, authentication of
imported frames, future source access or storage health. Public tree operations,
recursive destination metadata effects, other hosts/formats, physical/production
recovery, owner acceptance and the full all-platform/storage 0.1.0 remain work.
