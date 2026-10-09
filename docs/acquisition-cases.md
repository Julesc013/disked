# Recorded acquisition cases

The native case reader captures an explicitly selected acquisition
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

The dev.31 ordinary-file composition selects `evidence.export` and exact report
operation observation through the shared asynchronous request service. The
authored public registry remains proposed/planned; product discovery separately
reports the implemented prototype and its provider. This admits no stable ABI,
authenticated custody, current acquired-image verification, other platform or
physical-storage qualification. DE-W034 and DiskEd 0.1.0 remain incomplete.

The [joint admission proposal](../spec/catalog/acquisition-case-export-prototype.json)
binds immutable case revision, current metadata resources and exact selected
output effects. The [export command profile](../spec/catalog/export-command-prototype.json)
owns preparation/execution and disclosure semantics. Preparation creates no
files. Execution requires the exact reviewed wrapper digest and four independent
case-read, report-write, store-write and host-effect grants. Source applicability
and observed output effects remain separate; a late source change cannot erase
an actual output or receipt. The output is created without overwriting.

The same executable's report role receives four inherited capabilities, no
standard handles, and the selected bounded worker job. Retained /2 history binds
operation, attempt, worker, reviewed definition and producer/host/store identities.
Cancellation request persistence is distinct from its later worker observation.
An absent terminal record remains unknown alongside actual output; no timeout
permits restart or automatic dependency deletion.

The [watch profile](../spec/catalog/report-watch-prototype.json) owns report
inspect/cancel/watch selection, row/progress validation, events and exact
sequence/digest/epoch reconnect. Finite follow and queue closure do not own the
worker lifetime. Historical compatible observation does not regrant old code
writer authority. One occupied product request slot survives its four-second
wait timeout; cached commands remain usable and late results are not reissued.

The same service is selected by CLI, stdio, Win32 GUI, native TUI and shell.
GUI/TUI/shell review remains inert; a separate submission dispatches the request.
Object editors bind the report definition's 64 KiB/depth/value/string budgets.
Public input envelopes and Windows argv limits are independent, so a maximum
private definition need not fit every transport. Report events and replies use
their explicit finite quotas and escaped display budgets; rendering grants no
storage authority. Four-second waits bound intentional waiting, not OS API latency.

With installed pinned tools, the actual frontend journey test is:

```text
python tests/frontend/test_product_export.py --product build/windows-bootstrap/Release/disked.exe --fault build/windows-bootstrap/Release/disked_report_test.exe --root .
```

It checks real generated acquisition/report bytes, all five frontend
prepare/execute paths, reconnect/streaming, rejected grants and a private named
observer gate across request timeout. Private fault controls are absent from the
product. Retained build/source/host/import evidence is still required for each
qualification; tests do not establish physical or power-loss durability.
