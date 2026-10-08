# W033 implementing-agent command component review

Reviewed clean source `9a9de03aab09aa87f28e0c445408c719acb281c1` against `3a2f003fc265b72bc56a76cab17e431735f7b08a`, DE-103 and the continued
local development grant. This is implementing-agent review, not owner acceptance
or an independent privileged-storage review. It supports continued local
integration; W033 is incomplete.

The command owns no Windows/file effects. Its preparation and execution ports
point inward from the shared runtime; the private probe supplies the tested
Windows worker adapter. The generator binds the transitive local schema closure
to exact build inputs. The catalog remains the single command owner and preserves
image.acquire's planned/unavailable status. No public executable composition was
changed to admit the private worker.

Prepare/execute fields are mutually exclusive. The full definition is strictly
typed and bounded to 16 KiB canonical JSON, depth 20, 2048 values and 1024-byte
strings; text decoders also limit their original inputs and reject duplicate
keys. Definition options agree with the inner plan. The exact digest and four
actual true grants are checked before an execution callback. Spec-tool validation
checks directory u64 bounds, option agreement and byte limits by schema identity;
production plan semantics remain with the native acquisition core.

Response projection preserves the known operation identity and recovery
coordinates on post-invocation uncertainty. A running admission needs an active,
nonquiescent observation; a pre-admission refusal carries no admitted identity.
Completed execution requires matching definition/operation/code/host/capture
bindings and complete certain coverage. A paused operation remains incomplete
for execution (exit 4), while inspecting it is a completed read (exit 0).
Substitution quality is retained rather than equated with original source data.

Independent callback spies establish zero provider calls for invalid inputs and
exactly one call for admitted tests. Real generated-file checks verify bytes/map
hashes, reconnect, cancellation/resume provenance and late results. All 44 native
groups and 173 specification tests pass clean reproduction (two existing skips);
the retained pre-review working full run is superseded for the final source.

Shared parser/form decoding is not actual GUI/TUI/shell execution. Operation
watch and exact visible review/grant presentation still require implementation.
The schema remains provisional; global aliases/fencing, failing physical media,
power-loss survival, other targets, owner and release gates remain separate.
Continue W033 with those interface/lifecycle integrations before product admission.
