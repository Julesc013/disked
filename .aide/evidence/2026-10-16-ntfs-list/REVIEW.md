# Implementing-agent review: NTFS attribute-list entries

DE-W084, base `8883b56d754eae4f853b8dc68e08de34b0e69ae5`.
Tested source `65ca67d9f1acd9fe4798fe561de1767b73446e8a`. Review is by the implementing agent under the
existing local-development and dev/main synchronization grant. Owner acceptance,
physical/elevation/customer/install/signing/publication authority remain separate.

The private C90 decoder belongs in `portable/ntfs/attribute_list.c` alongside
the existing FILE/attribute/run algorithms. It interprets supplied bytes only;
there is no allocation, I/O, callback, new public interface or provider admission.
The independent Python struct/integer oracle defines expected outputs from the
pre-evaluation contract. Raw names, signed-coordinate patterns and full reference
bits are preserved. Every readable full header is observed, while malformed
framing stops without inventing a next entry. Safe framing may continue after
name/VCN/type diagnostics. Exact span exhaustion, short tails and item-budget
stops remain distinct; EOF is not a stream-completeness claim.

Bounds review: the 26-byte header is checked before each fixed load. Declared
length/alignment/span checks precede advancement. Name checks use bounded
subtraction after checking the offset. Advancement cannot exceed the remaining
span; count cannot exceed4096. No FILE-record size limit is imposed on list
values. Empty/invalid calls preserve sentinels. Borrowed inputs/control objects
must remain valid, disjoint and stable; this is not a hostile C-caller boundary.

The clean Windows x64 Release campaign passes **561 protected-byte list cases**,
**24 selected native groups**, **59 standalone headers**, and
**244 tooling tests with two skips**. All **1047
registered/build inputs** remain unchanged. Strict C90 syntax passes with the
recorded MinGW GCC; MSVC builds/runs the probes. Build/header/source-map checks,
PE/import/dependency observations, manifest and context freshness pass.
[Exact commands and results](qualified-65ca67d9/summary.json).

The selection includes NTFS record/boot/attribute/run/list/capture/file/worker
and common-command regressions, neighboring portable/readers and build checks.
The default build compiles all selected-composition targets, but this campaign
does not run the complete registered product test suite. The prior full
154-group campaign remains bound to `b985adf2`. No failure expectations, byte/item
limits, timeouts or safety gates were relaxed. The working build and oracle
passed on their first actual native run; their logs are retained separately.
The first clean campaign at `65b0c5b5` passed23 of24 selected groups and failed
the exact NTFS build-source contract because the new file was omitted from its
approved list. The correction adds that one owned source, preserving checker
rules and its32 negative fixtures. The original failed campaign and contract
remain in `failed-65b0c5b5`; it is not relabeled as a pass. This fresh campaign
qualifies the corrected source/contract checkpoint.
An unavailable Windows clang executable was not an executed compiler test;
the installed GCC supplies the recorded strict-C90 check without installation.

Two tooling symlink checks are skipped. Native actual-file-symlink qualification
remains unavailable with Windows error1314. Other hosts/ABIs are untested here.
The current NTFS product command remains bootstrap-scoped: it still refuses
attribute-list-dependent MFT/volume interpretation. This decoder does not resolve
references/sequences, join extension records, read arbitrary MFT records or
qualify namespace/content, writers/recovery, physical storage, Setup or release.
Original all-platform/storage0.1.0 remains incomplete.

Conclusion: eligible for ordinary source integration after current metadata and
staged-byte closure. Record actual Git writes separately. Continue with a bounded
source-bound MFT extension/reference contract and independent fixtures; retain
the original programme scope and outstanding authority/qualification gates.
