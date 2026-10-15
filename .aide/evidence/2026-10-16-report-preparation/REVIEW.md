# Implementing-agent review: partial preparation-timeout correction

DE-W034 corrective slice, base `46b7dba5ef68ae0abb1bcc415b00c0856af1573f`.
Source `5ae50aeef3a92a29a593daff3ca37a1fa1d6d880` is pushed to dev.
The existing local implementation/test/repair grant applies to generated ordinary
files and owned unprivileged processes. No owner/physical/elevation/customer-data/
installation/signing/release authority is supplied by this review.

The delayed-call investigation exposes a real label defect. A pending explicit
preparation was reported as export-execution. The command profile records the
expected correction before evaluation; the shared service now emits
export-preparation for this phase. Execution and operation-observation labels,
selected routing and fixed waits remain. No admission/effect/exit claim follows.

Working native tests pass both unjoined and joined product frontend groups.
Their new controlled stdio case blocks preparation through the original four-second
wait, requires the corrected unknown result, leaves discovery responsive, and
proves selected output/state files remain absent. On release a fresh request
returns preparation for its own destination, with no implicit execution. Existing
execution-timeout/single-effect/reconnect and CLI/GUI/TUI/shell journeys remain.
The private test initially fails because it expects an audit wrapper around a
direct probe response. Correcting that test lookup preserves all expectations;
the failure and corrected private-group pass are retained.

Clean exact-source qualification DOES NOT PASS: three of four groups pass
(frontend.product_export, evidence.export_commands, evidence.report_watch).
frontend.joined_report fails in its fixture's image.acquire execute call before
report preparation, returning unknown/6 with request_wait_expired and no operation
ID. This broadens the latency investigation beyond report preparation. No native
group is retried to obtain a pass and no writer is re-executed.

Read-only retention of the failed fixture finds a completed65,537-byte copy with
equal source/destination SHA256 and a hash-linked terminal record about10.186
seconds after worker creation. The operation ID is retained in the existing
request file although absent from the timed-out frontend response. Current
process lookup is recorded separately; a terminal receipt or absent PID is not
used as an actual historical exit observation. The source/copy/map/request/records
remain retained, and no recovery dependency is deleted.

Independent validation continues after the failed native command without running
it again. All242 tooling tests(two skipped), structural/index/source-map,
strict build/include boundaries, manifest/context and source freshness checks
pass. Actual compiler/SDK/runtime, executable hashes and PE/import observations
are retained. All1028 registered/build inputs remain unchanged in the clean
checkout. These independent results do not clear the failed native campaign.

The original11e6f625 executable also produces an unresolved unjoined preparation
on sample13 of a diagnostic run, already slow before dump collection. That dump
is potentially intrusive and has no usable thread context: no original cause is
inferred. Direct preparation1000 and later prewarmed CLI200 plus2000 samples are
fast, which does not explain the failure. A controlled six-second sleep verifies
the dump reader against live thread contexts. Raw dump memory stays local with
actual file-length/hash references; the original helper's bytes field is a final
file pointer, not the length. The correction is recorded without changing the
retained raw observations. Offline address scanning is not a stack unwind.

A separate controlled CLI timeout emits the corrected preparation result and
exits in4.04 seconds while its provider callback remains blocked. It rules out
an unconditional wait for pending callbacks at CLI exit in that controlled case,
not the spontaneous delay. Original copy/map birth timestamps are also retained;
they are observations rather than a historical parent stack or causal diagnosis.

Available result: a tested phase-label fix with partial clean-source regression
evidence and a more precise shared acquisition/frontend latency and routing issue.
The joined controlled case passes only in the separately retained working run;
it is not relabelled as a clean-source pass. DE-W034, W075/main, original
all-platform/storage0.1.0, owner, writer/recovery, physical, Setup and release
qualification remain incomplete.

Next: preserve reviewed store routing when acquisition execution returns unknown;
capture the shared parent/worker boundary if a delay recurs, and reconcile only
by recorded identities without re-executing an uncertain writer. Keep original
deadlines and test expectations. Original NTFS/frontend/metadata/namespace work
also remains; no further general architecture review is required.

Diagnostic API/layout references: [MiniDumpWriteDump](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/nf-minidumpapiset-minidumpwritedump),
[thread record](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/ns-minidumpapiset-minidump_thread),
[module record](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/ns-minidumpapiset-minidump_module).
