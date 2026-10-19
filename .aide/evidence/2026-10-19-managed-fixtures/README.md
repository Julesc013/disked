# Managed fixture routing for DE-W105

This change moves existing native test fixtures into the source-bound managed
temporary parent. It does not implement a new storage operation or qualify a
native campaign. The host runs only bounded coordinator tests; native DiskEd
and compiler tests remain in the guest.

`migration.json` identifies all 35 migrated scripts and 38 replaced parent
expressions, original/result SHA-256 values, unchanged test method names and
assertion counts. An AST literal inventory verifies that fixture byte, number
and string expectations are preserved, excluding the declared source-parent
resolver removal and the inserted import-path constants. Existing prefixes,
deadlines and recovery/process-retention conditions remain intact.

Simple `TemporaryDirectory` calls use the existing `managed_directory` helper.
Custom lifetime helpers keep their failure retention and process-exit checks;
only their parent changes. Three source-containment assertions now check the
verified managed parent. Timeout diagnostics also stay inside that parent.
The input dependency registry binds the shared helper for each affected script.

The recovery harness's outer test directory is managed. Its two lifetime tests
inject that owned directory into the restoration helper, preserving their
original dependency-retention and confirmed-exit assertions. Five existing
harness tests passed in an initial bounded coordinator run. The full specification
suite then passed 253 tests with two expected skips and 1,325 structural checks.

A follow-up audit found the artifact-staging test's real output directory also
used `.aide-local`. Its parent, constructor and cleanup assertion now use managed
scratch. That file and the recovery harness appear in `additional_migrations`.
Their existing test names and content/rejection oracles remain intact. The full
253-test receipt predates this final artifact-path adjustment; fresh affected
bundle, tooling, artifact and recovery tests plus index/check/manifest results
are retained separately in `fixture-checks.json`.

`migrate.py` is a one-off transformation against the original source revision,
retained for review. Do not rerun it on already migrated sources. It never
executes native fixtures. The old differential campaign remains a DE-W106
repair, and must not be run using its obsolete output recipe.

The ordinary-token primitive proof and complete current x64 qualification are
still required. No test result here supplies owner acceptance, a release, or
physical-storage authority.
