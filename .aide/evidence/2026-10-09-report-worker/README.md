# Private report-worker evidence

Current source: `c81d330a4e160dcee23b29069a8ad894df396c03`; task base: `d1f1cc8978ac13e1ac744442f3037cb6f9662547`. DE-W034 remains partial, with
owner acceptance pending. Native product version is `0.1.0-dev.28`.

The private same-executable role binds the reviewed acquisition case, selected
support artifact, output, worker/producer image, host and execution-store
generations. It retains operation/attempt/worker/process identities, versioned
state, cancellation observations and exact receipts. Client exit or a timed-out
admission does not restart the worker. A lost terminal record preserves unknown
execution alongside any actual created output.

Clean results: 64/64 native groups, 178 report-worker checks, 959 structural checks,
262 manifest files, and 175 tooling tests run (173 passed, two skipped). Exact
commands, host/toolchain, raw logs, generated private state samples and artifact
hashes are under `reproduction-c81d330a/`. The 307 build-input hashes were
independently checked. Actual generated acquisition bytes/map and support bytes
were checked independently of the producer. Five report files were created:
three completed artifacts, one retained empty cancellation artifact and one
independently verified artifact whose terminal record write was injected to fail.

`sample-support.json` alone is selected redacted content. The surrounding case,
definition, state and receipt samples contain generated private routing metadata.
Record hashes authenticate no actor and do not verify current acquired images.

Reproduce from this exact source with installed recorded dependencies:

```text
python .aide/evidence/2026-10-09-report-worker/reproduce.py --source c81d330a4e160dcee23b29069a8ad894df396c03
```

The runner uses fresh owned paths. It refuses existing paths instead of deleting
them; retain failures and choose a new owned path for a separately recorded run.
`reproduce-de597e3a.py` and that source's results preserve the earlier provisional
format. `supersession.json` records the cancellation-label correction. The initial
test-helper failure and its generated fixture inventory are retained as failures.

The product still has 18 available commands; `evidence.export` remains planned.
This private role, export/case libraries and production journal prototypes are
unlinked from disked.exe. Public export parameters/results/descriptors, bounded
common service/watch and actual CLI/stdio/GUI/TUI/shell journeys remain pending.
No other platform, physical storage, real full filesystem, power loss,
authenticated custody, installation, signing, publication or owner acceptance is
qualified here. The all-platform/storage DiskEd 0.1.0 goal remains active.
