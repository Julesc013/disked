# Logical extraction evidence and verification

DE-W049 extends the existing evidence/export/verification services to complete
FAT byte-content extraction. The [owning contract](../spec/catalog/logical-extraction-evidence-prototype.json)
defines expected behaviour before evaluation. Focused development passes; clean
full source qualification is pending.

The exact extraction definition, request, grant and history form a recorded case.
Logical case/support, verification definitions, observations, collections and
joined reports use version 2. Raw producers keep version 1. Readers explicitly
dispatch known versions and reject namespace mismatches. A valid record/hash
chain does not authenticate an actor or establish that its statements are true.

Use the existing `image verify` preparation/execution service with the extraction
operation and its state directory, destination file and checkpoint map. Review
the exact definition and grant case/image/map reads, private store metadata and
host effects separately. Verification reads the current destination and map;
it compares recorded metadata against all seven planned resources, including the
backing image. It does not open or reverify the original FAT source. A matching
result establishes current destination agreement with the recorded map, with
source preservation, authenticity and acquisition consistency still unproven.

The retained collection preserves the exact original request/history and its
verification observation. A later mismatching destination does not rewrite an
earlier match. Joined support export retains historical outcomes without claiming
they qualify current bytes. The existing `evidence export` service binds the exact
case/collection and explicit no-clobber output effects.

All 16 disclosure-policy combinations remain defined. Logical window, FAT copy
and file length require raw-value disclosure; node and metadata digest also
require identifier disclosure. Paths require identifiers, raw values and customer
data together. File payload and raw source names are absent from support output.
The resulting projection is not a complete selector or a source-opening grant.

CLI, protocol and native GUI/TUI/shell use the same service and exact grants.
Owner approval, stable production APIs, physical/power-loss qualification,
production recovery, other hosts and the unchanged full 0.1.0 remain separate.
