# Implementing-agent journal codec review

Reviewed `ce9ae70f28e6e8c7d6408563fd3508d51d263164` against `2e63bbabf75129acb5c6b67e0fa3c54ce2f4fca8`, DE-043/042/074 and the continued local
development grant. This review permits local continuation, not owner acceptance,
a stable format or production journal admission.

The experimental header/record layout is explicit in the canonical profile;
native packing is never serialized. Python struct/hashlib expectations are
independent of the native encoder and check exact bytes. Digests bind header,
complete prefix/payload, record order and expected resource/code observations.
They are integrity checks and do not authenticate supplied receipts.

Source length/record/payload bounds are checked before corresponding read calls.
The scanner retains one payload; the test observer explicitly caps metadata at
64 rows while traversing 4096 frames. Short or oversized source returns and source
exceptions fail closed. Source diagnostics are normalized instead of treating
untrusted exception text as an authoritative code. Visitor rejection/exception
does not extend the verified prefix and is distinguished from source failure.

Partial final framing is uncertain and never repaired here. Invalid complete
records, wrong chains/order, unsupported critical records and bytes after a Seal
are rejected. Strict producers emit only known kinds; readers preserve unknown
zero-flag observational kinds in the declared high range. Dropping a critical
bit cannot make a known mutation record observational. The codec supplies no
effect writer, replay/truncation decision or operation-completion authority.

The test publisher identity/epoch and journal-global sequence are separate.
Their observed values do not transfer effect-worker ownership. Full immutable
plans, receipt semantics, traits, freshness/worker guards and flush/effect
reconciliation remain later W040 components. The format is explicitly proposed
and the production decision/acceptance ledger is unchanged.

All 48 native groups, 175 specification tests, 923 structural checks, generated
freshness, manifest/context, 230 input hashes and five artifact identities passed
clean reproduction. Product linker dependencies exclude the codec. No physical
access, elevation, customer data, installation, signing or remote writes occurred.

The first clean campaign's shared-image callback failure is retained and remains
unexplained; a timed probe and three unchanged repeats passed. The follow-up
private event gate establishes callback entry/continued occupation and deliberately
releases it. Correlated observations, not elapsed sleep or gate release, establish
slot availability. A closed gate cannot affect the ordinary product. Clean native
and separate schema-validated image journeys passed at this reviewed source.
The retained image-inspection PNG was visually inspected and shows the native
command/result panel and form. The shared screenshot helper's more general
client-render validation limitation remains recorded in TODO.MD.

The reviewed source's initial acquisition journey missed its 30-second fixture
deadline, completing in 30.837 seconds. Subsequent reconciliation independently
checked source/destination bytes, map/record hashes, identity and an absent worker.
There was no replay or fixture removal. Unchanged clean revalidation passed; the
initial campaign remains failed in the ledger. These samples do not qualify
universal storage throughput or eliminate host timing variance.
