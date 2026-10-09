# Setup package fixture development

The first DE-W060 slice maps DiskEd's already built portable bytes into pinned
Universal Setup product/recipe schemas and verifies ordinary fixture extraction.
It is independent of actual software installation. The full work unit and owner
acceptance remain open.

Clean packaging source `e1683b1` passed 22 fixture tests, independent archive and
extraction equality, occupied-root retention and actual original/extracted
launches. The dev.36 executable retains its separately qualified native source
`ec30be78` and exact SHA-256; it was not rebuilt by the packaging test. See the
[retained review](../.aide/evidence/2026-10-10-setup-fixtures/REVIEW.md) for commands,
hashes and remaining qualification. No live Setup mode is inferred from this.
The provisional recipe explicitly reports `maximum_tested_reader: not_run`;
the minimum reader is a requirement, not a test receipt.

The [binding guide](../release/bindings/universal-setup/README.md) gives exact
commands. The [profile](../spec/catalog/setup-fixture-prototype.json) owns expected
behaviour; [source-lock.json](../external/universal-setup/source-lock.json) owns
exact upstream identities. Only unmodified MIT schemas and license text are
vendored. No upstream scripts, runtime or zlib are included or executed.

Assemble uses independently enumerated staging. Verify/extract require the
original separately selected inventory and actual native build-info, checking
both typed schema conformance and agreement between fields. The recipe has no
mutation selection. Customer-style data in tests is generated, externally
owned and preserved on occupied-root refusal. Interrupted output is retained.

The source pin is a local inspected revision; no remote branch freshness claim
or stable adoption is made. Source-only SDK observations do not establish live
ABI compatibility. Native SDK consumption, install/repair/update/move/uninstall,
state compatibility, active-generation interlocks, other targets, signing and
publication need subsequent authorized evidence. Root-level schema permission
for per-user or machine topology does not make those modes available.
