# Implementing-agent review: held ordinary-file NTFS directories

DE-W091; base `ea25e8aad23b555aef870d82054acaebc4c9eea5`. Exact tested native source `4156accfa906943ad14e61061954b01c48e08207`.
The retained grant permits local implementation/test/repair across agent-reviewed
units and dev/main synchronization. Owner acceptance, independent safety review,
physical/elevation/customer/install/signing/publication authority remain separate.

The existing `ntfs_file.h/.cpp` now supplies a private directory request/API using
the same pinned ancestors, read-only held file, source metadata, immutable request
and callback copies, native response retention and process sequence. Directory
meaning remains in the existing runtime collector/portable decoders. No new
production file, library, opener, parser, scheduler or source hierarchy is added.
The 317 source files retain their ownership and maximum 62-character source path.
Default bootstrap output, schema, domain and native-read order are unchanged.

Automatic 3.0 does not relabel a 3.1 refusal or repeat native bootstrap reads. It
first replays only the retained prefix under 3.0, stops deliberately at its first
new read and compares the explicit common facts after normalizing only the
profile-match boolean. Strict response/provenance checks reject corruption before
new I/O. A validated prefix may be reused in the 3.0 collector before the same
native reader acquires the suffix and final rereads. Its actual native trace and
read/retention quotas equal explicit 3.0. Legitimate pre-directory refusals need
no suffix. Unknown versions and other bootstrap failures never trigger selection.
After collection, native metadata checks, full pure replay and final checks stay
distinct. Profile/prefix/final replay facts and their hashes identify each phase.
All returned data owns its lifetime; no observation grants future source effects.

The independent corpus passes 550 native responses in 12 methods and five pure
report reconstructions: both versions/profiles, old/new headers, root/empty/deep
and fragmented/list/bitmap layouts, full references/raw names, exact limits,
every native/prefix/final replay fault, immutable controls, source/path/ancestor
exclusion and release. Actual ordinary-file reads above 4GiB and complete before/
after file hashes are retained. Probe, prefix-validation and foundation hashes
are independently reconstructed through guarded supplied-reader probes. The
actual leaf-file symlink fixture remains unverified for absent privilege.

The clean Windows x64 Release campaign builds every product/test target and
passes 31 explicitly selected affected groups of 161 registered,63 standalone
C++ headers, nine NTFS C sources/two C headers under strict GCC C90, eight
PE/import observations and 244 tooling tests(two known symlink skips). All
1094 registered/build input hashes stay unchanged and
the checkout stays clean. This is selected current regression qualification,
not a claim that all 161 current native groups ran. The preceding full 160-group
campaign remains evidence for its earlier 7bb6153a source only.
[Current campaign](qualified-4156accf/summary.json).

An isolated Win32/WOW64 codemodel-derived fixture passes six groups: 550 directory-
file, 79 existing file, 155 bootstrap, 227 supplied-directory, 298 stream and 134
closure cases. Four standalone headers, separate normal/fault provider variants,
four probe PE/import checks and actual above 4GiB reads/source hashes pass.
[Supplement](win32-4156accf/summary.json). This is private probe qualification on
the recorded host, not the full Win32 product or historical-host qualification.

Two working failures were fixture-builder duplicate keyword arguments; both were
retained and corrected without changing native expectations or production code.
The first clean x64 qualification built successfully but CTest rejected a Python-
style noncapturing regex. CTest returned 0 with zero tests; exact membership/count
verification correctly rejected the empty result. That
[failed phase](failed-selection-4156accf/summary.json) remains failed. Corrected
recipe `1e8d1087045291be509f0d6257e28428323ef3ff` uses a CTest-compatible group, preflights all 31 names
and explicitly resumes only the verified unchanged configure/build/registration
stages. Compiled artifact hashes remain exact before/after the resumed run. Native
source/test/contract parameters and deadlines did not change. The generator hash
and this sole qualification-recipe exception are bound separately in metadata.

The code is suitable for ordinary source integration after metadata/staged-byte
closure. Next, extend existing retained-frame/snapshot and owned-worker mechanisms
for directory mode before public frontend admission. Namespace/content, original
platforms/storage 0.1.0, writer/recovery, Setup, licensing and owner/release/privilege
gates remain. Earlier campaign failures and unknown historical delays remain.
