# exFAT namespace development evidence

The expected DE-W073 supplied-data contract was recorded before implementation.
`working/` retains the dirty-checkout build, independent namespace and existing
regressions, tooling, header/artifact identities and the initial failure. The
first namespace assertion exposed a C++14 receiver/argument evaluation-order
bug in omitted findings; counts are now computed before moving the findings.
Tests and expected counts were retained. Exact-source full qualification is pending.

Run `python .aide/evidence/2026-10-15-exfat-namespace/reproduce-qualified.py --revision <committed-source-revision>` from the repository root. It refuses an
existing campaign directory. No physical/source access or public namespace
admission is conferred by the supplied-directory results.
