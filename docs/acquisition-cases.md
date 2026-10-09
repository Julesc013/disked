# Recorded acquisition cases

The private native case reader captures an explicitly selected acquisition
operation's `acquisition.request` and `acquisition.records`. It validates their
contract and chain, holds ordinary read-only file and ancestor handles, and
checks exact contents, paths and metadata generations. The
[proposed profile](../spec/catalog/acquisition-case-prototype.json) owns these
semantics. It opens no image path recorded inside either metadata file.

The immutable case retains the original before definition, accepted records,
exact history digest/completeness, and an after snapshot only for a complete
finished history. Its revision binds that content. The native source binding
separately identifies current files and ancestors. An unchanged content revision
does not establish resource-generation continuity. Open/torn histories, absent
configuration data, worker exit, actor authenticity and current image validity
remain qualified or unknown; a recorded completion is not a new verification.

Default support contains structural state and recorded outcome. Raw counters,
code/random identifiers and labeled inference require their own policy flags.
Literal declared source/destination/map paths require identifiers, raw values and
customer-data selection together. Original private/history/custody hashes,
resource/capture hashes, grants, diagnostics, receipt extensions and torn content
remain omitted under every policy. The typed artifact is exact compact JSON plus
LF; its new hash covers only selected support content.

With the installed pinned Windows toolchain:

```powershell
cmake --preset windows-bootstrap
cmake --build --preset windows-bootstrap --target disked acquisition_worker_fault acquisition_case_probe
python tests/evidence/test_acquisition_case.py --probe build/windows-bootstrap/Release/acquisition_case_probe.exe --product build/windows-bootstrap/Release/disked.exe --worker-fault build/windows-bootstrap/Release/acquisition_worker_fault.exe --root .
ctest --preset windows-bootstrap -R '^evidence\.(acquisition_case|case_model|export_model|file_export)$'
```

The test creates actual disposable-file acquisitions, verifies source/copy/map
independently and checks typed support/export bytes. Pure-model alterations are
synthetic; the live writer uses a separate admission-delay fault seam. The
private probe's surrounding case/source output contains original metadata and
paths and is not a redacted support payload.

These private case/export libraries remain unlinked from `disked.exe`.
Public `evidence.export` admission still needs exact case/source-resource and
prepare/execute contracts, bounded service effects and cancellation/late-result
behavior, and actual CLI/stdio/GUI/TUI/shell parity. Authenticated custody, current
acquired-image verification, other platforms and physical qualification remain
open. DE-W034 and DiskEd 0.1.0 remain incomplete.

The [joint admission proposal](../spec/catalog/acquisition-case-export-prototype.json)
now binds case revision, current metadata resources and exact selected output
effects together. It requires explicit case-read, report-write and host-effect
declarations, reconstructs the reviewed inputs, and checks the held source around
each native effect step. Source applicability and output effects have separate
outcomes: a late source change cannot erase an actual verified output or receipt.
These are synchronous observations, with native qualification retained separately.
Durable worker/store identity, bounded service/cancellation/late results, public
descriptor syntax and frontend integration remain required before availability.

The private report worker binds an additional owned execution store and exact
worker/producer/host generations. Its durable operation, attempt and worker
identities support private reconnect and cancellation; failed terminal writes
retain uncertain state and created output. This does not yet admit public
`evidence.export`: common service/watch and actual frontend contracts/journeys
remain pending. See the canonical report-worker prototype profile.


The provisional `evidence.export` prepare/execute syntax and common inward
service contract are defined in the [export command profile](../spec/catalog/export-command-prototype.json)
and closed parameter/result producer schemas. The actual command remains
planned/unavailable in the product composition. Private request/parser/form
checks do not qualify real frontends. Operation watch, bounded product admission
and actual CLI/stdio/GUI/TUI/shell journeys remain the next availability gate.
Preserve exact native case/effect/store/code bindings and separate disclosure
selection from the private review/receipt routing metadata.


Report operation observation has its own [provisional watch profile](../spec/catalog/report-watch-prototype.json).
It binds the retained request/attempt/worker, validates /2 rows and reconnect
cursors, and separates completed observations from logical effect outcomes.
Finite follow and queue closure do not own the worker lifetime. Product report
IDs are explicitly unavailable in the existing composition; private protocol/
parser/reader tests are prerequisites for actual bounded frontend admission.
