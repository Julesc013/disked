# Semantic binary journal declaration evidence

Verified source: `0aed6f813a58947a413d73a51c0c4f12e005f84e`, based on
`3c948562cff7580e3598056784629a698a345139`. DE-W040 remains active and incomplete.
Owner acceptance and production decisions DE-DEC-004/008 remain pending.

`disked_journal_semantics` joins the bounded byte scanner to private immutable
definitions/receipts and typed event/recovery declarations. It checks expected
plan/header/publisher bindings, exact canonical payloads, receipt references,
scope, per-attempt event sequence, capture/worker domains, resource states,
intention/completion/cancellation order and fresh checkpoint declarations. It
preserves the accepted prefix/projection on semantic, framing or source failure.
All projections retain false authority/durability/replay/retirement flags and
require live reconciliation. This is declaration consistency, not authenticated
facts, live target/process evidence or a storage executor. The guarded model's
native event producer is not yet integrated. All four private libraries remain
outside `disked.exe`.

Clean reproduction passed eight focused native groups, 189 semantic scenarios
(378 inspections including separately submitted complete-prefix controls), 168
guarded scenarios/4117 actions, 243 definition/receipt cases, 784 framing vectors,
929 structural checks and 175 spec tests (173 passed, two symlink skips).
Generated freshness, manifest and task context passed. All 245 build-input hashes
and 11 retained artifact hashes were verified. The manifest contains 247 files/
1,530,609 bytes. Actual build-info launch and PE headers/imports/dependencies were
recorded. Tested lane: Windows 10 Enterprise build 19045 x64, MSVC 19.44.35228.0/
toolset 14.44.35207, SDK 19041, C++14 Release `/MT`, existing Python 3.14.7,
PyYAML 6.0.3 and jsonschema 4.26.0. BLACKGLASS-WIN1\Jules ran unelevated.

Only eight of 51 configured native groups ran at this source. The reader and
shared test-fixture changes are disconnected from product behavior. Selected
checks cover the reader/model/definition/codec/JSON dependencies and product
bootstrap/build/invocation boundaries. Other 43 groups, GUI captures and
acquisition/resilience journeys were not rerun. Historical full 48-group evidence
and timing/harness limits remain bound to `ce9ae70f`, not this revision.
`FINDINGS.md` retains both failed exploratory fixture runs, their repairs, original
input/output hashes and selected generator snapshot; no native defect was
established by those failures. This is not a claim that the reader has no defects.

`reproduction-0aed6f81/commands.json` retains exact commands/results and
`clean-results.json` binds source, toolchain, inputs and artifacts. Binaries remain
local under `.aide-local/artifacts/DE-W040-semantics-0aed6f81/`; nothing was installed
or published. Hashes identify actual builds, without claiming bit-identical builds
across tool paths/timestamps. `inventory.json` binds retained evidence bytes, and
the partial handoff is schema/semantically validated.

To reproduce, retain a copy of `reproduce.py` from this evidence commit, then run
it from a checkout of the verified source using the recorded toolchain and an
existing Python environment with `spec/tools/requirements.txt` dependencies.
The runner was committed after its source checkpoint and is absent at that earlier
revision; use its retained absolute path if needed. It creates a new local clean
clone, refuses existing destinations, records actual logs and does not fetch
remote code or install dependencies. A later evidence-only revision changes the
source stamp and artifact hashes. The clean pack's disposable `DE-W040-guarded`
directory label is retained from the earlier runner; its verified content includes
the current semantic-reader input closure.

Review is by the implementing agent, not owner or independent safety acceptance.
Real adapters, authenticated authority, independent safety review, physical
power-loss tests and other platforms remain unverified. Next: integrate the closed
guarded model's event producer with this typed binary reader and validate actual
generated crash/fault prefixes without converting accepted bytes into authority.
