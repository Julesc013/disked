# Implementing-agent review: held-file NTFS name correspondence

DE-W096; base `887af8ed615bf18a7b0dbeb9f1a37a161ec6d550`; exact native source/fixtures/recipes `c1511f80c0e407a755d40cd956b7b467bd4afade`.
The persistent local development grant and DE-W095 implementing-agent review
permit this bounded file adapter and reviewed dev/main source integration.
Owner acceptance, independent safety qualification and release/storage privileges
remain separate. Full original all-platform/storage 0.1.0 is unfinished.

The existing ntfs_file owner copies the full request, target cap, callback and
fault controls before native access/callbacks. It reuses the same local_file
opener, source/ancestor pins, finite native read/byte/retention controls and
capture observer. No second opener/parser, worker kind, snapshot kind, public
command or source directory was added. The source map still covers all 324 files.

The typed membership request wraps the existing directory request. Target caps
1..256 are checked before opening and bound in the native domain and automatic
profile foundation. Old modes omit the new field and preserve their existing
serialized domains/foundations and native traces. Automatic3.0 validates and
reuses the exact bootstrap prefix before any new native read. Independently
reconstructed probe/prefix/selected reports and foundation digests match.

All reads, target/list/extension closure and final exact rereads use the existing
qualified collector. A complete valid name mismatch stays complete/nonapplicable;
malformed/stale/unsupported/changed/error/quota evidence stays incomplete. Source
metadata, native binding, pure reconstruction and aggregate eligibility remain
distinct. observed_stable includes observation applicability; a mere mismatch
does not fabricate a binding error. All authority/atomic-snapshot flags stay
false. Current synchronous native waits remain uncontained and private.

Fresh all-target Windows x64 build passes the predefined 31 affected groups out
of 166 registered, including496 new held-file cases across 11 methods and the
existing NTFS/public/shared-file regressions. This is selected current evidence,
not a full 166-group run. All67 standalone C++ headers, strict C90 sources/two
headers,13 distinct executable PE/import observations and 247 tooling tests pass
(two coordinator symlink skips). Serialized Win32/WOW64 supplement passes 11
selected groups/10 headers/7 executables, including the same 496 native cases.
Full Win32 product, historical Windows, DOS and other hosts remain unqualified.
The old bootstrap-file and directory-file suites also retain actual file-symlink
checks as unverified on both x64 and Win32: the unprivileged host reports
WinError 1314. These are separate from the two coordinator test skips. No
elevation was requested or performed to turn them into passing observations.
Whole generated source hashes are unchanged; exact commands/logs/artifact hashes
and contexts are retained.

The first working run remains failed. Its new assertion incorrectly classified
a short response as ntfs_reader_failure; the established reader and old directory
tests require ntfs_read_length. The new expectation was corrected against that
existing contract. No runtime behavior, threshold or expected refusal changed.
Earlier W095 timing failures remain retained at their original revisions; this
selected campaign does not explain or qualify absence of those intermittent
delays. Another unexplained timing failure needs measurements before a retry.

The first W096 clean `9fac1bde` campaign also remains failed: one group passed,
the existing large-directory human CLI request returned request_wait_expired,
and 29 selected groups were not run. Temporary reader/snapshot phase probes
complete in 0.16/0.19 seconds; the unchanged exact product request takes 0.17
seconds, and the complete 100-case directory-command recheck passes. The original
delay remains unexplained. The temporary harness's first compile/output errors
are retained separately; they were not product defects or qualification.
The existing frontend test now records elapsed time/exit/output before its
unchanged assertions. AST comparison confirms all existing assertions identical;
every production runtime source file and deadline remains unchanged from 9fac1bde.
The new exact-source selected campaign above is distinct evidence, not a
relabelling of the original failure or proof that intermittent delays are absent.

The second fresh `90e246d9` campaign also remains failed after one pass, a missing
independent-worker snapshot and 29 selected groups not run. Its helper discarded
raw worker state. Twenty-five direct workers, twelve new-path workers and twelve
product copies, plus two focused two-group CTest sequences, subsequently passed
without reproducing the failure. Neither the delay nor missing snapshot has an
established cause. The helper now retains full raw worker failure output and
elapsed/outcome before its AST-identical assertions. The later campaign is
separate evidence; these observations do not establish absence of intermittent
availability failures. Production runtime source/deadlines remain unchanged.

Review supports source integration after metadata/staged-byte closure. Next is
the separately contracted worker/snapshot boundary, then common frontend
admission. Namespace/collation/lookup/content, original platforms/storage,
writer/recovery, Setup/licensing and owner/release gates remain.
