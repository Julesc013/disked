# Shared GUI/TUI presentation rules: 2026-10-12

Native source `055bd850e03b723c9b8afa63cb1c803107f466eb`, continuation base
`7813f45d5934cc0f607f5eb724899895a8e3c050`. This is bounded maintenance under
the standing local development/implementer review/dev-main synchronization grant.
It does not record owner acceptance, full unit completion or release admission.

Tooling-only repair source `1b92d0ba2251061e2fd0d40d65af714cff1331b9` is separately
bound. Every native source/contract input is byte-identical across that repair;
the native executable remains bound to055bd850. This campaign began October12
and continued across local midnight into October13; logs retain actual times.

`PendingRequestView` in existing `runtime/presentation/requests.*` centralizes
GUI/TUI pending identity, submitted local view epoch, matching delivery and slot
release. Missing/mistyped/mismatched/unsolicited/duplicate IDs cannot clear the
slot or replace output. False/throwing polls perform no such local mutation.
Exact epoch equality selects CurrentView; unequal tags select EarlierView. This
does not roll back a callback, authorize effects, certify producer identity or
assert worker/operation completion. The executing request channel is unchanged.

`view_command_available` in existing `presentation/session.*` centralizes exact
unique composition discovery eligibility and transport/session exclusions. Bad
or duplicate matching discovery deterministically fails closed. Unknown
observational background is tolerated; parameter form support, storage legality
and grants remain separate. The models retain navigation/editing/rendering.
No universal frontend/scheduler, runtime source file or source rename was added.

## Actual results

- Clean source-bound Windows x64 build/launch using pinned MSVC19.44.35228,
  toolset14.44.35207/SDK10.0.19041.0/CMake4.2.3/Python3.14.7, static Release CRT.
- All85 native groups passed, including existing product/CLI/GUI/TUI/shell/image/
  acquisition/private recovery and wait/resource tests. No expected outcome or
  effect/resource limit was weakened.
- 34 direct native rule cases and8 new Python tests span both GUI/TUI models:
  typed IDs, unchanged output/slot on refusal, duplicate/old delivery, u64 maximum
  epoch equality, malformed discovery and late-result isolation. Exact case names
  and probe identity are retained in `rule-cases.json`.
- Seven independent header compilations, including requests.h/session.h;
  122 generated targets and
  3452 quoted include edges pass bounded checks.
  The existing16 checker fixtures also pass.
- 215 tooling tests ran:
  213 passed and
  2 skipped. Structural/index/manifest/context checks
  and196-file source-map coverage passed.
- 446 source SHA-256/Git-blob bindings and
  436 product inputs retained. Hashing is not a fresh
  semantic review of every source file.

Product disked.exe: 2180608 bytes, `sha256:6f51fc54df116608de67c5eb6d1a0123bf99540d28c37e4074daa0965dfa786b`. Local copies
of the product and3 frontend/rule probes are in
`.aide-local/artifacts/DE-W015-shared-055bd850/`. Imports/dependents/PE headers,
actual launch, build projects, raw codemodel and context archive are retained.
These are development artifacts, not published/signed releases.

## Preliminary diagnostic

The first focused build intentionally built only the model/rule probes. Shared
presentation passed, but existing GUI/TUI CLI-parity cases could not start the
missing disked.exe fixture (WinError2). `development-diagnostics/focused-tests.log`
preserves that result. The subsequent clean full build supplied the product;
the unchanged parity cases passed within85groups. The final focused shared
test and original build/boundary logs are retained too. This was a missing test
artifact, not an established product defect. No retry/timeout/guard was relaxed.

The clean native campaign then found3errors/1failure in the215-test tooling suite:
`logs/tooling.log` retains the original result. Its positive context tests still
used320KB while their expanded owning frontend contracts required354KB; the
production guard correctly refused. The tooling-only repair sizes positive
fixture capacity from copied input bytes and keeps the100-byte/no-truncation,
populated-destination, freshness and all other semantic assertions unchanged.
127targeted tooling tests passed (125pass/2skip), then the clean215-test suite
passed (213pass/2skip). Native inputs are byte-identical across the repair;
successful85-group native receipts were preserved rather than replaced.
Separate `tooling-repair-commands.json` and tooling source/blob bindings record
the exact repair revision. Production context/artifact limits did not change.

## Review and limits

This checkpoint has implementer review, not separate human approval. Stable
commands/schemas/normal valid UI behavior are unchanged. The new deterministic
private malformed-discovery and non-string identity handling is explicitly
specified. Discovery eligibility cannot admit a provider or grant an operation.
Pending UI state is separate from executing threads, durable records, producer/
worker epochs and uncertain storage effects. Old evidence remains immutable at
its exact sources. GUI/TUI forms/navigation remain distinct; other duplication
is not claimed eliminated. Module-qualified includes (SR-03), other headers,
production recovery/writers/physical targets, broader hosts and full all-platform/
storage0.1.0/owner/release gates remain open.

CMake dependencies are transitive/order build closure, not direct links. Quoted-
header checks are lexical rather than preprocessing or complete ABI/system
import qualification. The7 compiler checks do not qualify every header/platform.

## Reproduce and audit

```text
.aide-local/venv/Scripts/python.exe -X utf8 .aide/evidence/2026-10-12-shared-presentation/reproduce.py --source-revision 1b92d0ba2251061e2fd0d40d65af714cff1331b9 --existing-clone .aide-local/owned-layout-clean-2c731a1c/checkout --output .aide-local/shared-presentation-clean-new
.aide-local/venv/Scripts/python.exe -X utf8 .aide/evidence/2026-10-12-shared-presentation/audit_retention.py
```

Use an existing clean owned clone with local origin pointing to this repository,
fresh output directory and the pinned toolchain/dependencies. `commands.json`
records exact actual commands, source cwd, results and logs. The audit verifies
retention/source/identity/outcome applicability; it does not rerun native tests,
establish independent review or manufacture acceptance.

The fresh combined recipe above uses the corrected tooling revision. The
retained campaign ran native checks at055bd850 and completed tooling at the
later repair revision with `complete_tooling.py`; both actual command sets are
retained. Do not present the later Git integration as a new native build.
