# DE-W105 product capture qualification

The expectation in [expected.json](expected.json) was fixed before implementing
the product coordinator or evaluating product pixels. This is the next bounded
step after the verified private [transport control](../2026-10-21-capture-transport/REVIEW.md).

The coordinator inherits the earlier image pins, request queue and scope checks.
It overrides the invalidated pixel reader completely. Captures use the actual
DiskEd GUI thread, a separate query-only membership job and a fresh anonymous
output section. The outer supervisor handle remains private. Client coordinates
are separate from frame bounds. The existing client, caption, alpha, frame-only
and inert-review assertions remain required for all six separately identified
product cases.

Source export now resolves stable input identifiers through the same typed
dependency graph as context generation and impact analysis. Catalogs come from
the exact selected revision. The source-snapshot regression exercises an alias
whose stable identifier differs from its pathname, its transitive prerequisite,
and a dirty catalog that cannot alter an earlier revision's selection.

The first host regression attempt exposed an older synthetic test fixture that
provided no typed input registry. Its failure is retained in
`preparation-failure.json.xz`; the fixture now supplies the real registry-shaped
inputs while preserving its exact-revision expectations.

Run preparation or qualification through the existing workspace runner:

```text
python -B tools/workspace.py run -- python -B .aide/evidence/2026-10-21-product-capture/launch.py --prepare-only
python -B tools/workspace.py run -- python -B .aide/evidence/2026-10-21-product-capture/launch.py
```

Native results are pending. Preparation, source checks and private controls do
not establish product capture success. Current full native qualification is
still required before main promotion. Owner acceptance, release, reference and
all original platform/storage gates remain separate.
