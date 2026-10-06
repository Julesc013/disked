# DE-W020 portable arithmetic and extents

Source `aaac4d4fc712d3c03d2a9960e949a13a5c83995e`, base `6e49cf3b19a6f4b91ceea767e5bcd35412e497f9`. The clean source produces the shared internal
C90 library, its C and C++ callers, and the existing fake-only native DiskEd
0.1.0-dev.15 composition. The executable is `.aide-local/artifacts/DE-W020-aaac4d4f/disked.exe`,
916992 bytes, `sha256:032c58f2cccdc744cbf0045a33e4b279b3c7d01ded7f48d301ed748f011c02f2`. Library and probe artifacts are
also retained under `.aide-local/artifacts/DE-W020-aaac4d4f/`.

The core uses four 16-bit limbs with checked 32-bit intermediates, reusing the
DE-W018 implementation. It adds comparison, subtraction, multiplication,
division/remainder and exact target-size conversion. Bounded borrowed views
validate ranges before pointer arithmetic; explicit 1/2/4/8-byte endian access
supports unaligned data and refuses truncation or width loss before any write.
Immutable named block spaces bind nonempty half-open extents, exact logical units,
inclusive endpoint conversion, overlap/containment and checked byte projection.
Equal names do not merge separately owned spaces. A pointer is an internal borrow,
never serialized identity or storage authority.

All 33 native CTest groups pass in a clean local clone, preserving the earlier
fake-provider/frontend/worker containment checks. The portable oracle passes
10334 cases in each of three separate compiler builds: strict-C90 GCC x64,
MSVC 2022 x64 and MSVC 2017 x86. The same arithmetic and byte rules hold while
native-size refusal follows actual 32/64-bit size_t. A C++ caller links the C
library and tests actual read-only/no-access page boundaries. The original
411-case DE-W018 control still passes against the same implementation.

The specification suite runs 171 tests: 169 pass and two existing Windows
symlink-privilege cases skip. Structural/manifest checks and strict producer
response/operation checks pass. Passive AIDE validation covers 36 records at
the unchanged pin; live AIDE remains not_run. Exact commands, build-input hashes,
compiler/SDK/runtime/host declarations, PE headers/imports, test logs and
case observations are retained in `working/` and `reproduction-aaac4d4f/`.
Raw logs retain their original whitespace. Initial findings are recorded separately.

This is local DE-W020 development completion under the continuation grant;
canonical status remains needs_review and owner acceptance is pending. The C
interface is private, with caller-owned object/lifetime preconditions, not a
frozen public SDK or hostile-pointer API. It allocates nothing and performs no
I/O. No real-storage command was added to the fake executable. The pure block
coordinate model is distinct from the stricter JSON extent producer, which also
requires successful byte projection. No partial block is silently rounded.

Only this modern Windows host was exercised; x86 runs under its WOW64 environment.
Historical 16-bit-int builds, real legacy loaders/terminals, other hosts, physical
media, production journals/recovery, privilege, installation, signing and release
qualification remain open. DE-W018 and the full 0.1.0 programme are not complete.

Continue DE-W021 bounded read-only MBR/EBR parsing over ordinary synthetic image fixtures, using the reviewed portable core. Pin actual format references and define diagnostic/resource limits before implementation; preserve opaque bytes and distinguish current-EBR from container-relative links. DE-W018 historical compiler/launch gaps remain open independently. No mounting, physical access, privilege or writer authority is implied; owner acceptance and full 0.1.0 qualification remain separate.
