# Capture publication independent of owned reader retirement

Exact source `2d753baec32c443e121c462ac9b19fa002edb114` builds proposed 0.1.0-dev.37 on the recorded
ordinary Windows 10 host. All 77 selected native CTest
groups pass; the independent capture reducer campaign runs 16
tests, including publication, partial coverage, old epochs, malformed replies,
duplicate polls and allocation-atomic publication/failure/retirement.

Each x64/x86 lifecycle campaign runs six controllers and six actual owned
injected readers. Together these lifecycle runs make 210
assertions. The existing namespace-worker regression adds 24 controllers and
18 actual readers per architecture, with 232 assertions total.
These finite process counts cover the private campaigns only; the full product
regression has additional generated native processes recorded in its raw log.

The clean tooling suite runs 215 tests
(213 passed, 2 skipped).
1045 structural checks, context freshness and the spec
manifest pass. 401 product inputs and 419
combined inputs bind exact Git/source bytes. These checks do not qualify
hardware, production storage, all platforms or the complete work unit.

The lifecycle probe deliberately publishes empty graph fragments. It establishes
the link from owned-session publication/process exit to the common capture
reducer; namespace node identities and graph projection remain unimplemented.
The product composition still has no live native namespace provider. Modern
MSVC/SDK x86/x64 builds do not establish historical Windows support. Static PE
observations and dynamic System32 security/random binding are separate.

`reproduction-2d753bae/` retains actual commands, raw process requests/replies,
native logs, source identities, compiler/project configuration and PE observations.
`inventory.json` binds retained evidence and the six local executable artifacts.
The [implementing-agent review](REVIEW.md) grants no owner/provider acceptance.

Reproduce with the installed pinned toolchain and tested Python dependencies:

```text
python .aide/evidence/2026-10-10-capture-publication/reproduce.py --source-revision 2d753baec32c443e121c462ac9b19fa002edb114 --output NEW_LOCAL_DIRECTORY
```

Select a short owned output directory, such as `.aide-local/cp37-2d` on the
recorded checkout. The deliberately long Unicode acquisition fixtures require
the resolved final paths to fit the existing 240 UTF-16-unit profile. The first
full native run used an overlong nested root: 75/77 groups passed, with paths of
243 and 247 units causing two acquisition frontend failures. That failed run
and exact diagnosis are retained in `failed-long-root-2d753ba/`. The shorter
root rerun retains every original fixture name/assertion and the product bound.

An initial invocation used an abbreviated revision and was explicitly stopped
after configure, before qualification, to rerun with the required full revision.
Its completed logs are retained as `aborted-short-revision/`; it is not a pass.
