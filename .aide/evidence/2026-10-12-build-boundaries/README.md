# Private native build boundaries: 2026-10-12

Native source: `7f86f6bfdf45e0b79420f1c451a797ce2f70514a`; maintenance base:
`9de2b2156e51d31919cb2c93012c06237db65544`. Tooling-only repair source:
`f04563a5584db4c5e7e25435c92e20b27d50523e`. Every bound native input is unchanged
across that repair. Native and tooling receipts identify their separate revisions.
This continues DE-W010/012/017
maintenance under the standing local-development and dev/main synchronization
grant. It records implementer review and generated/compiler/test evidence;
owner acceptance, full work-unit completion and release admission remain open.

## What changed

`disked_json` now compiles only `json.cpp`. `disked_command` compiles the command
parser, protocol and shell lexer; `disked_invocation` compiles frontend selection
policy. Command and invocation depend on JSON independently. Presentation/typed
command adapters explicitly declare command, and product composition declares
invocation. JSON-only codec and invocation-policy consumers do not inherit
command implementations. Existing C++14, static Release CRT, warning/error,
UTF-8 and security options remain pinned. No command ID, runtime source behaviour,
public ABI, tree layout or source filename changes in this checkpoint.

The checker reads CMake's generated codemodel, actual compile-group include roots
and quoted headers. It checks core source/flag expectations, consumer isolation,
forbidden layer crossings, unresolved/ambiguous headers and exact spelling case.
Sixteen synthetic negative/positive fixtures independently test contamination,
wrong case, ambiguity, missing inputs, mixed ownership and weakened flags.
Five generated translation units independently compile each private core header
as the first/only project include. Generated files remain in the build tree.

## Actual verification

- Clean checkout/build/launch at the native source above; tested unprivileged
  `BLACKGLASS-WIN1\Jules`, Microsoft Windows 10 Enterprise 10.0.19045.
- MSVC19.44.35228/toolset14.44.35207/SDK10.0.19041.0, CMake4.2.3 and Python3.14.7;
  exact configure/build flags and project files are retained.
- All 84 native groups passed with parallelism4,
  including existing product/frontend/image/acquisition/private recovery tests.
- 16 checker tests passed; all5 core header
  compilations produced objects under the actual target usage requirements.
- 120 generated targets, 386 compiled source entries
  and 3435 quoted include edges pass the bounded checks.
- 215 specification-tooling tests ran;
  213 passed and
  2 were skipped. Structural checks, generated index,
  manifest, 196-file source-map coverage and source-bound task context passed.
- 444 input SHA-256/Git-blob bindings and
  434 product inputs retained. Input hashing is not a
  claim that every source file received a fresh semantic correctness review.
- PE headers/imports/dependents and actual launch identity retained for the
  product and4 isolated core probes. Header-object identities are retained too.

Product: `disked.exe`, 2180608 bytes,
`sha256:b0fdce865d4a737bd9850fc4c00d7f4881e1ca6e48343b530ed04407ce8250e5`. Local copies of all5 executables are under
`.aide-local/artifacts/DE-W010-build-7f86f6bf/`; these are development artifacts,
not published/signed releases. Full invocation/log receipts are in `commands.json`
and `logs/`; detailed test outcomes in `native-details.log`; normalized generated
dependency/header results in `build-boundaries.json`; original file-api replies,
projects and context archive are retained.

## Failed development diagnostics preserved

`development-diagnostics/checker-initial.log` records the initial 13-test dirty
development run:12 passed, wrong-case detection failed because Windows
`Path.resolve()` canonicalized spelling too early. The fix checks lexical spelling
before resolution; the final exact-source fixture remains strict.

`development-diagnostics/build-boundaries.log` records three false missing-CRT
diagnostics. CMake spells the equivalent MSVC runtime option `-MT`; generated
projects independently record `MultiThreaded`. The checker accepts equivalent
slash/dash prefixes and separately rejects `-MD`. No runtime or warning rule was
weakened. These early logs concern uncommitted development versions, not failed
qualification of the clean source above. Focused initial/corrected/core build
and native test logs are retained alongside them without replacing original bytes.

The clean native campaign then reached a tooling fixture failure at7f86f6bf:
`logs/tooling.log` records215runs,7errors/1failure/2skips. Its fixed350KB positive
freshness-fixture allowance was smaller than the live356KB required context;
production correctly refused without truncation. The later tooling-only repair
sizes positive fixture capacity from its copied input bytes. It changes no
production budget, guard or expected semantic assertion. All29 corrective tests
passed, followed by the clean215-test suite at the repair revision above;
payload/artifact undersized-refusal tests remain intact. Successful native receipts
were preserved because all native source/contract inputs were byte-identical.
`tooling-repair-commands.json`, repair logs and separate tooling source/blob
bindings make this distinction explicit; the original failed suite is retained.

## Scope and remaining work

CMake `dependencies` is transitive/order build closure, not direct link
declarations. Lexical quoted-header checking includes conditional branches and
is not a preprocessor; system angle includes and complete declaration/ABI closure
are outside it. Only5 headers received standalone compiler checks. Most
cross-module includes remain unqualified, and GUI/TUI shared completion/view-epoch/
availability invariants remain pending SR-04. No full historical-platform,
production writer/recovery, physical/power-loss, owner or all-platform/storage
0.1.0 qualification follows. Earlier storage/recovery evidence remains immutable
and applicable to its exact revisions.

Read-only GitHub observations at `2026-10-12T11:14:13.948064+00:00` found Universal Setup
PR237 open/draft at `b63eb946494c45dd706f35455944ebdb773e7146`; exact-head run
38240571262 was in_progress
with conclusion `None` when sampled.
The earlier failed run belongs to the earlier head and must not describe this
new candidate. Main/dev remain c048f7f/2b7a4d0. Both release lists were empty;
DiskEd main was unprotected. No other-repository writes, settings changes or
release publication occurred. These are timestamped observations, not a later
CI result or a statement about every private artifact/tag.

## Reproduction and retention audit

From the repository root with the pinned Windows tools and Python dependencies:

```text
.aide-local/venv/Scripts/python.exe -X utf8 .aide/evidence/2026-10-12-build-boundaries/reproduce.py --source-revision f04563a5584db4c5e7e25435c92e20b27d50523e --existing-clone .aide-local/owned-layout-clean-2c731a1c/checkout --output .aide-local/build-boundaries-clean-new
.aide-local/venv/Scripts/python.exe -X utf8 .aide/evidence/2026-10-12-build-boundaries/audit_retention.py
```

The fresh combined recipe above uses the corrected tooling revision. This
retained campaign ran native checks at7f86f6bf and completed tooling at the later
repair revision using `complete_tooling.py`; its exact arguments are retained.
The recipe requires an existing clean owned clone with local origin pointing to
this repository, uses a fresh output/build directory and refuses nonmatching
source/host results. The audit checks inventory hashes, source Git blobs,
generated identity and retained outcomes; it neither reruns native tests nor
authenticates acceptance. Later evidence/metadata integration may have a newer
Git head; the executable qualification remains bound to the named native source.
Continue SR-03 and SR-04 with bounded native evidence and existing authority.

Closing read-only Universal Setup observation at `2026-10-12T11:37:55.231042+00:00`: PR237 head `b63eb946494c45dd706f35455944ebdb773e7146`, state `open`, draft `True`; exact-head run 38240571262 was `completed` with conclusion `failure`. This does not replace the earlier timestamped snapshot.
