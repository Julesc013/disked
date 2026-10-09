# Bounded native H/D/offline ZIP fixture evidence

Clean source `d4102abd5a1ea619b5123210bd8b801cb8657ea2` built and launched a
private DiskEd-bound read-only host (H), retaining the exact previously
qualified dev.36 executable (D) in a deterministic stored ZIP fixture (S).
The [implementing-agent review](REVIEW.md) permits continued local development
under the existing programme grant. Full DE-W062, live servicing, native Setup
carriers, owner acceptance and the full 0.1.0 release remain unqualified.

The finite contract was authored before the clean evaluation in
`spec/catalog/carrier-fixture-prototype.json` and
`spec/catalog/servicing-preview-prototype.json`. The builder uses separate
original D inventory/build information and a caller-selected H observation/hash;
those inputs are not publisher authentication. The inner manifest binds H/D
only, and final S is bound externally. Neither H nor D embeds the other or S.

The [results](reproduction-d4102ab/results.json) record 33 local source inputs,
84 exact unmodified upstream inputs at Setup
`2e64f654b370f500ddbab45ae097df63352c3c25`, two separate native campaigns of
33 executions/223 assertions, four additional H inspection launches, 26
carrier/servicing tests, 30 package/export tests and 215 specification-tool tests
(213 passed, two symlink checks skipped). All 1,041 structural checks passed.
DE-W062's 294,400-byte context was generated and verified without truncation.
No upstream scripts, installed SDK, product rebuild or remote writes occurred.

The actual unprivileged host was `BLACKGLASS-WIN1\Jules`. DiskEd-owned CMake
4.2.3 compiled the original C++17 CoreStatic and inflate-only Zlib inputs plus
the C11 consumer with MSVC 19.44.35228.0, toolset 14.44.35207 and SDK
10.0.19041.0, Release x64 `/MT`. The H project, build logs, direct PE imports,
source hashes, native requests/results and original inventories are retained.
H directly imports `KERNEL32.dll`; no VC runtime DLL import was observed. This
is not a complete transitive/dynamic OS dependency qualification. The linked
static library contains dormant lifecycle code; imports alone do not establish
read-only behavior. The consumer whitelist and null lifecycle configuration
restrict the exercised routes. `host.inspect` does not create a context.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| H: disked-setup-host-fixture.exe | 1,549,824 | `25e557d70b00fd6e14f2fead5a462a064d17941483c975017a6fa59e020ae582` |
| S: carrier.zip | 3,662,608 | `70c0a46080aa2ffeaeff8f7609be5f83f3c8048ed57dafadfa11581b00aba137` |
| D: disked.exe | 2,110,464 | `ac2721db6b26231ed52c31742f472063bed8c7bd88ceb8f14690eb37dd63994d` |

Artifacts are retained locally under
`.aide-local/artifacts/DE-W062-carriers-d4102ab/`; their exact identities, the
base consumer and static library are in
[retained-artifacts.json](reproduction-d4102ab/retained-artifacts.json).
They are development fixtures, not signed or published releases. Determinism
here means two S constructions from identical finalized H/D inputs matched;
it does not assert bit-identical PE output across separate native builds.

From the repository root, reproduce into a new disposable output directory:

```powershell
.aide-local/venv/Scripts/python.exe .aide/evidence/2026-10-10-carrier-fixtures/reproduce.py --repository D:/Projects/DiskEd/disked --source-revision d4102abd5a1ea619b5123210bd8b801cb8657ea2 --upstream-repository D:/Projects/Universal/universal-setup --package .aide-local/artifacts/DE-W060-setup-fixtures-e1683b1/package --inventory .aide/evidence/2026-10-10-setup-fixtures/reproduction-e1683b1/independent-inventory.json --package-evidence .aide/evidence/2026-10-10-setup-fixtures/reproduction-e1683b1/results.json --build-info .aide/evidence/2026-10-10-setup-fixtures/reproduction-e1683b1/build-info.json --output NEW_DISPOSABLE_OUTPUT
```

The recipe requires the selected local upstream pin and previously qualified
portable inputs. It clones exact source, verifies original Git/blob identities,
uses the prior source-consumer recipe, compiles H, constructs/verifies S,
executes expected refusals, checks retained generated data and runs the full
selected suites. The builder never executes supplied code or extracts S. The
reproduction separately copies two fixed independently checked S entries into
an owned damaged-D fixture and never executes damaged D.

Raw [commands](reproduction-d4102ab/commands.json), delegated
[source-consumer commands](reproduction-d4102ab/sdk/commands.json) and native
observations retain actual exit codes, including expected refusal exits 1/2.
An expected refusal is tested by its enclosing zero-exit campaign; it is not
recorded as a successful zero-exit invocation. Generated runtime trees,
compiler objects, exported upstream source and full context contents are
disposable; selected raw observations/configuration and context manifests are
durable. [inventory.json](inventory.json) and the schema-validated handoff bind
these retained bytes, including the local artifacts. After closure:

```text
python .aide/evidence/2026-10-10-carrier-fixtures/verify_closure.py files
python .aide/evidence/2026-10-10-carrier-fixtures/verify_closure.py staged
python .aide/evidence/2026-10-10-carrier-fixtures/verify_closure.py head
```

`staged`/`head` select those Git bytes; local binary hashes are checked in all
modes. These retained closure checks are separate from native correctness.
