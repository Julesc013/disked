# DE-W021 bounded MBR/EBR readers

Source `7c8466877f1caab46747d73afbbcaf29f6720955`, base `a0d4fac3f71bef0cc1a20e6f2fdf0d2b87a7814b`. The private C90 reader library is built from
immutable views and DE-W020 checked values/extents. It performs no I/O, allocation,
callbacks, mounting or writes. Its caller supplies a named block space and keeps
all input bytes/workspace alive. The fake product remains DiskEd 0.1.0-dev.16;
`table.verify` and real image providers remain unavailable.

The MBR reader preserves the full block, decodes explicit little-endian records,
checks primary extents/overlaps, diagnoses protective/hybrid records, and compares
CHS only with supplied geometry. The EBR reader uses a caller-selected container,
the common two-entry profile, the two different relative-address bases, a visited
set and an absolute 1..128-node budget. It retains incomplete observations and
separates traversal completion from layout correctness. Historical slot/base
variants are reported as unsupported, not silently rewritten.

All 35 native CTest groups pass in a clean local clone. Each of three compiler
lanes (strict-C90 GCC x64, MSVC 2017 x86, MSVC 2022 x64) passes 1296 synthetic cases
and the real memory-protection test. A C++ caller links the C implementation,
preserves read-only pages and checks all 512 truncated boundaries plus oversized
refusal/state preservation. The corpus covers u32 endpoint widening, device ends,
both EBR bases, cycles, the 128-node bound, primary/logical/metadata overlaps,
truncation/unavailability, protective/hybrid/CHS records, non-512 units and opaque
byte retention. Generated absolute-coordinate layouts and seeded mutations are
distinct from an external differential-parser run, which remains not_run.

The specification suite runs 171 tests: 169 pass and two existing Windows
symlink-privilege cases skip. Structural/manifest and strict producer checks pass;
passive AIDE validation covers 36 records at the unchanged pin. Live AIDE is
not_run. Exact commands, compiler/linker/input identities, imports, host details,
launch output and failures/corrections are retained. See FINDINGS.md for the GCC
formatting warning, combined-overlap regression and hybrid-classification correction; expectations were not
weakened. Native artifact identities are in `reproduction-7c846687/clean-results.json`;
local binaries/libraries are under `.aide-local/artifacts/DE-W021-7c846687/`.

This is local implementation completion with implementing-agent review, not owner
acceptance or independent safety review. Canonical status remains needs_review.
Only this modern Windows host was exercised; x86 runs under WOW64. No historical
loader, real storage, production recovery, privilege, installation, signing or
release qualification is claimed. The whole 0.1.0 goal remains active.

Continue DE-W022 independent primary/backup GPT observations against pinned UEFI 2.10, defining the bounded header/entry-array contract before implementing it. Preserve competing valid candidates, exact GUID/UTF-16 bytes, checked endpoints and the specified CRC. DE-W023 external differential/fuzz campaigns and DE-W024 coherent image-provider/frontend integration remain separate. No physical access, mounting, privilege or writer authority; owner acceptance and full 0.1.0 qualification remain open.
