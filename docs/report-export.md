# Native support-file export development contract

DE-W034's private exporter accepts a typed case support projection, freezes its
exact compact JSON bytes plus one LF, and binds the payload, disclosure policy,
destination/parent identity and producer file identity/digest in an immutable
definition. It never exports the full private case or original custody hashes.
The [proposed profile](../spec/catalog/report-export-prototype.json) owns the
encoding, effect, resource, verification and public-admission boundaries.

The shared [ordinary-file path profile](../spec/catalog/ordinary-file-path-profile.json)
owns ancestor coordination for this adapter and image/acquisition consumers.
Preparation observes ordinary local paths, pins ancestor and executable handles,
checks absence and records identities. It creates nothing. Ancestor handles
require directory list/read access with write/delete sharing
denied; metadata-only handles do not prevent rename on the tested host. Failure
to acquire those stronger handles refuses preparation.

Execution requires the exact definition digest plus explicit report-write and
host-effect flags. The
native session executes once. It creates a new file with exclusive sharing,
revalidates resources, writes bounded chunks, confirms the file flush API and
reads every byte back. Existing outputs, reparse/device/network/stream paths and
ordinary-profile aliases refuse. There is no overwrite, force, automatic retry,
resume or deletion of incomplete files.

Submitted, acknowledged-written, read and verified bytes differ. A failed write
acknowledgement leaves the written count unknown; a failed flush remains uncertain.
Cancellation before creation creates nothing. Cancellation or failure afterwards
retains the output and cannot report completion. Only proof that creation never
occurred allows a creation failure to report `not_created`; other failures retain
uncertainty. A completed report establishes exact artifact readback within the
observed file/producer generation. It establishes no source preservation,
authenticated custody, physical backing or power-loss persistence.

The output file contains only the selected support payload. The surrounding
definition, receipt and routing metadata contain paths and producer identities;
they are not redacted support exports. Fixture actor/code/target declarations are
not authenticated facts. All underlying case claims remain qualified as before.

With the existing pinned Windows toolchain:

```powershell
cmake --preset windows-bootstrap
cmake --build --preset windows-bootstrap --target report_export_probe file_report_export_probe file_report_export_fault
python tests/evidence/test_export.py --probe build/windows-bootstrap/Release/report_export_probe.exe --root .
python tests/evidence/test_file_export.py --probe build/windows-bootstrap/Release/file_report_export_probe.exe --fault build/windows-bootstrap/Release/file_report_export_fault.exe --root .
ctest --preset windows-bootstrap -R '^evidence\.(export_model|file_export)$'
```

Tests use fabricated observations and owned disposable report destinations. The
fault binary alone includes controlled API/cancellation/coordination seams. File
bytes and hashes are checked independently in Python after native completion;
creation races and owned-child cuts retain observable file facts. Injected faults
and process termination are not actual full-filesystem or power-loss tests.

The normal Windows image prototype now links the exporters and dispatches
`evidence.export` for recorded acquisition and joined verification support.
The canonical command catalog owns its availability and provisional contract
status; the [joined frontend profile](../spec/catalog/joined-report-public-prototype.json)
owns its selected scope. Later programme evidence covers actual private workers,
bounded waits and frontend journeys; the older synchronous commands above remain
only a fixture floor. These results do not establish authenticated custody,
physical association, power-loss persistence or other platform qualification.
DE-W034 and the full original DiskEd 0.1.0 scope remain incomplete.

The separate report-worker fault probe now offers bounded preparation phase
observations, including streamed prefixes for stalled callbacks. Normal products
have no trace mode. Inputs are copied before trusted instrumentation; a callback
cannot replace the selected case, collection, policy or destination. The fixture
keeps its original twelve/eighteen-second timeouts and retains raw partial output
on failure. A controlled pause verifies prefix retention and actual owned exit;
it does not reproduce the earlier spontaneous stalls or diagnose their cause.
[Diagnostic evidence](../.aide/evidence/2026-10-15-report-prepare-phases/README.md)
retains both failed and passing regressions.
