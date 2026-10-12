# Private header namespace and ownership: 2026-10-13

Native source `3598ac40b79972969ea1ce8585e38a05733e2d87`, base
`c3782b63a941f758cdd011456df1498c22027b45`. Bounded maintenance under the standing
local development/tests/implementer review/dev-main synchronization grant.
Owner acceptance, complete work units and release admission remain separate.

## Change

Cross-module headers use source-relative layer/module names, such as
runtime/command/json.h, portable/hash/sha256.h and apps/disked/gui/gui_model.h.
Same-folder sibling includes remain short. The source tree keeps all 196 files;
166 C/C++ files change include directives only. No algorithm/command/ABI/effect/
resource behavior changes were introduced.97 headers retain their paths.

CMake disked_internal HEADERS file sets follow implementation targets and
explicit header-only capture/text-input owners.80 main-composition headers have
declarations;17 belong to standalone Windows adapter lanes. The shared inline
Windows worker file mechanism has an interface target; actual image/JSON/hash
dependencies and per-executable test macros stay intact. No second implementation
tree, copied header facade or independent manual source inventory was created.

private-header-usage.json projects actual CMake owned/exported headers and
direct/interface compile-usage edges. Header access is checked against that
closure and corroborated by codemodel source membership. LINK_ONLY/private edges
cannot export headers. The source/ namespace root is a shared compiler search
root, not filesystem/C++ access control. Current literal dependencies are
supported; unknown generator expressions fail closed pending an explicit rule.

The guarded journal probe has one compile-only DISKED_MODEL_BINARY_PROJECTION
flag. Simple declared ifdef/ifndef uses configured definitions; source
redefinitions refuse. Unknown expressions/elif/platform flags remain
conservative. This is not complete preprocessing or compiler/system ABI analysis.

## Actual verification

- Exact clean source build/launch on unprivileged current Windows x64 with
  pinned MSVC 19.44.35228/toolset 14.44.35207/SDK 10.0.19041.0/CMake 4.2.3/Python 3.14.7,
  C/C++ language/runtime/security settings preserved.
- All 85 native groups pass, including product/help/CLI/protocol/GUI/TUI/shell,
  image/acquisition/private recovery/wait/resource cases.29 checker tests pass.
- Seven standalone header compilations; 123generated targets
  and 3450quoted include edges pass. Compiled main source
  entries remain 389; header membership is separate from compiled units.
- All 20 standalone Windows adapter executables compile under exact recorded
  commands. They were not launched; no physical queries or provider admission,
  XP/other-host execution qualification follows. Active standalone Windows and
  legacy compilation include roots were updated; historical recipes unchanged.
- 215tooling tests run:
  213pass/2 skip.
  Structural/index/manifest/source-map/context checks pass.
- 501exact source SHA/Git-blob bindings and
  436product inputs retained. Input hashing is not a new
  semantic correctness review of every source file.

Product disked.exe:2180608bytes, `sha256:8569e295cd948ea74cfacd7ca94925db785ea78af79d41fa2e528db7a6af1988`. Local product/
frontend/rule probe copies in .aide-local/artifacts/DE-W010-headers-3598ac40/;
not published or signed. Actual launch, headers/imports/dependents, CMake projects,
raw file-api and compile-usage projection, context archive and command receipts
are retained. Windows adapter hashes in windows-artifacts.json describe compile-
only outputs at the same source.

## Development diagnostics and review

Original namespace bindings came from the preceding generated report. Remaining
standalone headers were unique internal names and confirmed by standalone build.
The first visibility check flagged generated ALL_BUILD/ZERO_CHECK bookkeeping
and an inactive producer-only include in the journal fixture. Bookkeeping has
no compiling source; the declared compile-only guard is interpreted rather than
adding an unwanted link dependency. Raw diagnostics and corrected checks remain.
29 negative/positive fixtures test missing projection/owner, private export leak,
compile-vs-build reachability, exact naming/case/ambiguity and guard handling.
No expected test outcome, provider/effect/resource or production budget was
weakened. This is implementer review, not independent-person/owner approval.

The original committed controller incorrectly asserted eight adapter executables,
confusing rewritten include blocks with target count. Both compilation stages
had succeeded. Its actual stop is recorded in controller-count-defect.log
(explicitly a transcript of tool output). Read-only inspection found 20 outputs
matching all 20 CMake target declarations. complete_campaign.py resumed the
remaining native/tooling checks against the unchanged clean source. No runtime
test expectation or device/privilege/effect rule was relaxed. The original
reproduce.py stays byte-bound to the native source; reproduce_complete.py is
the corrected complete controller for future reproduction. Additional evidence
controllers are bound by retention.json; they are not represented as files
from the native source revision.

SR-03's bounded namespace/visibility work is implemented. Standalone adapter
header-ownership enforcement, broader self-contained headers, all platforms,
production writers/recovery, hardware/privilege/owner/licensing/release and the
full all-platform/storage0.1.0 scope remain open. No whole-product completion or
enterprise/physical qualification follows. Earlier evidence stays immutable
and applies to its exact source/fixture/host scope.

## Reproduce and audit

```text
.aide-local/venv/Scripts/python.exe -X utf8 .aide/evidence/2026-10-13-qualified-headers/reproduce_complete.py --source-revision 3598ac40b79972969ea1ce8585e38a05733e2d87 --existing-clone .aide-local/owned-layout-clean-2c731a1c/checkout --output .aide-local/qualified-headers-clean-new
.aide-local/venv/Scripts/python.exe -X utf8 .aide/evidence/2026-10-13-qualified-headers/audit_retention.py
```

Use an existing clean owned clone/local origin and fresh output directory with
the pinned dependencies. Audit verifies source/evidence/outcome applicability;
it does not rerun native tests or supply execution grants/acceptance. Later
metadata integration can have a newer Git head; native qualification stays at
the named source. Continue the broader programme and recovery gates.
