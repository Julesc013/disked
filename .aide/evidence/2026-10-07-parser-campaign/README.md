# DE-W023 parser campaign evidence

Source `c0e52fd383cd9a776219ce2d1c3b1e7204fd1624`, base `7ea2d5f5bda17eae35d655b73b5432b1d1d31aaf`. This checkpoint adds generated ordinary-file
recipes, native/external observation adapters and a deterministic mutation runner.
Production readers and all 176 native build inputs are unchanged from W022; their
clean Windows probes were reused after checking every recorded input hash. The
sanitizer readers were freshly compiled from this clean source on Ubuntu WSL2.

The clean campaign passes 35 expected native image observations, 14 adapter
controls and 10,035 cases with fatal AddressSanitizer and UndefinedBehaviorSanitizer.
Separate intentional faults prove each detector, the campaign invariant and the
exact failing-input replay path. Logs, versions, compiler/library/input hashes,
coverage and the generated corpus manifest are retained under
`reproduction-c0e52fd3/`. Reproduction commands are in
`tests/differential/README.md`; the outer and inner receipts record actual commands.
Instrumented executables and the replay-control image are retained locally at
`.aide-local/artifacts/DE-W023-c0e52fd3/`, with hashes in `clean-results.json`.

Installed sfdisk 2.39.3 and 2.41, plus sgdisk 1.0.10, produced 162 bounded
observations under UID 65534. Ninety-two table projections were compared, retaining
20 discrepancies. Initial runs retained 19 because disk GUID was not yet compared.
The final additional discrepancy is sgdisk's generated in-memory GUID on the
both-bad-CRC fixture; it is not evidence of a file write or a DiskEd repair.
No comparison selects a winner or revises the expected native findings. Every
fixture remained byte-identical after each external command. Exact package source
versions are recorded; full upstream source bytes were not independently rebuilt.

Coverage is measured, not exhaustive: GPT gpt.c executed 168/168 instrumented
lines and 179/256 branches; MBR 104/116 lines and 92/146 branches; EBR 70/73 lines
and 66/100 branches. Raw per-line/branch records also show uncovered primitive
and encoding paths. Existing unit/property evidence remains separate. This is
deterministic seeded mutation, not coverage-guided fuzzing; an installed libFuzzer
runtime was not found in the inspected locations and that campaign was not run.

The specification suite ran 171 tests: 169 passed, two existing Windows
symlink-privilege cases skipped. All 904 structural checks, manifest/context
freshness and passive AIDE validation of 36 records passed; live AIDE was not run.
FINDINGS.md preserves the initial control/setup failures, stale-index failure and
coverage-summary correction. Tests were retained and defects repaired.

The local bounded deliverable is reviewed, while canonical status remains
needs_review and the owner acceptance ledger remains unchanged. Native W022's
37-group result is reused evidence, not a new W023 native CTest run. Historical
platforms, coherent source capture, product image-provider integration, physical
storage and independent safety/release qualification remain separate. The whole
0.1.0 programme is still active.

Implement DE-W024 bounded read-only raw-image capture, typed verification observations and shared frontend dispatch over generated ordinary local files. Define capture consistency, path/resource limits and exact diagnostic/exit behavior before evaluating code. Preserve both GPT candidates, finite EBR coverage and source identity; no mounting, physical devices, elevation, customer data, installation, writer admission or release. Continue local tests/review across slices under the grant; owner acceptance remains separate.
