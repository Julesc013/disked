# DE-W106 preparation: managed packet coordinator

This is a partial development checkpoint. DE-W105 remains current and its native
capture/full qualification gates remain open. No dependency, worker, campaign,
owner or release acceptance is recorded here; main remains at DE-W104.

The coordinator now connects packet preparation, native/reference collector APIs
and finalized evidence comparison. Preparation invokes no workers and includes
all 35 current corpus recipes by default. Named subsets are explicit. Exact
case/participant/kind sets, commands, timeouts, outcome policies, identities,
original Windows/POSIX paths, generator and comparison-tool inputs are frozen
before collection. A separate caller-held digest binds the resulting manifest.

Before dispatch, the coordinator checks every supplied worker identity and fixed
command, the authored recipe facts and selection, and existing output paths.
A new digest cannot relabel a subset as all cases or redefine the independent
fixture facts. Returned success flags are ignored: bounded receipts must exist
at their expected paths, and success consumes the full comparator gate plus
declared positive projection controls. Active/completed participants and the
comparison report's byte count/hash are retained. Exceptions and interruptions
stop without retry; failed finalization cannot yield a successful receipt.

The synthetic-worker integration tests exercise real packet generation,
collection, comparison and ordinary-file cleanup. The complete 35-case example
with native and two reference definitions records all 197 planned unavailable
observations: evidence accounting is complete, while execution and coordinator
success fail. Positive controls and conflicting GPT copies also traverse the
complete data path without resolving a native conflict. Changed raw artifacts,
missing/extra workers, wrong identities/commands, missing receipts and interrupted
or failed checkpoints cannot produce success.

The final unchanged-input pass ran 253 specification tests (two skips), 211
tooling tests (one skip) and 77 differential tests (five Linux-only skips),
plus 1,327 structural checks, source-map coverage of all 327 runtime files once
and manifest verification. Exact source hashes and command outputs are in the
[coordinator review](coordinator-review.json) and compressed receipt. The managed
validation workspace peaked at 54,001,795 bytes and was removed. Earlier focused
integration runs passed 73 and 76 tests at their respective intermediate bytes.
No native/reference tools were launched and the shared VM was not accessed.

This supplies no worker launcher, transport, scheduler or execution admission.
Its comparison success does not qualify native product tests, sanitizers,
process ownership, storage confinement, OS quotas, platforms or releases.
The outer managed runner owns cleanup; its actual result remains separate from
the coordinator's pending-cleanup marker. Historical WSL and direct collector
CLIs stay suspended. Do not infer permission or qualification from an API call.

Next, connect the existing confined guest runner to the typed collection port:
measure exact worker/tool/profile identity, preserve stdin and separate raw
streams, prove terminal process ownership and capped cleanup, then run an owned
bounded representative case. Determine actual reference-tool availability before
claiming any external profile. Keep DE-W105 and real native/sanitizer admission
at their existing gates; do not repeat closed GUI capture variants.

Earlier source-bound checkpoints remain in the [set review](validation-review.json),
[CLI review](cli-review.json), [binding review](bindings-review.json) and
[collector review](collector-review.json). Historical outputs are unchanged.
