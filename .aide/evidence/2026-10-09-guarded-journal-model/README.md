# Guarded fake-memory journal/effect evidence

Verified source: `09bb6cb5c39f75a3fb81a3678ebf258930656419`, based on
`5d9039db5d05613623082419a20bbf66a1b6012c`. DE-W040 remains active and incomplete.
Owner acceptance and production decisions DE-DEC-004/008 remain pending.

The separate native `disked_guarded_model` exercises immutable-plan and receipt
bindings, stable-intention-before-dispatch, target flush/recapture/verification
before completion, whole-plan resource identity/state guards, late worker results,
cancellation, client loss, crash fates, fresh admission and retained journal
generations. It exposes no host file/device/process or authenticated authority
port. Its hash-chained JSON history is not the binary codec or a production ABI.
All three private journal/plan/model libraries remain outside `disked.exe`.

Clean reproduction passed seven focused native groups, 168 guarded scenarios
with 4117 actions, 243 definition/receipt cases, 784 framing vectors, 927 structural
checks and 175 spec tests (173 passed, two symlink skips). Generated freshness,
manifest and task context passed. All 240 input hashes and nine retained artifact
hashes were verified. The manifest contains 246 files/1,517,844 bytes. Build-info
launch and actual PE headers/imports/dependencies were recorded. The tested lane
is Windows 10 Enterprise build 19045 x64, MSVC 19.44.35228.0/toolset 14.44.35207,
SDK 19041, C++14 Release `/MT`, Python 3.14.7, PyYAML 6.0.3 and jsonschema 4.26.0.
Execution used BLACKGLASS-WIN1\Jules with an unelevated token.

Only seven of 50 configured native groups ran at this source. The component is
disconnected from product behavior; checks cover its JSON/definition/codec
dependencies and product bootstrap/build/invocation boundaries. Other 43 groups,
GUI captures and acquisition/resilience journeys were not rerun. Historical full
48-group evidence and timing/harness limits remain bound to `ce9ae70f`, not this
revision. `FINDINGS.md` retains fixture failures and five native defect categories;
original observations and selected old-source snapshots were not overwritten.

`reproduction-09bb6cb5/commands.json` contains actual commands/results and
`clean-results.json` binds source, toolchain, inputs and artifacts. Executables and
libraries remain local under `.aide-local/artifacts/DE-W040-guarded-09bb6cb5/`.
They are not installed or published. Hashes identify actual builds; bit-for-bit
equality across tool paths/timestamps is not claimed. `inventory.json` binds
retained evidence bytes, and the handoff is schema/semantically validated.

For reproduction, retain a copy of `reproduce.py` from this evidence commit, then
run it from a checkout of the verified source with the documented toolchain and
existing Python dependencies from `spec/tools/requirements.txt`. The script was
committed after its source checkpoint and is not present at that earlier revision.
Use its absolute path if needed. It creates a new local clean clone, refuses
existing destinations, records actual logs and does not fetch remote code or
install dependencies. Reproducing at a later evidence-only commit changes the
source stamp and artifact hashes.

Review is by the implementing agent, not owner or independent safety acceptance.
The fake flush/crash and worker-exit assumptions qualify only this closed model;
missing physical journal data cannot prove an effect absent. Semantic binary
journal integration, real flush/observer ports, trustworthy authority, independent
safety review, physical power-loss tests and other platforms remain unverified.
Next: bounded semantic binary-journal integration and contradictory-history tests.
