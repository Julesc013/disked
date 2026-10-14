# Exact-source Windows worker lease and exFAT command qualification

Source `75689f9799c91315f6cba4d876c8a9e46ef7a704` builds as
`0.1.0-dev.57` in a clean sparse checkout with all registered/build/native-test
inputs. The fresh full suite of 141 native groups, 48 header compilations and 242 tooling tests
with two skips pass. Logs, commands, source/artifact hashes, import/dependency
observations and verified context retain the actual scope. Separate four-case
ambiguous-media CLI/GUI/TUI/shell checks pass at the same executable/revision.

Four unassociated kernel markers lease cooperating worker slots; existing
private jobs enforce 128 MiB per process. Controllers preserve their two-process/
256 MiB job and independently lease children. Caller ancestry is retained;
legacy/prepared conflicts refuse, and a fifth slot cannot restart an unresolved
operation. Acquisition/report/verification job names persist through query-only
inherited handles so the tests inspect actual private enforcement.

This qualifies the selected Windows ordinary-image development prototype,
not physical storage, installation, other platforms, hostile same-user isolation,
public ABI, owner acceptance or the complete original0.1.0 scope. The prior
60376a0e full failure and all selected working failures remain historical evidence.

The first ambiguity supplement lost the JSON prefix from its owned 1,000-row console buffer. The retained bounded overlay uses 4,096 rows/983,040 characters. Same parsing, waits, review, restored host state and source/artifact checks pass. Original failed capture, overlay origin/hash and actual final results remain retained. CompareObjectHandles is resolved dynamically from loaded kernelbase.dll; successful child/ancestry tests exercise it on the tested host. Dumpbin records static imports.

Reproduce from the repository root:

```text
python .aide/evidence/2026-10-14-worker-leases-qualified/reproduce-qualified.py --revision 75689f9799c91315f6cba4d876c8a9e46ef7a704
python .aide/evidence/2026-10-14-worker-leases-qualified/check-ambiguity-frontends.py --campaign .aide-local/worker-leases-exact-75689f97
```

Use a fresh campaign path; the runner refuses an existing one. The supplement reads its retained sibling console fixture and imports original console helpers from the exact checkout. This retained invocation also passed all four cases; its log/results are reproduction-supplement.*.
