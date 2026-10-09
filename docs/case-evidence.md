# Case observations and custody development contract

DE-W034 currently has a private native case builder for validated fixture health
observations. It records immutable before/observation/after snapshots and an exact
code/case/fixture declaration bound to an ordered hash chain. Recording a snapshot
does not issue a query, observe worker exit, authenticate an operator or prove
that the original source stayed unchanged. The existing collector's unknown,
partial, unavailable, cancellation and outstanding-worker facts remain explicit.

An after record closes collection; it does not certify storage postconditions.
Comparison is a labeled inference about available public fixture fields with
matching declared target/provider/field bindings. It excludes serials, customer
labels and secrets. Missing observations or changed bindings remain incomparable.
Health, source preservation, acquisition consistency and authenticated custody
are separate claims; this builder establishes none of those claims.

The default support payload contains ordinal labels, states and availability.
Explicit policy flags select identifiers, raw values, interpretations and customer
content; category and content permissions are independent. Secret content is
always omitted. Original case/context/fixture and custody digests never enter the
support payload, even with all flags: those hashes could disclose omitted data.
An identifier policy may create a separate chain over the disclosed projection.
That chain is explicitly different from the original custody chain and supplies
no authentication. Public-field comparison is disclosed only with both raw and
interpreted content selected.

The [proposed profile](../spec/catalog/case-evidence-prototype.json) fixes the
private encoding, phase/count/aggregate limits, provenance and disclosure behavior.
Its SHA-256 input uses compact JSON with sorted keys, UTF-8 values, quote/backslash
escapes, and every control character encoded as lowercase `\u00xx`. It is not a
stable public case or production journal format. Failed append leaves old records
and hashes unchanged; budgets reject instead of truncating snapshots.

With the [pinned Windows toolchain](native-bootstrap.md), run:

```powershell
cmake --preset windows-bootstrap
cmake --build --preset windows-bootstrap --target case_evidence_probe
python tests/evidence/test_case.py --probe build/windows-bootstrap/Release/case_evidence_probe.exe --root .
ctest --preset windows-bootstrap -R '^evidence.case_model$'
```

The independent fixtures check exact chain hashes, immutable retention, phase
guards, inference limits, all disclosure combinations and omission of hashes over
private values. The probe handles owned JSON fixtures only and has no file-export,
device, self-test, acquisition or privileged port.

The builder is currently unlinked from `disked.exe`; public `evidence.export`
remains unavailable. The private native report adapter is described in
[report-export.md](report-export.md). Public execution parameters/service admission,
actual acquisition/case integration and physical/platform qualification remain required. DE-W034 and DiskEd 0.1.0 are incomplete.
