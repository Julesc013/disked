# DE-W060 source mapping and payload fixtures

Base: `3de808c705c6abb395e507dc275a48aac174e666` on `goal/disked-0.1.0`.
The existing programme grant covers local fixture implementation, tests and
commits after agent review. It does not grant owner acceptance, real
installation, storage privileges, signing, publication or remote writes.

The source lock selects exact locally available Setup
`2e64f654b370f500ddbab45ae097df63352c3c25` and optional Launcher
`e61782bc6d71fb91efa960e9033738b5a44fece3`. No remote freshness claim is made.
Twenty-two selected upstream blobs, including five retained unmodified schemas
and their MIT license, are compared with their exact Git/blob/size/SHA identities.
Relevant docs and policy/API source portions were read, not a full upstream
runtime audit. No upstream script, CMake build or runtime is executed.

The authored profile preceded implementation. Fixture tests distinguish native
evidence from their synthetic non-executable payload. Independent expected
inventory and build-info are supplied for assemble, verify and extraction;
internally recomputed hashes cannot redefine expected bytes. Occupied roots and
failed writes are preserved. No installed-state record or fallback installer
exists. Existing native input hashes are unchanged; native build qualification
is reused explicitly at `ec30be78ba9e9f61dc578ff67b9d0af186166145`.

Reproduction uses the exact previously qualified dev.36 `disked.exe`, SHA-256
`ac2721db6b26231ed52c31742f472063bed8c7bd88ceb8f14690eb37dd63994d`, and its
original retained native evidence. `reproduce.py` checks those identities,
creates a clean checkout of the selected packaging source, performs actual
original/extracted launches, verifies exact archive/extraction equality, runs
occupied-root and unsupported-mode controls, and retains commands/logs/hashes.
It does not rebuild or rerun the unchanged native suite.

```text
python .aide/evidence/2026-10-10-setup-fixtures/reproduce.py --source-revision 92d72bb7a7a1b312b74db9dcbeccba9bdda94548 --exe .aide-local/artifacts/DE-W034-joined-public-ec30be78/disked.exe --native-evidence .aide/evidence/2026-10-10-joined-report-public/reproduction-ec30be78/clean-results.json --output NEW_OUTPUT_DIRECTORY
```

This is fixture package conformance/equality, not live Setup ABI, lifecycle,
state compatibility, authenticity, installation, release, additional target or
owner acceptance. No customer data or physical devices enter the tests.

During development, the structural checker refused an external-root Markdown
link in the owning spec. It was changed to the canonical source-registry link;
the checker was not relaxed. The failure appeared in tool output before raw
logs were established; it is disclosed here, not represented as a retained
raw failure log. Subsequent exact-source logs determine validation claims.

Clean qualification at `92d72bb` passed: 22 fixture tests, 213 tooling tests
passed plus two skipped, 1,035 structural checks, actual original/extracted
launches and exact byte equality. Raw commands/logs and independent inputs are
under `reproduction-92d72bb/`. [REVIEW.md](REVIEW.md) records the implementing-agent
review and limits. `inventory.json` binds retained evidence and seven local
artifacts. The Windows checkout warning at initial source `5248a8a` prompted an
explicit license-byte preservation rule before clean qualification.
