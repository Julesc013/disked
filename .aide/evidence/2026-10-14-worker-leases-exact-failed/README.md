# Exact worker lease campaign: terminal native failure

Clean immutable source e75602f8 builds with 48 selected standalone headers.
The complete native campaign ran 141 groups: 139 pass; FAT tree-extraction worker
and FAT worker fail. All eight failures from the earlier 60376a0e campaign pass.
Post-native Git status is clean and every retained source-input hash is unchanged.
Tooling, imports and context steps were not run after the native exit 8.

Both failures exercise the fifth-worker quota. The harnesses constructed that
worker outside their launch-refusal catches, while the declared new lease
contract rejects a full namespace during preparation. The actual refusal is
operation_worker_budget_resource, before a fifth process exists. This evidence
does not qualify the whole source. Corrected harnesses must retain precise
refusal, four live workers, actual retirement and no-output/source-preservation
checks. Main promotion and full original 0.1.0 remain unearned.
