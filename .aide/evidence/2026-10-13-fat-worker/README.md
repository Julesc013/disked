# Contained FAT reader evidence: 2026-10-13

Native source `56effc8f4d35ec4ae519453ad288d8da725945ed`; base `bace2f916885e16b01a3fad15e18a008e9106e6e`. Expected contract `a4302dd9` preceded
implementation. Standing local implementation/testing/implementer review and
tested dev/main synchronization grants apply; owner and full 0.1.0 acceptance remain separate.

The existing ordinary-file reader now has an owned region/result API. Its legacy
JSON output is unchanged. Shared request validation keeps the same predicates;
shared namespace withdrawal preserves original facts while denying applicability.
The new frame/input validator belongs to providers/image; the concrete FAT worker
role belongs to platform/windows/storage and reuses the existing observation host.
The source map covers 214 current files, with four actual source files added.

Requests bind exact expected file metadata/generation/size, explicit volume window,
FAT copy, caller capture epoch, flags/budgets and optional CP437/850/932 queries.
The worker checks before metadata before reading. Source paths/parents/file types,
sharing and single-link rules remain enforced. No source-derived name becomes a
path. Caller capture epoch, internal file sequence/domain and process identity are
distinct. No mount, writes, installation, elevation or physical storage is used.

The anonymous channel preserves the existing host limits. FAT uses <=8 MiB frame
bytes, a 128 KiB input mapping and <=32 KiB publication reply, within the existing
16 MiB payload, 278528-byte input and 786432-byte reply ceilings. Existing 128 MiB
child, 256 MiB parent and shared worker quotas are unchanged. Oversize/resource
refusal remains explicit; no truncation or limit increase is admitted.

The parent copies and hashes the published payload, validates complete frame/
receipt/input shapes and bounds, then independently reconstructs the original FAT
observation from ordered captured regions. Region coordinates/errors/lengths/
hashes, reread consistency, overlap and metadata flags are derived and compared;
raw-result tampering cannot establish a snapshot. Capture-domain/process binding
is checked against actual native PID/creation and code/request/role/epoch evidence.
Pure frame validation authenticates no process. Only the owned FatWorker session
constructs an immutable snapshot, which retains values after actual retirement.

Logical result completion and process exit remain separate. Genuine publication
can be consumed while the child is still alive; retirement requires observed exit.
Cancellation/timeout does not establish quiescence. Pre/post-spawn exceptions keep
the caller's owned session and permit explicit retirement, without replacement.
Unstable/partial/invalid media retains honest facts. These observations do not
certify a source snapshot, filesystem health, mounted consumer or current authority.

Actual focused tests passed 11 methods/109 cases: native FAT12/16/32 children,
512/4096 units, optional allocation/auxiliary/name models, independent region and
domain hashes, partial/invalid media, source-generation/sharing/hardlink refusals,
capture errors/changes, every exercised envelope binding, forged data/receipts/
domains/processes, pure-frame mutations, cancellation, hangs, late publication,
completion before exit and immutable retention. Normal builds reject test fixtures;
fault controls stay in separately compiled test binaries. Generated whole-file
hashes are preserved by the reader; one controller deliberately grows its owned
fixture to prove actual generation refusal.

The initial invalid-input harness passed an override twice to a dict constructor.
Its constructor now applies explicit overrides; expected refusals are unchanged.
The original failed 91-case log remains retained. The first clean parallel native
campaign at b4f133ba passed 95/96 groups, with the FAT fixture failing; its original
logs/source bindings are preserved in development-diagnostics/first-native-campaign-b4f133ba.zip.
The same clean-source 108 cases passed in isolation. A new actual four-reader
test proves the fifth launch is refused by the shared job, with real exit-only
retirement of all peers. The FAT CTest fixture was missing the existing shared
resource lock, so it could compete with other fixtures. It now uses that lock;
runtime caps and outcomes are unchanged. The original failed run retained output
digests rather than all refusal bodies; its exact historical refusal text cannot
be recovered from those hashes. New refusal/quota observations are explicit.
The repaired source is the qualification revision above. No checks, outputs or warning
policies were weakened. A genuine missing callback sequence cannot be accepted
merely because the observer converted an exception into a partial report.

The exact clean unprivileged Windows x64 build passed 96 native groups, including
prior 1335 allocation, 6790 directory/name, 149 capture, 86 allocation-scan,
257 auxiliary and 171 namespace cases. Fifteen independent headers compile.
Tooling: 213 passed, 2
skipped (215 run). Structural/index/manifest/context/source-map,
actual launch/imports and generated dependency checks pass. MSVC 19.44.35228,
toolset 14.44.35207, SDK 10.0.19041.0, CMake 4.2.3, Python 3.14.7;
GCC 15.2 strict C90 syntax for the four FAT C sources only, not runtime/ABI/legacy.
518 SHA/Git-blob bindings, 474 build
inputs, 150 targets and 3732 include
edges are retained. Hashing is not semantic review of every input.

Raw commands/logs, source/blob bindings, context, build projects/codemodel and
executable/library hashes are retained here. Local artifacts:
`.aide-local/artifacts/DE-W037-fat-worker-56effc8f/`. No executable release,
signing or publication was performed. Product dev.42 and its 21 command identities
remain unchanged; this private reader is not yet in the shipped composition.

```text
.aide-local/venv/Scripts/python.exe -X utf8 .aide/evidence/2026-10-13-fat-worker/reproduce.py --source-revision 56effc8f4d35ec4ae519453ad288d8da725945ed --existing-clone .aide-local/owned-layout-clean-2c731a1c/checkout --output .aide-local/fat-worker-clean-new --gcc-executable PATH_TO_EXISTING_GCC_15_2
.aide-local/venv/Scripts/python.exe -X utf8 .aide/evidence/2026-10-13-fat-worker/audit_retention.py
```

Use a fresh output and clean owned clone. Retention audit is not a fresh native
run. Integration heads add metadata/evidence; native source remains the revision
above. Continue actual shared command/frontend admission, larger/chunked FAT
coverage, explicit extraction and further consumer/host/platform/storage work.
Production journal/recovery and owner/physical/elevation/customer/install/sign/
release gates remain open; the full all-platform/storage 0.1.0 goal is unfinished.
