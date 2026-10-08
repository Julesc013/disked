# W033 implementing-agent observation review

Reviewed `eae515b0d0c4a6fe60eba4e6fe2f4158e08c772b` against `3868d05bf488316f999a6e261f27042b33ede898`, DE-103 and the continued local development
grant. This permits continued implementation after recorded checks; it is not
owner acceptance, release admission or an independent storage review.

The Windows worker's pure record/history validation now belongs to a portable
runtime module. The worker writes the same provisional record bytes and checks
full history before projection. Acquisition observers use explicit image-op
identity and never fall back to fake metadata. Inspection completes independently
of copy outcome; cancellation persists a request, with acknowledgement only at
the worker's verified checkpoint. Watch termination does not transfer worker
ownership or remove recovery dependencies.

The shared event reader selects a closed acquisition profile with an independently
obtained exact definition. It checks resource/capture/code/host binding, total
coverage, record hash, counter/outcome relationships and cursor continuity.
Within a stream it freezes the full process/attempt binding, rejects regressing
coverage and disallows records after a terminal state. Failed acceptance leaves
the reader cursor unchanged. Reconnect supplies worker epoch and exact prior
digest; producer replay still verifies the full immutable history.

Acquisition events have a separate negotiated feature and 32 KiB envelope bound.
Retained records keep their 16 KiB/depth/value/string limits. The queue remains
64 events/one MiB; follow is bounded to 2000 ms. Only CLI/stdio acquisition-watch
batch admission explicitly selects the finite one MiB result budget. Other
requests and interactive frontends keep their existing 64 KiB default. Tests
prove the default is retained and invalid budget requests dispatch no callback.

New producer schemas and identity-dispatched semantics reject u64 overflow,
contradictory coverage/completion, changed event identity and incorrect hashes.
Those schemas cannot prove full coverage without an independent definition;
that check remains in the native observer/reader. Producer strictness and reader
handling of additive observational envelope fields remain separate.

All 45 native groups, 175 specification tests, 921 structural checks, generated
freshness, manifest, task context and exact source/input/artifact identities pass
clean reproduction. Tests cover actual product CLI/stdio observation and the
native portable reader. Existing interactive fake/image regressions also pass;
they do not qualify visible acquisition-copy frontend submission or large
acquisition-watch rendering. Those are the next bounded W033 work.
