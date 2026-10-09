# Private native volume-namespace qualification

Exact source **17129e6eaa6cfb5786cbf1f022fb38eb25fd286f** builds and executes a bounded Windows
volume-namespace adapter with injected Win32 replies. Each x64/x86 campaign
has **49 actual process executions and 258 independently checked assertions**.
The clean checkout tooling suite ran 215 tests (213 passed, 2 skipped), and
structural validation passed 1,043 checks. This is a DE-W030 component,
not a completed native inventory unit or a released product capability.

The ordinary host identity was `BLACKGLASS-WIN1\Jules`; the process was not
elevated. MSVC 19.44.35228 / v143 toolset 14.44.35207, SDK 10.0.19041.0,
CMake 4.2.3, Release C++14 and static `/MT` were used for x64 and Win32.
The compiler configurations and original command/log bytes are retained.
`dumpbin` records x64/x86 PE machine identity, the intended volume API imports,
KERNEL32.dll as the only dependent DLL, and modern PE/CRT settings. Those
settings and injected execution do **not** qualify XP or any other host.

| Private fixture artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| x64 | 246272 | `sha256:3a15be6eb28711e38d281c0e87e5c203e670ec84683fc80e4a6b5aaf341124cc` |
| Win32 | 204800 | `sha256:f8978240d64a5c8978e23e4dba8b39594c9e047ef89a0a4a5b70f9b12a0b1985` |

The binaries are retained under `.aide-local/artifacts/DE-W030-nt-volume-17129e6/`.
They are private qualification programs, not `disked.exe`. The shipped product
composition is unchanged at the separately qualified dev.36 source
`ec30be78ba9e9f61dc578ff67b9d0af186166145`; it was not rebuilt or retested here.

`reproduction-17129e6/` retains exact commands, logs, all request/stdout/stderr
fixture bytes, independently checked results, compiler/project configuration,
context manifest and hashes of all 11 selected source inputs. The clean checkout
and final source cleanliness were checked. `exploratory/` keeps earlier working
campaigns and the oversized-fixture failure; those are not clean-source evidence.

The initial maximum-mount fixture was refused by the private JSON harness with
`value_limit_exceeded` before API dispatch. The harness now uses its explicitly
specified 16,384-value/65,535-byte request budget; public/product limits were
not raised. Both clean campaigns include that fixture and exact budget edges.

The native table is inspected without dispatch. Every enumeration and mount
reply in qualification comes from injected callbacks. No live host namespace,
physical device, filesystem contents, elevation, installation, customer data,
network or remote write is part of these campaigns.

The implementation preserves exact UTF-16LE units separately from inert ASCII
display, retains duplicate observations, refuses incomplete native buffers,
keeps denial/removal/partial/cancellation visible, and closes once without
turning failed close into quiescence. A complete selected namespace is not
physical identity, topology, mutation authority or complete alias proof.

Reproduce from a new ordinary local output directory:

```text
python .aide/evidence/2026-10-10-nt-volume-namespace/reproduce.py --repository . --source-revision 17129e6eaa6cfb5786cbf1f022fb38eb25fd286f --output NEW_OWNED_OUTPUT
python .aide/evidence/2026-10-10-nt-volume-namespace/verify_closure.py
```

Live API qualification, containment of hangs, physical identities/topology,
public graph/service/provider admission, historical and other platforms,
full DE-W030, owner acceptance and full 0.1.0 remain open. The next bounded
development slice is contained private namespace observation under injected
process faults; no live storage dispatch is authorized by this evidence.
