# DE-W020 implementation findings

The pre-implementation DE-031 contract defines finite pure-C arithmetic, borrowed
views and immutable named block spaces. Existing DE-W018 functions were renamed
into the single internal module; the earlier 411-case probe surface is preserved.

The first strict GCC run passed all 10334 property cases. The first MSVC CMake
build rejected the test transport's strtok use with C4996 under /W4 /WX /sdl.
The harness now uses a local scan within its fixed 256-byte line and ten-token
limit; no warning option was weakened and no expected result changed. The corrected
native build passed portable.checked and portable.c_cpp_linkage. This diagnostic
was observed in the tool output; a complete initial build log was not captured.

Review made endian writes retain their destination pointer before modifying the
caller's buffer. Final GCC x64, MSVC 2022 x64 and MSVC 2017 x86 controls each pass
10334 cases, including actual 32/64-bit size_t conversion. A separate GCC legacy
regression passes the original 411 cases. Full native and clean-source verification
are retained separately. All raw compiler logs preserve their original whitespace.

The block-coordinate constructor and the JSON extent producer have different
admission scope: the JSON review schema also requires successful u64 byte
projection. The owning contract now states that distinction explicitly. No buffer
or I/O adapter receives a rounded, narrowed or wrapped byte range.
