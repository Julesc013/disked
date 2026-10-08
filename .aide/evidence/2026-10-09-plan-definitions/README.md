# Private immutable definitions and receipt-binding evidence

Verified source: `8ec0404f95209e2582f08609f338a7da352a1e2b`, based on
`3a11b9efce8deb4df4222dcd2ac88fe53aceb162`. DE-W040 remains active and incomplete.
Owner acceptance and production decisions DE-DEC-004/008 remain pending.

The separate native library/probe validates canonical immutable fake-model plan
bytes, all resource and code dependencies, effect ranges, state-digest ordering,
cycle witnesses, independent recovery properties and separate receipt bindings.
It has no target/file/effect/authority ports and is not linked into `disked.exe`.
This is a private proposal, not a production ABI, admission broker or recovery
writer. Matching declarations do not establish authentication, freshness,
qualified flushes or actual postconditions.

Clean reproduction passed 243 independent definition/receipt cases, 784 framing
vectors, six focused native groups, 925 structural checks and 175 spec tests
(173 passed, two symlink skips), generated freshness, manifest and task context.
All 235 build-input hashes and seven retained artifact hashes were verified.
The manifest contains 245 files/1,504,874 bytes. Actual build-information launch,
PE headers, imports and dependencies were recorded. The tested lane is Windows
10 Enterprise build 19045, x64 MSVC 19.44.35228.0/toolset 14.44.35207, SDK 19041,
C++14 Release `/MT`; existing Python 3.14.7 with pinned spec-tool dependencies.
Execution used BLACKGLASS-WIN1\Jules with an unelevated token.

Only six of the available 49 native groups were run at this source. The new
component is disconnected from product behavior; checks cover its codec/JSON
dependencies and the product's bootstrap/metadata/invocation boundary. The other
43 groups, GUI captures and acquisition/resilience journeys were not rerun here.
Historical full 48-group results and timing/harness limitations remain bound to
`ce9ae70f`; they are not new results for this source.

`reproduction-8ec0404f/commands.json` retains exact commands and results;
`clean-results.json` binds source/toolchain/input/artifact identities. Artifacts
are local under `.aide-local/artifacts/DE-W040-definitions-8ec0404f/` and are not
published or installed. Hashes identify these actual builds; bit-for-bit equality
across tool paths/build timestamps is not claimed. `reproduce.py` can reproduce
the selected checks at the matching source using the documented toolchain and
an existing Python environment with `spec/tools/requirements.txt` dependencies.
It creates a new clean clone and refuses an existing destination. The preceding
231-case result at `57177457` and its matching runner are retained as history.

The failed exploratory harness run and its repair remain in `FINDINGS.md` and
the original logs/JSON. Neither failed observations nor older successes were
overwritten. Review is by the implementing agent, not owner or independent safety
acceptance. Next: guarded intention/flush/effect transitions, stale worker/capture
epochs, cancellation, uncertainty and observation-before-replay; then integrate
payload semantics with framing. Real storage and physical durability remain gated.
