# Exact-source contained exFAT reader qualification

The full clean checkout at `cce05d172c89f0a71dba5ee1cc0698307f8c686e` passes all 139 current native groups
with no native skips, 46 standalone header compilations,
69 owned-reader cases/six methods, 63 ordinary-file cases/eight methods and
242 tooling tests with two skips. Exact commands, JUnit, compiler/build identity,
normal/fault PE imports, artifact and source hashes, context closure and clean
Git observations are retained. This is a fresh complete native suite because
the shared ObservationWorker retirement logic changed. Prior failed working
runs and repairs remain in the separate working evidence; no old result is erased.

Actual zero-wait retirement is derived from confirmed process exit, not a
termination request. Expected source metadata is checked before content reads.
The parent checks bounded retained bytes, replay, source/process relationships
and the actual owned attempt before constructing an immutable typed snapshot.
Read-only ordinary-image scope is private: no normal frontend dispatch is added.

The file-symlink fixture remains explicitly unverified without privilege; passing
junction/hardlink checks do not replace it. Other hosts, whole exFAT namespace/
tree/content/extraction, physical mutation/recovery, owner acceptance and the
original full all-platform/storage0.1.0 release remain unfinished.
