# Capture-local exFAT namespace qualification

The private DE-W073 implementation is locally qualified for development integration
and owner review. It owns a validated immutable volume upcase map, exact supplied
directory records and UTF-16 units, NameHash/full comparison, ambiguous/incomplete
lookup and finite budgets. It does not open sources or confer stream/effect authority.

- `qualified-2545d078/`: clean full 142 native groups/50 standalone headers,
  242 tooling tests/two skips, manifest/context, imports, artifact/source identities.
- `qualified-84d0c227-word-bounds/`: exact corrected private probe and unchanged
  six-library kernel; x64 and Win32 each pass303 namespace cases/13 integer-boundary
  cases/two headers. Old-probe-only Win32 baseline measures 11 conversion mismatches.
- `working/`: initial dirty build, omission-count failure and corrected regressions.
- `word-bounds/initial-harness-failure.log`: initial ZERO_CHECK runner failure before
  compilation. Corrected closure policy is explicit, with no weakening of tests.

`REVIEW.md` is implementing-agent review, not independent qualification or owner
acceptance. Coherent stream/tree/content/ValidDataLength, held-source/worker/frontend,
other platform/storage, physical, writer/recovery and original full 0.1.0 gates remain.

Reproduce the full campaign with `reproduce-qualified.py --revision
2545d078b8dd6fc5335cf38314013be3d4c2fc7c` from a fresh repository campaign location.
Then use the word-bounds runner as documented in `word-bounds/README.md`, selecting
revision `84d0c227eaaa1a76ac318aeb70e2da22a641698e` and a new output directory.
Retained source/configuration files are evidence; the reproduction runner derives
new paths and hashes actual inputs rather than executing historical absolute paths.

Setup's latest retained PR237 head082d6c7f has six successful checks and a failed
native-windows job. Raw status/log evidence remains separate from DiskEd's tests.
No Setup code was changed or independently qualified here.
