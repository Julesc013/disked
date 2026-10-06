# DE-W018 modern primitive controls

Source `cca910c16635e1fe3cf9ff2729c006150100d258`, base `635e846705cb1870608fecf292587bf25e997973`. Three clean builds each pass the same 411
independent arithmetic/representation/text cases on the current Windows host:

- gcc-x64: ok char=8 short=16 int=32 long=32 pointer=64 intermediate=32; `sha256:a4ad30da01bff68ebf11c99607e98417c692ad693199ef7c6b8f3ccc8dc0e847`.
- msvc2022-x64: ok char=8 short=16 int=32 long=32 pointer=64 intermediate=32; `sha256:27ea1eb43c786fcfd2e574595dc2b9a3020f0dc7ba54f277fc5685fbb163da89`.
- msvc2017-x86: ok char=8 short=16 int=32 long=32 pointer=32 intermediate=32; `sha256:f324dd809133badb6832c8b67363f32b653e3cd896f5567abf39f46ae0f31d5d`.

Commands, compiler/linker paths and hashes, explicit SDK include/library paths,
source hashes, imports, PE headers and line-ending-normalized stdout/exit observations are retained
in `reproduction-cca910c1/`. Executables are retained in
`.aide-local/artifacts/DE-W018-cca910c1/`. GCC's strict C90 mode checks the
shared source; MSVC 2022 x64 and MSVC 2017 x86 supply independent compiler/ABI
controls. x86 execution here is on the same modern x64 Windows host, not XP/9x.

Four 16-bit limbs represent exact u64 values without a native 64-bit type.
Checked decimal parsing/formatting, addition, u32 narrowing, explicit eight-byte
little-endian serialization and inert byte display preserve caller outputs on
failure. The independent Python integer oracle covers boundary and seeded random
values; the native sentinel checks exercise buffer capacities and aliased addition.
All 256 byte values are displayed without emitting their control sequences.
The private C call contract excludes null pointers and in-place text/wire conversion.
No SDK ABI or DiskEd product command was admitted, and the product executable
does not link these probes yet.

The final specification suite runs 171 tests: 169 pass and two existing Windows
symlink-privilege cases skip. All 904 structural checks and the manifest pass.
Passive AIDE validation covers 36 records at the unchanged pin; live AIDE was not
run. The earlier native product evidence remains the 31-group watch reproduction.
This isolated probe addition does not claim a fresh run of that product suite.

Initial errors are retained: the MSVC cross-host DLL search failed, and four
context-fixture tests outgrew their prior byte allowance. The installed native
x86 compiler fixed the first without installation; a larger valid-fixture budget
fixed the latter while preserving all integrity and no-truncation assertions.
Raw compiler logs retain their original trailing whitespace and blank lines.

Read-only inventory found registered Windows 3.1 and Windows 98 VMs. No guest was
booted, inspected, mounted or changed. Their names and paths do not prove usable
installed systems. The four historical lanes, actual 16-bit-int compilation,
8086 instruction audit, historical loaders/terminals/keyboards/code pages and the
DiskEd parser remain not_run. No physical storage, elevation, installation,
signing, publication or owner acceptance occurred. DE-W018 and 0.1.0 remain open.

Continue DE-W018 period-tool/guest investigation and harmless legacy loader probes where the installed environment permits. Actual 8086/Win16/Win9x/OS2 compilation and launch remain unverified; do not use named VMs or modern compiler success as qualification. Preserve the portable corpus for later target admission. If a historical lane needs unavailable tools or separate installation/guest authority, retain that scoped blocker and continue independent DE-W020 image work under the programme grant. Owner acceptance and release/storage gates stay separate.
