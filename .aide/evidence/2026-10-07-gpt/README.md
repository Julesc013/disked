# DE-W022 independent GPT readers

Source `ad88098941dcad2e1b4056d892a324c59683edaa`, base `3ac97606aaf058e2c66430ea2f9a97bc1b5096cf`. The private C90 library interprets caller-owned
immutable header/array blocks and checked named-space coordinates. It performs no
I/O, allocation, callbacks, mounting or writes. DiskEd remains the fake-only native
0.1.0-dev.17 composition; no real image provider or `table.verify` command is admitted.

The reader validates primary and backup headers independently at their fixed
locations, bounds the advertised array before access, and separates header
findings, complete array coverage and entry consistency. CRC spans exclude array
padding and logically zero the header CRC field without modifying input. GUID
byte order, original UTF-16 names, attributes, inclusive endpoints, duplicate IDs,
overlaps and opaque/reserved bytes retain explicit treatment. Caller limits bound
entries, widths and array bytes; budget refusal does not declare corrupt media.

Comparison retains both candidates and returns agreement, disagreement or
incomparable. It compares every advertised array byte as well as semantic header
fields, excluding expected location differences. No copy is automatically selected
or repaired. A constructed pair with identical CRCs and different valid bytes is
correctly reported as disagreement. Equal bytes with different entry shapes also
remain distinct observations.

All 37 native CTest groups pass from a clean local clone. Each of three compiler
lanes (strict-C90 GCC x64, MSVC 2017 x86, MSVC 2022 x64) passes 1022 independently
constructed GPT/encoding cases and the native memory-protection probe. All case
input/output hashes also agree with the native CMake build. The corpus uses Python
zlib, UUID and UTF-16 codecs as encoding oracles, generated layouts, seeded
malformed mutations, maximum active-entry workspace, exact resource refusals and
non-512 units. Actual read-only/no-access pages cover exact/truncated headers and
arrays, oversized refusal, and budget/workspace refusal before inaccessible data.
The shared compiler runner still passed its earlier 1296-case MBR regression.

The specification suite runs 171 tests: 169 pass and two existing Windows
symlink-privilege cases skip. Structural/manifest and strict producer checks pass;
passive AIDE validation covers 36 records at the unchanged pin, live AIDE not_run.
Exact commands, compiler/linker/input hashes, imports, host and launch results are
retained. FINDINGS.md records the initial fixture-alias failure and correction;
expected results were unchanged. This corpus is not a run of an external partition
parser or a coverage-guided fuzz campaign; those remain DE-W023.

Artifacts are under `.aide-local/artifacts/DE-W022-ad880989/`; their exact sizes
and hashes are in `reproduction-ad880989/clean-results.json`. No owner acceptance
or independent storage safety review is manufactured. Canonical status remains
needs_review; implementing-agent review permits local continuation under the
explicit grant. Only this modern Windows host was exercised, with x86 under WOW64.
Historical/small-memory profiles, source-consistent image integration, real media,
production recovery, privilege, installation, signing and release remain open.
The whole DiskEd 0.1.0 goal remains active.

Continue DE-W023 reproducible differential corpus and parser fault campaigns for the native MBR/EBR/GPT readers. Inventory available external oracles, pin their exact identities, define adapters over disposable synthetic fixtures and retain disagreements without voting them away. DE-W024 coherent raw-image capture and frontend integration remains separate. Preserve historical/source-consistency, owner acceptance and writer/recovery gates; no physical media, mounting, elevation, installation or release authority is implied.
