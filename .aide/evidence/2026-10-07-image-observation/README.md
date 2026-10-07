# DE-W024 private map-observation checkpoint

Source `5e033f206eb241c157e211d454a1fed6a3c9338d`, base `c20b4d7e48fbc5423d351a20ec9a76b509581ef4`. This is a locally reviewed **partial W024**
deliverable: one private C++14 integration over the existing C90 readers. It
consumes a bounded immutable byte prefix with explicit u64 geometry, returns owned
observations and performs no file I/O. The product remains 0.1.0-dev.17 with its
existing fake commands; image.inspect and table.verify are still unavailable.

Seventy-one native integration cases pass from a clean clone, along with all 38
native CTest groups. The integration reuses 35 independent image recipes and adds
empty/truncated prefixes, raw-byte retention, 512/4096-byte units, geometry/input
limits, incomplete sources, omitted-detail validation, conflicting GPT copies and
original invalid/control-character names. A maximum workload reaches four 128-visit
EBR budgets and validates both active GPT arrays while the report remains within
48 KiB. Reports retain exact byte coverage and digest, reader statuses and findings,
both candidates, omitted detail counts and source_consistency=unknown. Missing or
undecoded metadata is not replaced by fabricated decoded zero values.

The probe overwrites and frees its input before serializing the returned report;
the result contains no surviving borrows. The captured byte digest is not a source
identity, snapshot or proof that an underlying file stayed coherent during capture.
No format/copy selection, repair proposal or filesystem-health conclusion occurs.
FINDINGS.md retains the initial evaluation-order bug and the zero-geometry test
correction; the parser readers were unchanged.

The full spec suite ran 171 tests (169 pass, two existing Windows symlink-privilege
skips). Structural, manifest/context and passive AIDE validation pass; live AIDE
was not run. Actual commands, source/build inputs, executable/library hashes,
imports, launch output and native/spec logs are retained. Clean artifacts are in
`.aide-local/artifacts/DE-W024-observation-5e033f20/`; their identities are in
`reproduction-5e033f20/clean-results.json`. This Windows-host evidence does not
qualify other platforms or a production image provider. Owner acceptance is absent.

Reproduce with `cmake --preset windows-bootstrap`,
`cmake --build --preset windows-bootstrap`, and
`ctest --preset windows-bootstrap --output-on-failure` on the pinned installed
toolchain. The individual command is
`python tests/frontend/test_image_observation.py --probe build/windows-bootstrap/Release/image_observation_probe.exe`.
No model service participates in those build/test commands.

Continue DE-W024 with an explicit ordinary-local-file capture adapter, source/geometry/consistency evidence and bounded shared image commands. Define file/path limits and exact responses before handler admission; test actual CLI/TUI/GUI parity and delayed/denied/changed source behavior. The private map observation is qualified only for captured bytes, not a coherent live source. Keep physical devices, mounting, elevation, customer data, installation, owner acceptance and release separate; preserve model-independent runners and interruption records.
