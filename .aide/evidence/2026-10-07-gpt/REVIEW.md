# DE-W022 local implementing-agent review

Reviewed `ad88098941dcad2e1b4056d892a324c59683edaa` against `3ac97606aaf058e2c66430ea2f9a97bc1b5096cf` and the DE-032 contract written before code.
This is implementing-agent review under the cross-unit grant, not owner acceptance
or independent safety review. The acceptance ledger remains unchanged.

- The reader accepts complete logical blocks, validates fixed header offsets
  before decoding, and checks HeaderSize before computing its CRC. Original bytes
  are never modified. Unsupported revisions and inconsistent geometry cannot
  issue array requests. Primary failure does not redirect or suppress backup work.
- Count/size multiplication and rounded block extents use checked u64 primitives.
  The minimum reserved area remains separate from CRC-covered array bytes. Device,
  metadata and usable ranges are checked before exposing a request. Profile and
  native-size limits precede array access/workspace writes. Caller-owned immutable
  descriptors/bytes and disjoint mutable workspace remain explicit preconditions.
- The original bitwise CRC matches independent zlib vectors; header logical-zero
  treatment and array-padding exclusion have distinct cases. Full entry bytes and
  uninterpreted attributes remain retained. Inclusive end conversion, adjacency,
  overlap and duplicate IDs are tested without normalizing invalid metadata.
- GUID text uses the EFI mixed-endian mapping. UTF-16 decoding bounds every unit
  and surrogate pair, stages UTF-8 before publication, preserves original bytes,
  and reports missing termination separately. It performs no normalization or
  terminal rendering. Invalid encoding and short output buffers do not publish
  partial strings or termination state.
- Candidate comparison requires consistent complete observations in the same
  space object. Different valid bytes with the same CRC still disagree; identical
  bytes with different entry shapes also disagree. No winner selection, repair,
  source-stability, protective-MBR or filesystem qualification is inferred.
- 1022 cases and actual protected-page checks pass in three compiler lanes, with
  identical observations across those and the native build. Existing native
  regressions pass (37 groups). These are modern-host controls; external parser
  differential/coverage fuzzing, historical profiles and coherent capture remain
  explicit next gates. The initial failing fixture was corrected without changing
  its expected result and its failed receipt remains available.

The bounded W022 deliverable and both acceptance criteria are met locally.
Continue to W023 under the grant while preserving owner/storage/release gates.
