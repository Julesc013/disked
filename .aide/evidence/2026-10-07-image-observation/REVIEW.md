# DE-W024 captured-map local review

Reviewed source `5e033f206eb241c157e211d454a1fed6a3c9338d` against `c20b4d7e48fbc5423d351a20ec9a76b509581ef4` and the DE-102 private integration
contract. This is implementing-agent review under the continuation grant. W024
remains active; its file capture and actual frontend parity criteria are not met.

- Input geometry and multiplication are checked before any region conversion.
  The 16 MiB prefix cannot exceed declared capacity. Regions use checked named
  extents; a missing/truncated block supplies only actual available bytes.
- Every eligible MBR extended root has bounded progress. GPT headers are read at
  independent fixed locations with per-candidate entry/array budgets. All raw
  views and entry workspace outlive comparison and report construction. No reader
  pointer escapes in the owned JSON value, and input remains immutable.
- Summaries cover complete bounded walks/arrays even where detail rows are omitted.
  Exact omitted counts are computed before moving containers. Truncated/unsigned
  headers have no fabricated decoded fields; invalid array shapes have no derived
  zero-byte size masquerading as a calculation. Raw records and names remain exact.
- Capture completeness and source consistency are separate. Reports bind byte
  coverage, geometry and digest while explicitly retaining unknown source
  consistency. Comparison retains both candidates without choosing or repairing.
- Native cases include ownership/lifetime checks, resource maxima, undecoded fields,
  independent corpus assertions and non-512 blocks. All 38 native regressions pass
  on clean source. This does not establish file consistency, frontend image parity,
  hardware safety, historical-platform support or owner acceptance.

Continue the remaining W024 integration under the existing local grant. The owner
acceptance ledger and storage/release gates remain unchanged.
