# DE-W105 product capture qualification

Current: `3bbf92f2` passes24 independent native controls and all six actual
product GUI cases. The saved PNGs pass the complete-background checks and
direct visual review. Full180-group x64 qualification and main admission remain
open; this is a focused capture result.

The full attempt at `c319466b` stops before compilation when source import
exceeds its unchanged180-second deadline. No native groups run. Its exact
failure, source retirement and owned cleanup are in `full-native/source-import-timeout/`;
the earlier connection-only failure is retained separately. All1344 selected
source files subsequently match their Git blobs. The cold phase was not recorded,
so that observation does not diagnose the exact timeout location.

The importer now sets explicit index skip-worktree bits and checks out only
NUL-delimited declared paths, avoiding a non-cone pattern for every selected
file across64749 tracked paths. It isolates its child Git environment without
changing user configuration, and retains bounded nonce-bound phase timings.
The15 source-transport tests include a64000-path virtual excluded tree and
caller Git-routing/configuration controls. All240 tooling tests pass afterward.
See Git's [index semantics](https://git-scm.com/docs/git-update-index#_skip_worktree_bit)
and [explicit path checkout](https://git-scm.com/docs/git-checkout-index).
`launch.py --source-proof` selects the existing512MiB source/NUL control;
it does not compile the product or replace the full native gate.

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

The `f301a9cb` retry (`attempt-002/`) passes build/import/protocol acceptance and
publishes one authenticated owned-client capture with all20 descendants and
stable11 GDI objects. The unchanged client/caption assertion rejects it. No PNG
was saved because the assertion preceded writing; the candidate harness now
saves PNG and per-region diagnostics in the archived build directory first.
This is a diagnostic-retention repair, not a relaxed assertion or capture pass.

At `5ad35f00`, `attempt-003/` retains the actual984x681 inventory PNG and
caption-region diagnostics. The image places the first button at18,41 while
its client-relative outer position is10,10: the measured8x31 frame offset.
The whole client contains data, but seven of eight measured caption interiors
fail. This is a rendering-coordinate defect, not a missing account grant.

`framed-expected.json` fixes an independent240x96 framed-root A/B test before
its fixture and renderer repair. The existing tree mode now requires a real
captioned frame; normal and receiver modes retain their popup roots. The RGB
recipe, all modes and original guards are unchanged. Its first run intentionally
uses the unmodified renderer; an expected regression failure is not a pass.

Microsoft documents [WM_PRINT](https://learn.microsoft.com/en-us/windows/win32/gdi/wm-print)
client/child dispatch and the application-owned handling of
[WM_PRINTCLIENT](https://learn.microsoft.com/en-us/windows/win32/gdi/wm-printclient).
Those contracts informed the experiment; actual retained pixels established
the observed displacement.

The first framed control at `7ada96f6` fails the independent RGB oracle in
`tree`, after21 native calls; receiver modes are not reached. Its stdout hash
and parsed frame remain in `framed-controls/before-fix/`; unknown control pixels
were not retained. The candidate repair translates the owned memory DC by the
measured window-to-client offset before WM_PRINT. No display DC is used, and
the direct WM_PRINTCLIENT path and original guards are unchanged.

At `aab8adcc`, all23 native controls pass, including exact framed A/B pixels;
`framed-controls/audit.json` binds19 reported inputs to that revision and rejects
three corrupted replays. The real product then passes build/import/CLI and all
six GUI runtime cases. Direct inspection of all six PNGs rejects remaining
unpainted bottom/right background (`attempt-004/visual-review.json`). Receipt consistency
is now explicitly separate from actual image review, and main review requires
a passing visual receipt bound to the exact source, product and six PNG hashes.

`background-expected.json` fixes the next full-buffer test before implementation:
the framed root paints only through WM_ERASEBKGND, leaving hidden children.
The same two240x96 RGB recipes must match completely. This adds a ninth mode
to a separate32MiB profile while retaining every original mode and guard.
The first run uses the viewport-only renderer to establish the regression.

The background-only baseline at `5b5b17fd` fails the independent RGB oracle
after22 calls, with no receiver modes reached. Its failure and cleanup are
retained under `background-controls/before-fix/`. The candidate repair paints
root background at client origin before window-tree printing and omits the
second, shifted root erasure. The unchanged full RGB oracle must pass before
another product/visual admission attempt.

The product background oracle is frozen separately in
`product-background-expected.json`: unused outer client-edge RGB must equal
COLOR_BTNFACE observed by the fixture. A host regression reads the actual
runtime-passing `attempt-004` PNG, verifies its retained hash, and rejects its
missing background. Actual product checks now verify raw and encoded PNG
edges while retaining all previous assertions and visual review.

A retained host validation failure (`background-controls/host-interruption-failure.json.xz`)
exposes a test-injection defect: mocking every sleep to interrupt also aborts
cleanup backoff when Windows briefly holds a log handle. The outer workspace
was removed. The test now interrupts the post-launch resource check exactly
once, keeping child retirement and workspace-removal assertions unchanged.
Production runner limits, retries and cleanup code are unchanged.

The first background fixture was incomplete: offset0 selected only a120-pixel
child region. Both its baseline and repair failures are therefore inconclusive
for isolating renderer origin (`background-controls/fixture-correction.json`).
The fixture now paints the complete root and self-checks all23040 RGB pixels
in both phases through WM_ERASEBKGND on a separate client-origin memory DC
before exercising the capture primitive. The next diagnostic checkpoint uses
the exact viewport-only `aab8adcc` renderer to re-establish a valid baseline.

The corrected fixture at `91bd79e1` passes its direct two-phase full-canvas
WM_ERASE self-check and exits successfully, then the viewport-only capture
fails the independent RGB oracle after22 calls. This valid baseline is retained
in `background-controls/corrected-baseline/`. The client-origin background
repair is restored unchanged from `bccd405c` for the paired repaired run.

At `acd7724a` all24 native calls complete, including exact RGB in normal,
framed-tree and background modes and receiver/hang controls. Final evidence
saving exceeds the existing1MiB aggregate uncompressed record budget, so the
campaign remains failed (`background-controls/archive-budget-failure/`).
The candidate retention repair stores the zero-surface stdout once as bounded
XZ and validates its decompressed length/hash; no native expectation or budget
is changed. Old raw records remain readable.

At `3bbf92f2`, the complete repaired control campaign passes all24 calls and
nine modes, including both full23040-pixel background phases. Replay binds19
reported source inputs to that exact revision and rejects altered pixels,
missing frames and false reports. The49-entry archive contains878340
uncompressed bytes, below the unchanged1MiB limit. Owned cleanup is verified.
This admits the private control result only; the actual product capture and
full180-group qualification remain separate gates.

The actual product attempt at that revision applies the original checks and
the new raw/PNG client-edge invariant to all six cases. Receipt review now
requires the background observations as well. The post-review reader supports
bounded compressed receipts directly, rejects ambiguous or trailing records,
and keeps the explicit actual-image review requirement. `launch.py --full-suite`
selects the existing180-group,69-header,14-executable x64 contract in the same
512MiB capped guest; preparation is not execution or qualification.

The real `3bbf92f2` build/import/CLI acceptance and six GUI cases pass. All six
retained PNGs were displayed and inspected: controls and content align with
client coordinates, and the prior bottom/right background gaps are absent.
`visual-review.json` binds that observation to the exact product and six PNG
hashes. `replay.json` independently checks archive membership, request/receipt
identities and decoded PNG background edges. The archive is64088 bytes; owned
guest actor/profile/media, source and host workspace cleanup is verified.
No full-suite, other-platform, accessibility or owner/release claim follows.

Complete host validation retains253 specification,238 tooling and84 differential
tests with eight expected skips. Final routing changes receive all238 tooling
tests,1328 structural checks, source-map and manifest verification again, with
unchanged tested input hashes. The typed DE-W105 closure now binds the actual
x64/Win32 staging helpers, review reader and C90 checker. Stable IDs are resolved
to paths rather than assumed to be filenames. Both native profiles pass
preparation; those checks do not claim native execution.

`launch.py --win32-suite` uses the existing18-group/12-header/nine-executable
private Win32 contract and512MiB cap, retaining compact receipts in
`private-win32/`. It refuses leftover raw campaign output. A fresh run is required
because shared memory-budget code and the workspace runner have changed since
the historical Win32 result. `c90-check.py --evidence-dir PATH` reads the exact
selected compact receipt; its syntax-only host check runs no product code.
The focused build's ten NTFS C units and two standalone C headers pass.
