# Contained private namespace observer qualification

Final exact source **d3798a7d867f9cce7369ca50cd55659e0280eddb** builds and executes on the
ordinary `BLACKGLASS-WIN1\Jules` Windows 10 host (10.0.19045), without elevation.
Each x64/x86 campaign has 49 adapter process executions / 258 assertions,
plus 24 controller invocations / 18 actual child launches / 116 assertions.
That is **182 actual processes and 748 assertions** across both architectures.
The clean tooling suite ran 215 tests (213 passed, 2 skipped); 1,045 structural
checks, the exact context and specification manifest verified.

The selected compiler is MSVC 19.44.35228 / v143 14.44.35207, SDK 10.0.19041.0,
CMake 4.2.3, C++14 Release `/MT`, warnings as errors and native mitigations.
Compiler/project configuration, PE headers, imports and dependency observations
are retained. Static DLL dependence and the explicitly dynamic System32
ADVAPI32 security/random bindings are distinct; these observations do not
qualify XP, other Windows hosts or the full runtime/platform closure.

| Final private artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| adapter/x64 | 248832 | `sha256:b1a4def16b50539d676f75cbed2347308052d0ea48d83665c8e4203c5c790a26` |
| worker/x64 | 331776 | `sha256:f654ce1f7411a0c2f78c84a95536a9fc5093df016f96ee9dc0049caced0a2842` |
| adapter/Win32 | 206848 | `sha256:65895947df17989a4ea3d1df1177bf5003c2404b0ebf216ab49a7257478f24eb` |
| worker/Win32 | 278016 | `sha256:662403c16642e165f1abc15a35d6bada1e88506d7561b761bb02d1ff8fbf7e0e` |

Binaries are retained in `.aide-local/artifacts/DE-W030-nt-contained-d3798a7/`.
They are private fixture programs, not product `disked.exe`. The separately
qualified product remains dev.36 at `ec30be78ba9e9f61dc578ff67b9d0af186166145`;
it was not rebuilt or retested here, and no product command/provider is admitted.

The observer reuses existing strong code-parent pins, exact code bytes,
current-user object ACL, finite aggregate/local jobs and atomic handle/job-list
assignment. Its five capabilities are two bounded mappings and cancellation,
admission and dispatch events; it inherits no ambient stdio or storage handles.
The child reads immutable input and publishes one bounded, hashed reply. The
parent validates code/request/capture/observer/worker/attempt/process identities,
producer shape and fixed non-authority claims before exposing a snapshot.

Actual tests cover delayed results without replacement, cancellation before and
after query entry, a hung/crashed reader, explicit retirement, killed-client job
closure with an exact open child-process handle/creation identity, publication
before exit, stale/malformed/unsupported replies, invalid inputs and role/wait
budgets. Native full and mixed API tables are refused before admission. Pointer
checks do not prove arbitrary wrapper behavior; only the exact compiled fixture
factory is qualified. Volume enumeration replies are injected; no live host volume
namespace or raw physical device is accessed.

The original `acfe15a` clean candidate passed 23 controller invocations / 17
reader launches / 110 assertions per architecture, plus the same adapter and
tooling checks. Code review then tightened the original full-table-only check
to reject individual native pointers. Final `d3798a7` evidence includes the
mixed-table regression. Both exact revisions and raw campaigns are retained.
The exploratory x86 C4018 signed/unsigned failure is retained; its types were
corrected without disabling warnings or changing required outputs.

`reproduction-d3798a7/` is current qualification. `reproduction-acfe15a/` and
`exploratory/` are historical evidence. Original command/log/request/output/error
bytes and 24 exact Git-bound source inputs are retained. Client/reader process
termination is not cancellation acknowledgement, recovery success, durable
reconnect or storage quiescence. A missing/invalid reply remains unknown.

Reproduce from a new local output directory:

```text
python .aide/evidence/2026-10-10-nt-contained/reproduce.py --repository . --source-revision d3798a7d867f9cce7369ca50cd55659e0280eddb --output NEW_OWNED_OUTPUT
python .aide/evidence/2026-10-10-nt-contained/verify_closure.py
```

Finite observed waits do not supply universal kernel/metadata deadlines.
Live namespace, physical identities/topology, provider/graph/public/durable
service admission, historical/other hosts, full DE-W030, owner acceptance and
full 0.1.0 remain open. The next local slice binds the qualified observation
model into a capture/epoch-safe graph using generated observations; live and
physical dispatch stay at their separate gates.
