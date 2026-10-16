# Supplied NTFS uppercase table and name comparison

DE-W099 adds a private prerequisite for NTFS namespace and lookup work. Its
[execution contract](../spec/catalog/ntfs-upcase-prototype.json) specifies expected
behaviour before implementation evaluation. It changes no command or public ABI.

The complete table envelope contains 65,536 little-endian unsigned words. It is
borrowed through 256 separate 512-byte page views. This avoids requiring one
128 KiB C object or a large `size_t`, while retaining exact original bytes. A
successful envelope check does not establish the table's source or correctness.

Mapping uses every supplied entry, including ASCII, exactly once. Comparison
returns independent raw and mapped UTF-16 code-unit orders. Zero, controls and
unpaired surrogates stay data; there is no host locale, normalization, expansion
or recursive mapping. Mapped equality does not establish namespace uniqueness or
resolve DOS aliases. The eventual index policy must choose any raw tie-break
explicitly; this helper does not silently choose it.

`portable/ntfs/upcase.c` belongs beside the existing NTFS byte decoders. It has no
file handle, allocator, native source opener or frontend dependency. Its private
declarations remain in `ntfs.h`; no new directory or generic text framework is
needed. The independent fixtures and guard probe belong under existing test
owners. See [source-map.md](source-map.md) for each current file's responsibility.

Before actual lookup, collect FILE 10's unnamed data through the existing MFT and
stream closure, bind the exact table to its volume/capture and define namespace,
ordering and alias policy. That work remains required, alongside all originally
specified platforms and storage operations. A modern private probe does not
qualify a historical compiler or installed filesystem provider.

The [reference record](../.aide/evidence/2026-10-17-ntfs-upcase/references.json)
distinguishes format references from adopted dependencies. No upstream
implementation is copied, compiled or executed.

The [agent review](../.aide/evidence/2026-10-17-ntfs-upcase/REVIEW.md) links exact
source and successful selected x64/Win32 results, retained activation failure and
unverified platforms/capabilities. This is source review, not owner acceptance.
