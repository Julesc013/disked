# Guest source and configure checkpoint

Codex remains an enabled administrator emergency spare with its original profile.
The owner-requested password update succeeded through Agents; Codex was not
logged into and Jules was not changed. `account-check.json` records the read-only
verification without retaining a password. The connection helper admits Agents
only and never falls back automatically.

The guest verified 931 selected source files and clean Git identities. Source
`3f18a2879d44b76179f9fdb63ea339aaf59604f9` completed the pinned x64 CMake
configure after selecting the actual VS instance explicitly. This is configuration
evidence, not a product build. No private Win32 build or group passed here.

| Attempt | Result and retained receipt |
| --- | --- |
| 1 | VS instance discovery failed in the restricted worker; `first-instance-discovery.json`. |
| 2 | Explicit instance selected, compiler identification failed; `second-compiler-identification.json`. |
| 3 | Retained configure YAML identifies MSBuild FileTracker's empty CommonApplicationData path; `third-file-tracker.json`. |
| 4 | Scoped directory read resolved that path and x64 configure passed; fixture ancestry metadata was denied; `fourth-ancestor-metadata.json`. |
| 5 | Configure passed, fixture needed volume-root metadata; `fifth-volume-root-metadata.json`. |
| 6 | Directory update timed out; image retired, owned source required recovery; `sixth-directory-update.json`, `sixth-recovery.json`, `sixth-cleanup.json`. |
| 7 | Configure passed and fixture rejected worker probes' existing production support source; `seventh-probe-support.json`. All disposable output was removed. |
| 8 | Source f72b18ef verified clean. .NET refused to edit a noncanonical directory DACL before configure. Missing retirement metadata also interrupted report capture; original `eighth-report-capture.json` and recovered `eighth-directory-acl.json` preserve both failures. `eighth-recovery.json` and `eighth-cleanup.json` confirm owned cleanup. |

Every retained observation archive was read without extraction and checked against
its receipt's entry lengths and SHA-256 values. Attempt 8's raw archive did not
survive; its bounded receipt/tails were recovered before deleting disposable
inputs. Do not describe those tails as complete raw logs. The original local
archive-check helper also failed before retaining a diagnostic; handling of
list-shaped cleanup receipts was corrected and the repeat passed.

The canonical fixture generator now preserves
`source/platform/windows/memory_budget.cpp` in the two worker executables where
the real codemodel already places it. It rejects missing support and arbitrary
production additions. All 18 groups, 12 headers and nine executable targets remain
required. The current generator has fixture-test coverage, not a successful native
Win32 evaluation. The coordinator suite ran 119 tests: 118 passed, one expected
skip, no errors or failures. Its preceding 116-test run remains separate.

Exact source exports can now name an immutable full commit ID while retaining
uncommitted coordinator evidence. Both catalogs and blobs come from that commit;
the manifest separately records producer dirtiness. Default exports still refuse
dirty checkouts. Regression tests verify that no working edits enter or are lost
from the exported source.

Directory access changes were fresh-package read/execute rules without inheritance,
never write grants. `Set-Acl` on the volume root timed out. The later recipe used
the deliberately directory-local [SetFileSecurity API](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-setfilesecurityw),
which Microsoft marks obsolete for general use but documents as not propagating
directory security to children. This is a bounded guest setup recipe, not a product
security API. Cleanup removes the exact temporary rule instead of restoring a stale
whole DACL. No matching attempt-8 grant remained on any of the four declared paths
when recovery ran. Final observations find all three surviving ancestor DACLs
canonical; the removed owned qualification directory's original DACL was not
retained, so the failing path and origin of noncanonical ordering remain unresolved.
Do not canonicalize a shared ancestor or widen worker permissions speculatively.

The final recipe separates directory-access retirement, worker retirement and
archive retention so one failure cannot skip the other cleanup attempts. Optional
missing metadata no longer masks the original guest result. Host syntax and archive
checks passed for these changes; another native run has not evaluated them.

