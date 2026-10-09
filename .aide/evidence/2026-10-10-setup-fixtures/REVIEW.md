# Implementing-agent review: Setup fixture mapping

Reviewed packaging source: `92d72bb7a7a1b312b74db9dcbeccba9bdda94548`.
Native payload source: `ec30be78ba9e9f61dc578ff67b9d0af186166145`.
This review permits local continuation under the existing programme grant. It
is not independent review, owner acceptance, provider admission or release.

This first candidate's byte/shape results are retained as history. Final review
caught its `maximum_tested_reader: 1.0` ambiguity: no installed-state reader was
exercised. The implementation/profile now use explicit `not_run`, and reject
promotion to a version without a new contract. The new packaging source must
receive its own clean qualification before this slice's final handoff.

The clean reproduction passed 23 recorded commands, including four expected
negative outcomes: repeated extraction, repeated assembly, occupied generated
case retention, and an unavailable installation command. Both the original and
extracted executable actually launched and returned identical build information.
The independently checked ZIP contains one 2,110,464-byte `disked.exe` with
SHA-256 `ac2721db6b26231ed52c31742f472063bed8c7bd88ceb8f14690eb37dd63994d`.
The ZIP itself is 2,110,582 bytes, SHA-256
`5379d37cb0e016806b7aa71a4297b2cf616a6692bf24aa6a17fe66ff7b79a7a9`.

All 22 focused fixture tests passed. They cover deterministic equality,
malformed and contradictory package/recipe relationships, hashes recomputed
around a changed bundle, separately selected expected inputs, stale source
bindings, changed staging, bounded metadata, namespace/link rejection,
source/output overlap, occupied empty/file/data roots, and retained partial
assembly/extraction without cleanup or reuse. Synthetic test payloads are
explicitly not executable qualification. Tooling ran 215 tests: 213 passed,
two skipped. Structural validation passed 1,035 checks. The clean context is
289,439 bytes; manifest and source freshness checks passed.

Fourteen packaging inputs and 22 selected upstream Git blobs have exact retained
hashes. Five MIT schemas are unmodified and resolve offline. Schema conformance
is separate from semantic agreement and the callable USK C ABI. The native
401-input build evidence was reused at its exact identity, and those input hashes
remain unchanged; no native rebuild or new full native suite was claimed.

Every extraction/assembly output is a new explicitly marker-owned ordinary
fixture child. Existing roots refuse even if empty, and generated foreign,
case, evidence and unresolved recovery files retain exact hashes. Failure leaves
partial output. No lifecycle plan/apply, generic acquisition, competing
installed-state record or storage dispatcher is introduced. Configuration and
case/recovery ownership stay external to immutable payload ownership.

During implementing-agent review, verify/extract were tightened to require
separate original inventory/build-info inputs. A fully replaced internally
consistent bundle therefore cannot establish its own expected bytes. Path
canonicalization closes source/output aliasing in quiescent fixtures. This
remains a fixture tool, not an atomic snapshot or hostile-filesystem sandbox.
Unsigned hashes do not authenticate identity; supplying false independent
inputs cannot become genuine approval or native qualification.

The first source freeze `5248a8a` emitted a Windows license checkout conversion
warning. Exact license bytes are preserved by the subsequent source-bound
attribute rule; only `92d72bb` receives the clean qualification. Earlier structural
validation also rejected a spec link escaping its canonical tree; the link was
fixed without weakening the validator. Neither event is hidden or promoted
into a runtime pass. No new service/policy rejection occurred in this slice.

DE-W060 remains partial. Read-only SDK/ABI consumption, actual Setup lifecycle,
installed-state compatibility, embedded H/D/S, active-generation retirement,
native servicing owners, other targets, owner licensing, signatures and
publication need their own evidence and applicable authority. The full
all-platform/storage 0.1.0 programme remains active. Continue with an exact
read-only SDK consumer probe under owned builds, or other eligible local work,
without executing fetched scripts or crossing installation/storage gates.
