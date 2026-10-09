# Private health-observation development model

DE-W032 currently provides a native C++14 collector tested against owned fixture
values. It binds a result to the selected target generation/composite identity,
observer/provider declaration and capture/worker ticket. It preserves raw bytes,
vendor interpretation and unavailable values separately. Its declared identities
are not physical validation or authenticated authority.

The collector has no device, query, file or self-test port and is not linked into
`disked.exe`. `health.assess` remains planned/unavailable. Actual native adapters
still require DE-W030 inventory, containment, identity/classification review and
applicable platform evidence. This model is partial DE-W032 progress, not completed
provider admission or forensic qualification.

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
