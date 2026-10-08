# W033 Windows file-acquisition component checkpoint

Source `0f6552a95f04d66dfa94d34b96d922b82466d687`, work base `655a7d91b0fda453b74a4ea30c03635c7fda59c4`. The private provider is implemented and
verified on the recorded Windows 10 Enterprise x64 host, under an ordinary Jules
process. DE-W033 remains active and incomplete. The public `image.acquire`
command is unavailable; this is neither a complete acquisition product feature
nor all DiskEd 0.1.0, owner acceptance or physical/release qualification.

The adapter holds ordinary source, parent and code generations; preparation
creates no outputs. A separate exact-definition grant gates the source read,
destination/map writes and host effects. Exclusive normal-file sharing and
CREATE_NEW protect owned output files against conventional local races. Partial
outputs remain; missing headers do not authorize cleanup or a blind restart.

Bounded raw chunks, explicit substitution, canonical LF-framed maps, intent/flush/
readback/checkpoint ordering and matching-generation resume use the inward-facing
provider-independent core. Resume rejects unexplained growing-file suffixes
before repairing a torn map or replaying an effect. Receipts distinguish expected
length, actual held-handle size observations, successfully returned-call counters
and uncertain partial effects. Hashes detect changes but do not authenticate maps.

A fresh checkout at this exact source passed all **42 native CTest groups**,
**126 ordinary-file acquisition checks**, **208 core checks**, and **171 spec
tests** (169 passed; two existing symlink-privilege skips). Nine retained child
observations record both live state and terminal state; seven use owned-child
termination, and two continue via test-only release files. Source/manifest/context
and generated freshness checks pass. Native build identity binds 202 input hashes,
MSVC 19.44.35228.0, SDK 10.0.19041.0 and the static Release runtime. Product and
three probe import/header/dependency observations, actual launch and discovery,
eight local artifact hashes and exact commands are retained in
`reproduction-0f6552a9/clean-results.json` and `commands.json`.

To reproduce from an ordinary Windows checkout with the recorded toolchain:

```powershell
cmake --preset windows-bootstrap
cmake --build --preset windows-bootstrap
ctest --preset windows-bootstrap
python tests/images/test_file_acquisition.py --probe build/windows-bootstrap/Release/file_acquisition_probe.exe --fault build/windows-bootstrap/Release/file_acquisition_fault.exe --root .
python tests/images/test_acquisition_pipeline.py --probe build/windows-bootstrap/Release/acquisition_probe.exe --root . --validate-schemas
```

The last command uses the dependencies in `spec/tools/requirements.txt`.
Fault hooks exist only in the separately compiled probe; its test grants do not
constitute product authorization or owner acceptance. Input files are generated
inside an owned temporary folder. No device opens, mounts, elevation, customer
data, installation, signing or remote writes occurred.

CREATE_NEW races, real sharing and DACL refusal, Unicode, chunk boundaries,
controlled API failures, corrupt/incomplete maps and observed process interruption
are covered. Injected space/read/flush errors do not qualify actual thin backing,
disconnection or failing media. Per-file FlushFileBuffers/readback and kill/wait
tests do not prove power-loss survival, authenticated host identity, complete
physical aliases, snapshots, filesystem health, restore readiness, other hosts
or OSes. Capture intervals/per-attempt provenance and the durable public/frontend
lifecycle remain integration work. See FINDINGS for retained failures and
[DE-103](../../../spec/operations/acquire-image.md) for the private contract.

Continue DE-W033 with acquisition command/admission and bounded asynchronous operation lifecycle over the reviewed private file provider. Complete capture intervals and per-attempt provenance, exact-plan effect grants and operation/worker epochs in the owning contracts before public behavior; verify CLI/stdio/GUI/TUI/shell parity, cancellation at checkpoints, reconnect, hangs, late results and retained partial outputs. Keep physical access, elevation, customer data, power-loss qualification, other platforms, owner acceptance and release/publication at their separate gates. Do not broaden failing-media rereads or discard corrupt evidence.
