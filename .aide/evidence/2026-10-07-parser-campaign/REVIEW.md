# DE-W023 local implementing-agent review

Reviewed `c0e52fd383cd9a776219ce2d1c3b1e7204fd1624` against `7ea2d5f5bda17eae35d655b73b5432b1d1d31aaf` and the pre-implementation campaign contract.
This is the implementing agent's review under the explicit continuation grant,
not owner acceptance or independent safety qualification.

- Corpus inputs are generated ordinary files with declared sizes and hashes.
  Native probes receive bounded views and expected findings defined independently
  of the external tools. Primary/backup candidates and incomplete EBR walks remain
  distinct; disk GUIDs participate in projection comparison.
- External commands always name a checked fixture and observation-only options.
  UID, tool/library/package identities, time/output/memory limits and before/after
  hashes are recorded. Invalid output, refused operations and disagreements remain
  evidence. Invalid UTF-8 retains exact hex; escaped display never substitutes for
  the original bytes. Timeout remains active after a child closes both streams.
- The mutation harness compiles the unchanged C90 readers with fatal ASan/UBSan.
  Test-only CRC reconstruction reaches entry paths without changing the readers.
  Bounds and immutable-input checks are independent of instrumentation. Intentional
  sanitizer/invariant failures and replay reconstruction demonstrate that a broken
  campaign cannot report success solely because its process terminated.
- The clean checkout reproduces 35 native cases, 14 adapter controls, 162 external
  observations and 10,035 mutation/seed cases. Twenty discrepancies are retained
  and triaged; none demonstrates a production reader defect in this campaign.
  Raw gcov records identify remaining unexecuted branches. No exhaustive,
  coverage-guided, historical-platform or source-stability claim is made.
- Exact native build-input equality supports W022 probe reuse. The new test code
  and sanitizer build have their own clean source identity. Full spec tests and
  clean structural/manifest/context checks pass with explicit skips retained.

Both W023 acceptance criteria (reproducible malformed-input corpus/adapters and
retained version-bound disagreements) are met locally. Proceed to W024 under the
grant. The broader programme, owner acceptance and storage/release gates stay open.
