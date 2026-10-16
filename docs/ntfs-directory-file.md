# Held ordinary-file NTFS directory indexes

DE-W091 extends the existing NTFS ordinary-file adapter with source-bound
directory collection, explicit/automatic3.0/3.1 selection and exact retained replay.
Its [execution contract](../spec/catalog/ntfs-directory-file-prototype.json) defines
prefix validation/continuation, quotas, observations and expected tests before code.

The working corpus passes 550 native responses in 12 methods, including actual
offsets above4GiB, independently reconstructed probe/prefix hashes and every live,
prefix and final replay fault position. Five existing NTFS file/capture/closure/
directory/stream groups pass. Two fixture-builder errors and their corrections
remain retained; native expected outcomes were unchanged. A later test revision
also retains before/after whole-file hashes. Clean source-bound qualification is
pending: build all targets, run the31 affected native groups, all tooling and
header/import/context checks, plus six selected Win32/WOW64 groups.

The3.0 path validates the source-bound retained bootstrap under3.0, compares
explicit common facts, then strictly reuses the prefix before new native reads.
Its actual native trace/quotas equal explicit3.0. Metadata after collection and
final pure replay are separate checks; replay equality does not make an incomplete
or refused collection applicable. Default bootstrap outputs/domain remain unchanged.

This is a private synchronous source adapter. Contained worker/frontend admission,
namespace/content, original platforms/storage and separate owner, physical,
privilege and release gates remain required. Actual leaf-file symlink creation
remains unverified where the test host lacks the privilege.
