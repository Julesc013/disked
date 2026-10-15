# NTFS image inspection

The Windows ordinary-image prototype exposes the owned NTFS bootstrap through
the existing `image.inspect` command and CLI, stdio, Win32 GUI, native TUI and shell.
The [execution contract](../spec/catalog/ntfs-command-prototype.json) defines its
scope, exact projection and failure semantics.
Exact source `b985adf2` passes 50 NTFS cases, all 154 registered native groups,
59 standalone headers and 244 tooling tests (2 skipped), with complete
build/import/context/source evidence. This is not a stable storage ABI.

```text
disked image inspect generated.img --view ntfs --volume-offset 173 --volume-bytes 5120000 --ntfs-version auto --json
```

Select an explicit ordinary-image path and offset/length. The default version
selector is `auto`; explicit `3.0` and `3.1` remain available. A mismatch is a
failed observation rather than silently selecting a different interpretation.
The signed native byte window is checked before opening a source. NTFS-only
options are rejected in other views; existing map/FAT/exFAT forms keep their rules.

The result describes boot, MFT0, mirror0 and volume-information facts. The existing
MFT run count stays a scalar; mapping lists occur inside attributes. Projected
lists have exact original/returned/omitted counts and original canonical hashes,
including where nested run detail is omitted. Observation completeness and
presentation omission are separate. Missing55AA/checksum boot issues retain their
existing advisory meaning when bootstrap geometry is usable; completion is not
a whole-filesystem health judgment.

The [source-bound closure](ntfs-closure.md) work extends MFT/Volume dependencies.
It adds `record_closures` facts with bounded extension and join lists, exact
original hashes and counts. Earlier qualification above is historical evidence
for its exact source, rather than proof of that extension.

The native adapter holds source/ancestor generations, reuses the owned reader and
validates its retained-byte frame after actual child exit. Source consistency,
source applicability, process exit and host retirement remain separate facts.
Timeout retains the occupied callback/source until actual exit; essential static
commands remain available and no late unsolicited result replaces a newer view.

The working evidence retains all five frontends, source/code/process/epoch
relationships, malformed media, typed refusals before source access, nested
projection limits, private fault separation and controlled late completion.
Three failed development runs are preserved: scalar/list projection confusion,
an advisory boot-marker expectation, and an unknown-field diagnostic expectation.
The latter expectations were reconciled with existing contracts, not changed to
invent new parser/format semantics. See the [working evidence](../.aide/evidence/2026-10-16-ntfs-command/working/final/cases.json).

Full NTFS namespace/content, attribute lists and every remaining original
platform/storage0.1.0 capability remain work. Physical media, elevation, owner
acceptance, production writer/recovery, Setup and release gates stay separate.

The [source-bound review](../.aide/evidence/2026-10-16-ntfs-command/REVIEW.md) records qualification and remaining limits.
