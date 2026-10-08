# W033 acquisition requirement coverage

Reviewed source `54328453e355b0522e4cb2581a8887247a18efd8`. This maps
DE-REQ-103-01 and the W033 fixture criteria to implemented tests. Execution
receipts and actual outcomes remain in the reproduction directory; source
inspection alone is not a pass. The Windows ordinary-file development profile
and provider-independent model are narrower than the full acquisition scope.

| Required case | Implemented fixture coverage | Qualification limit |
| --- | --- | --- |
| Source/destination aliases | Pipeline output/input alias sets and role bindings; actual ordinary-file aliases, hard links and parent/name checks | Logical file/volume identities do not prove all physical backing aliases. |
| Full destination | Actual capacity observations; injected pre-creation capacity refusal and disk-full write error (112), retained partial effects and recovery | No real full-volume campaign. Fault injection verifies the error path. |
| Thin provisioning exhaustion | Bounded capacity checks and retained write-failure uncertainty | No thin-provisioned storage provider or exhaustion environment; not qualified by generic error injection. |
| Disconnection | Source read failures, changed resource bindings, owned-process interruption and exclusive sharing tests | Physical device/transport disconnection remains unverified. |
| Corrupt acquisition map | Torn header/tail, complete invalid records, changed chains, checkpoint bytes, suffixes and seals; independent ordered/hash checks | Map is provisional; no production journal or power-loss durability claim. |
| Resumed different resource | Source/output/map/code/provider/host epochs; actual file replacement, changed source bytes and rebound resume checks | A different physical disk or external backing chain remains unverified. |
| Read substitution | Explicit zero-fill outcomes and map accounting; short/error reads are never counted as successful source data; bounded retry and failing-read-mostly rules | Instrumented source errors and model ports, not real failing-media qualification. |
| Destination preexistence | Actual `CREATE_NEW`, map/destination preexistence and creation/sharing races without truncation | Ordinary local-file scope only. |

The shared public adapter adds actual CLI/stdio/GUI/TUI/shell copies, no-output
prepare/review/refusal, exact resubmission without replay, role capability checks,
checkpoint cancellation, fresh-store resume and independently verified image/map
bytes. The full 64-event presentation fixture is separately labelled synthetic.

The fixture deliverable is implemented for this Windows development profile.
DE-W033 remains partial against the programme's all-platform/acquisition scope.
Owner acceptance, physical access, real failing media, power loss, snapshot/restore
readiness and other-platform execution remain separate. There is independent
local work available: DE-W040's exact proposed journal byte format and native
failure model depend on implemented DE-W023/016, without admitting product writes.
