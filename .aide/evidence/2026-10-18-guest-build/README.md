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
