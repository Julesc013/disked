# DE-W056 partial content integration

Development observations at base 4905ae03, with working-tree source changes.
The source-bound supplied-reader cursor passes 39 independent cases/nine methods;
the held ordinary-file adapter passes 8 cases/four methods. These include FAT12/
16/32, 33,000-cluster file bytes, multisector/noncontiguous mappings, exact source
offsets, page chains, slack exclusion, cycles, metadata/epoch changes and native
double reads. Native content selection accepts only a key observed in that
adapter's latest traversal page. Cancellation preserves a historical prefix;
disagreement does not admit content. Generated source hashes stay unchanged.

The original tree-worker and shared frontend suites also pass. The full tooling
suite ran 238 tests: 236 passed and two were skipped. Selected content
and native headers compile; the source map covers 238 files; dependency checks
pass. The first test-harness failure is retained: string-valued budget comparison
and an allocated zero-length record expectation contradicted the existing decoder.
The independent source-offset oracle and data pattern were then strengthened.
An initial dependency check ran before the generated bootstrap header existed;
generating that header restored the normal check, without relaxing boundaries.

This is a partial backend prerequisite, not full recursive extraction. Destination
creation, immutable effects/grants, metadata ledger/name/time policies, interruption
and complete exact-source qualification remain required by DE-W056. No physical,
other-host, owner, production or full 0.1.0 qualification is claimed. Artifacts and
logs here describe dirty development, not a clean frozen native campaign.
