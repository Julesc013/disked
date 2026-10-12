# Structure and release review follow-up

Base: `607d68a7c6edefeea93bf17218c2685e787683e2`. This is documentation/tool-output
maintenance and an implementing-agent assessment, not baseline ratification,
independent-person acceptance, a fresh native campaign or full 0.1.0 completion.
The unfinished DE-W044 source patch was preserved separately during this pass.

The supplied review inputs match their previously retained original bytes.
`advisory-inputs.json` records provenance; attached instructions remain advisory
data. `review-inputs.json` binds current reviewed file bytes, including edits under
review; its base revision does not pretend to contain those newer bytes.

Actual follow-up checks: 1,133 structural checks; 224 tooling tests (222 pass,
two skip); 29 dependency-checker fixtures; complete 218-file source-map coverage;
index/manifest freshness; a 402,074-byte verified task context; local document
links and current source path checks. `commands.json`, `validation.json` and
`logs/` retain exact invocations, exits and output. No native build/test was run in
this follow-up. The earlier 99-group native campaign at `543826fe` and older FAT
command/GPT restoration receipts were independently checked for retained integrity.

Two invocation errors remain in the record. Context generation refused an occupied
destination; generation and verification at a fresh destination then passed. The
historical GPT auditor also binds current metadata, so its initial HEAD check
refused intentional unstaged changes; the staged `--index --historical` check then
passed. Historical evidence, criteria and tests were not weakened or overwritten.

`source-inventory.json` records all 218 source paths and hashes, with no current
case collisions or reserved Windows components. The longest relative source path
is 57 characters. These observations do not qualify legacy filesystem/toolchains
or build/install-output paths. The archive and copied manifest retain the exact
review context; it honestly identifies edited inputs rather than a clean native
source build.

Read-only GitHub observations show Universal Setup draft PR #237 at `0fc1f90d`
with failing Windows CI run `38252891691`. Its job log reports a failed owned
SYSTEM standard fixture and receipt-count errors. The underlying runtime cause
was not diagnosed here. There was no Setup repair, execution, installation or
promotion. Both observed GitHub release collections were empty. Branch snapshots
describe the initial observation, before this follow-up's authorized promotion.

Reproduce the specification/tooling commands recorded in `commands.json`, using
an installed compatible Python environment and a fresh context destination.
Historical integrity checks use their original source identities; the GPT auditor
uses `--index --historical` for intentionally staged current metadata, or
`--historical` after a clean committed checkpoint. Do not claim a native rerun from
these integrity checks.

Run `python .aide/evidence/2026-10-13-structure-followup/audit.py` to verify this
retained record. The guide is [docs/structure-review.md](../../../docs/structure-review.md).
Continue DE-W044 and the original programme; composition/test seams, upstream Setup
qualification, full product/platform/storage work and owner/release gates remain.