`context.json` records 1,323 structural checks, verification of 420 manifest files
and fresh DE-W105 context verification at f72b18ef. Canonical specification content
and runtime source did not change. The full historical specification test suite
was not rerun; its earlier evidence retains its own revision and scope.

`final-observations.json` confirms the qualification directory, image and source
copy are gone. `.aide-local` is empty. Only the project-owned portable Python
runtime and its manifest remain in the guest DiskEd directory: 613 files,
37,706,089 content bytes. The shared backing file remained 28,809,625,600 bytes;
deleting guest files is not a backing-file reclamation claim. The VM remains
running with four CPUs; host UAC is unchanged. Other users' processes, checkpoints
and accounts were not removed.

Next, diagnose the precise directory before changing permissions; preserve its
original descriptor and use the existing owned-root boundary where possible.
Support valid noncanonical descriptors without resetting shared ACLs. Then rerun
the same-source Win32 fixture under the existing cap and complete the full x64
product/build-gate qualification. DE-W105, owner acceptance, broader 0.1.0 and
release qualification remain incomplete. No new permission or VM restart is needed.


## Subsequent build and fixture correction

Attempt 9 identified the noncanonical directory as the newly owned qualification
root. The edit now preserves existing ACE order, with exact before/after
observations; `directory-roundtrip.json` proves all four original descriptors
were restored byte for byte. Pinned Win32 compilation succeeded. A log sharing
violation stopped import collection; `ninth-shared-log.json` retains that failure.
Attempt 10 completed all nine executable/hash/machine/direct-import observations.
Its first group failed in fixture creation/cleanup before native product calls:
Python's protected Windows 0700 directories omit the package identity. Both
attempts' images, source and input copies were removed.

`tests/support/tempdir.py` now supplies owned inherited-permission directories to
the two shared NTFS fixture bases only. Ordinary processes keep standard tempfile
behavior; confined processes require the expected source marker, plain ancestors
and a parent within their existing work root. Changed identities are preserved,
not forcibly removed. No interpreter globals or product assertions are changed.
The helper and its tests are bound in the build/input dependency catalogs.

The current coordinator suite ran127 tests with one expected skip; the complete
specification suite ran253 tests in355.810 seconds with two expected skips.
Structural1323 checks and the420-file manifest passed. The first full-suite wrapper
returned1 without a retained final test result; its partial receipt and original
wrapper are retained, and no completed test count is inferred. The revised wrapper
retains timeout output and permits900 seconds for this coordinator suite; native
per-test deadlines remain unchanged.

Two memory-only ACL cases/ten assertions and five retention/retry checks passed.
The initial enum-cast failure is retained separately. The campaign now archives
per-call requests, replies, stderr and JUnit before evaluating group outcomes,
then removes only those outputs. Sharing errors32/33 receive at most five seconds
of retry after owned descendants retire. Other errors remain failures. These
changes and the fixture helper still require an actual guest preflight and native
retest; no Win32 test group is currently qualified.

Attempt 11 at27d447 passed the actual confined fixture-helper preflight, the
Win32 build and all nine executable/direct-dependency observations. Native calls
then failed closed with image_path_identity/platform5 before source reads.
Attempt 12 retained a diagnostic-launch permission error. Attempt 13 ran the
corrected diagnostic inside the same confined worker: DOS/GUID final-path and
DOS-device queries returned5, while normalized NT paths and file IDs succeeded
for all ten held ancestors/source handles. These are diagnostic observations,
not passing product groups. All three attempts removed owned media/source/input
copies and restored temporary ancestor ACL entries.

The proposed private ordinary-file profile now binds complete normalized NT
names to a fresh strong handle for the selected DOS drive root and compares
volume IDs. It retains the original240-unit DOS input limit, ancestor handles,
generation checks and no-fallback behavior. Six predeclared binding rows cover
exact/case/dot positives and wrong sibling/root/other-volume negatives, with zero
data reads. Original79 file cases remain required (85 total), along with all18
Win32 groups and the complete current x64 gate. This repair has not yet received
native evaluation. The latest complete specification run passed253 tests with
two expected skips; its raw receipt is retained once in specification-checks.json.xz.

