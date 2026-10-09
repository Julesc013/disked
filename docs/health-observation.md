# Fake health observations and private collection model

DE-W032 currently provides a native C++14 collector tested against owned fixture
values. It binds a result to the selected target generation/composite identity,
observer/provider declaration and capture/worker ticket. It preserves raw bytes,
vendor interpretation and unavailable values separately. Its declared identities
are not physical validation or authenticated authority.

The collector has no device, query, file or self-test port. The provisional dev.22
`health.assess` composition uses it for synchronous compiled fake fixtures through
the same service as CLI, stdio, GUI, TUI and shell. Actual native adapters
still require DE-W030 inventory, containment, identity/classification review and
applicable platform evidence. This model is partial DE-W032 progress, not completed
provider admission or forensic qualification.

```powershell
disked health assess fake:alpha@1 --json
disked health assess fake:clone@1 --include-identifiers --include-raw --include-interpretations --json
```

Use exact graph target IDs. An optional stdio `expected_revision` (and GUI/TUI
review) binds the graph before collection. Denied or stale nodes refuse; unknown
nodes return partial observations and table/volume nodes explicitly have no
observer. There is no real sampling timestamp, physical query, self-test or file
export. The [proposed fake command contract](../spec/catalog/fake-health-command.json)
defines outputs and diagnostics; it is not a frozen health API.

The `support_report` defaults to labels/state/availability without values or
identifiers. Four optional flags select identifiers, raw values, interpretations
and customer data. Identifier/customer field content additionally needs its
category flag; secret content is always omitted. The outer selected target and
graph revision are routing metadata: the whole response is not a redacted support
export. Human views escape arbitrary text; machine values retain exact bytes.
An oversized label has explicit error/null values at the corresponding raw or
interpretation limit. A complete response never proves healthy or safe media.

With the [pinned native toolchain](native-bootstrap.md), run:

```powershell
cmake --preset windows-bootstrap
cmake --build --preset windows-bootstrap --target health_observation_probe
python tests/health/test_health.py --probe build/windows-bootstrap/Release/health_observation_probe.exe --root .
ctest --preset windows-bootstrap -R '^health.observation_model$'
```

The [proposed profile](../spec/catalog/health-observation-prototype.json) defines
the private input/output shapes, source/field/byte limits, epoch rules and export
policy. It is not a stable public API. The probe consumes owned JSON action vectors
and emits structured observations; it never executes values as instructions.

Every requested field starts unknown. Complete results must cover the selected
field set, but fields can explicitly be unavailable or denied. A complete response
does not establish healthy media, safe mutation, future reliability or adequate
backup. Timeouts exclude late content while keeping the worker outstanding;
separate retirement is required before another capture. Cancellation stops new
queries and retains valid pending observations without manufacturing worker exit.

Internal observations preserve exact raw bytes and UTF-8 interpretation with a
rule identity. Default support output contains ordinal labels, static states and
availability only. Explicit flags select identifiers, raw values, interpretations
and customer-classified data; secret-classified field content is always omitted.
Sensitivity is fixed in the selected request and cannot be downgraded by a reply.
The model cannot establish whether a future adapter classified its input correctly.
Actual admission must review that classification and presentation behavior.

Current fixture evidence exercises identity mismatches, partial/unavailable data,
malformed values, late/duplicate/stale responses, cancellation, worker retirement,
counter and byte limits, exact control/Unicode data and policy-specific omissions.
Other-platform execution, actual physical observations, OS worker containment,
deep scans, forensic custody and production support exports remain unverified.
