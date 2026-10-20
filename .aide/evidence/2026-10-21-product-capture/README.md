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

The first actual product run at `caa473b6` built and linked DiskEd in 296 seconds,
passed its import/security observations and the existing CLI/protocol acceptance
group. Capture failed before producing pixels: the coordinator's `SetPropW`
call returned Windows error 5. The failure, 20,432-byte archive and cleanup
receipts are retained in `attempt-001/`. Peak allocated scratch was 86,936,259
bytes; filesystem usage peaked at 110,043,136 bytes. The owned source, media,
actor and temporary output were removed, and local metadata was consumed.

The repair makes the GUI initialize its own nonce properties on its UI thread
from a bounded private test configuration. It no longer asks another process to
modify those properties. Invalid configuration fails explicitly. Desktop ACLs,
ordinary-token checks, image pins, query-only membership capability and all
caption/client/inert-review assertions stay in place. The receiver protocol and
earlier independent transport controls are unchanged. A repaired native run is
pending; no product pixels have been qualified.

Host validation passed 253 specification, 222 tooling and 84 differential tests
(559 run, eight skipped), with 1,328 structural checks, source-map and manifest
verification. The final helper registrations received the 222 tooling tests and
structural/projection checks again. Current full native qualification is still
required before main promotion. Owner acceptance, release, reference and all
original platform/storage gates remain separate.
