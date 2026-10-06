# DE-W012 synchronous slice: development review

Reviewed locally by the implementing agent on 2026-10-06. This is a development
review under the user's cross-unit continuation policy, not independent review,
owner acceptance, provider admission or release qualification.

The descriptor registry owns exact words, aliases, option arity, parameter
bindings and static suggestions. The complete invocation is validated before
dispatch. No handler initializes even the fake provider; the linked poison
variant and its positive control exercise that boundary. Planned storage commands
remain unavailable, including after successful parameter parsing.

The JSON reader rejects duplicate decoded keys, malformed UTF-8/surrogates,
nonfinite conversions and bounded-resource excess. Request handling validates
known structure, typed parameters and unsupported features before dispatch.
Responses are constructed and bounded before writing. NDJSON flushes each frame,
retains request order, continues ordinary refusals and ends on resource failures.
Compatible readers preserve observational extensions while refusing incompatible
schemas, statuses and required features. Producer outputs are separately checked
against the strict repository schema.

Review corrections included an argument-byte accounting guard, token locations
for invalid quantities, matching native/tool u64 quantity semantics, and matching
stream termination to the JSON reader's actual limit diagnostic codes. Regression
checks cover these paths. Historical DE-W010 cases remain at their original
contract; the active CTest process checks now exercise the explicit DE-021/022
synchronous contract. No expected value was changed to conceal an implementation
failure.

The native lane remains Windows x64/MSVC C++14. The JSON representation and parser
are private implementation types, not a public C ABI, durable plan encoding or
legacy-target admission. The parameter validator implements the admitted scalar
shapes; it is not a general JSON Schema implementation. Async identities, event
payloads, wait/reconnect behavior and effect certainty still require DE-W016/017.

This work does not qualify absent/invalid standard handles, Explorer launch,
caller-owned console behavior, other hosts, GUI/TUI, storage, recovery, installation
or a live AIDE worker. DE-W011 is the next local slice. Keep DE-W012 open for its
remaining asynchronous admission gates. Retain the empty owner-acceptance ledger.

`working-commands.json` records actual commands and exit outcomes. The working
build passed six CTest groups, strict native producer-schema validation, 154 of
156 specification tests (two symlink tests skipped), 879 structural checks and
passive validation of 36 AIDE-shaped records. Clean-commit reproduction is recorded
separately after committing the source; working-tree evidence alone is not that
claim.