Attempt 14 at ef1ffeb2 passed the Win32 build, all nine PE32/security-flag/import/
dependency observations and all six binding rows with unchanged source bytes.
The first native group retained83 calls, two errors extending large sparse
fixtures through CRT-backed truncate, and one unavailable symlink creation under
the deliberately restricted token. The group remains failed; neither error nor
missing privilege is a pass. Its complete output and cleanup receipt are retained
as fourteenth-sparse-fixtures*.

The fixture repair uses explicit sparse marking and native logical EOF, records
actual allocation after writing the original regions, and adds a confined
high-offset/zero-hole/removal preflight before compilation. A guest coordinator
prepares one bounded source and actual symlink; the same non-elevated product
probe must reject it. Worker privileges, original fixture bytes/cases, all18
groups and per-test deadlines remain unchanged. This fixture repair is not yet
natively evaluated.

Attempt 15 at aa0445e1 passed the actual sparse preflight, Win32 compilation,
all nine executable/security/import observations, and the first native group:
11 methods/86 calls, no errors, failures or unavailable checks. The campaign
then correctly stopped at its incorrect85-count guard; the remaining17 groups
did not run. The image, package profiles, source and transferred inputs retired.
The fixed scratch work peaked at154,486,378 allocated file bytes; the fixed image
remained512MiB, and recorded shared backing length did not grow in this run.

Inventory review independently expands the existing ten method loops to80
original calls. Hash-verified historical file and directory-file summaries show
79/550 completed calls and one explicitly unavailable symlink each. Keeping
those real checks gives80/551; adding six binding rows gives86. The new required
method matrix preserves every old call and strengthens the prior aggregate
guard. Historical records stay unchanged. The directory test reuses the owned
prepared symlink after copying and hashing its exact small generated source,
without granting worker symlink-creation privilege.

The base file recipe now retains exact per-process stdin/stdout/stderr and
process identity before result assertions, including failed/timed-out replies.
Other groups keep their existing retained recipes. This new retention path, the
method matrix and the directory symlink setup still need native evaluation.

The corrected contract passed253 specification tests in435.415 seconds with two
expected skips, structural checks and the refreshed manifest. Host GCC performed
syntax-only C90 checks for current portable NTFS sources/two standalone C
headers; source-map validation passed. These checks execute no DiskEd or media
code. The current bounded recipe/streaming-retention check also verified all14
retained guest archives against their recorded per-entry hashes. The next native
run must evaluate the new method matrix, raw-call receipts and shared prepared
symlink helper; specification and metadata passes do not substitute for it.

Attempt16 at08e538e4 passed the first native group and verified273 retained raw
files (1,785,343 bytes), all12 actual standalone-header object hashes and nine
PE32/security/import observations. The name-order file group retained208 calls
before a dense fixture extension hit the512MiB scratch cap; its9 methods had
one error. Work reached509,154,356 allocated file bytes. The failure stayed in
the capped filesystem, the shared backing length did not grow in this run, and
all owned image/source/input/profile output retired. Its317MB of raw evidence
compresses to288,904 bytes; no executable/object/image copy is retained.

The next recipe streams only closed request/reply/stderr files named by complete
published harness receipts into the existing compressed archive. It validates
exact group containment, plain single-link files and original hashes before
removal; unpublished output stays. Final receipt parsing is strict, duplicate
publication cannot duplicate archive members, and no live-group sharing retry
is added. Eight coordinator tests cover exact recovery, publication boundaries,
changed bytes and outside paths. All original name-order recipes and expectation
hashes remain unchanged. Small fixtures now use the same sparse logical-EOF
method as large fixtures, preserving logical bytes and all original assertions.
Both small and high-offset allocation/data/hole/removal preflights are required.

A read-only export audit also found two qualification expectation files already
bound in DE-W105 context but absent from the thin build export. The recipe now
explicitly adds all four required expectation files, matches their immutable Git
blob hashes to the source-bound context, and admits936 selected files. This is
a qualification-input repair; no expected result, native deadline or storage
budget changes. The new streaming/small-fixture/export path needs native retest.
