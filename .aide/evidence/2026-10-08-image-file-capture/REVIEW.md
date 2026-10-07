# DE-W024 ordinary-file local review

Reviewed `d0229f7a52e79a938cc6b3389be96366f686e389` against `307d3814fda66466a36f352d986da03d4df8c622` and the DE-102/036 private capture contracts.
This is implementing-agent review under the owner's continuation grant, not owner
acceptance, independent provider qualification or full W024 completion.

- The callback boundary checks requested byte extents, request/byte budgets and
  returned view size/nullness. The owned region store is stable through all header,
  EBR/array and candidate comparisons. Reader/workspace borrows never escape in
  the returned JSON. The pure prefix API retains its earlier geometry/byte binding.
- The file adapter performs no write, destination creation, device open, image
  mount, elevation or network discovery. Path profile checks precede source opens;
  ancestor/final handles are inspected and normalized-path bound. Source opening
  is read-only and non-inheritable; reparse, multiple-hardlink and offline/recall
  profiles are rejected. This is a restricted local prototype, not adversarial
  host isolation, real storage fencing or broad namespace support.
- The signed native file length is retained exactly, with explicit rounding of
  partial final blocks. Large offsets are not narrowed to 32 bits. Bounded reads
  retain actual short/error ranges without zero substitution. Captured copies
  remain immutable; inconsistent overlapping observations are not hidden.
- A complete owned region receipt binds per-region data/error/reread evidence.
  Its finite projection distinguishes total requests, unique regions and reuse.
  Before/after metadata and byte rereads produce observed stability, while the
  consistency class stays live-uncoordinated. Equal reads and source hashes do
  not establish an atomic point-in-time result or a healthy-volume certificate.
- The clean tests exercise corpus findings, real large sparse offsets, source
  bytes, actual local permissions/sharing/alias refusals and bounded test faults.
  Test-only environment hooks are absent from the ordinary provider library.
  All 39 native groups and 171 specification tests were actually run. Historical,
  other-host, actual changing/removal media and production-storage checks remain
  unverified; actual image frontend parity and command admission remain open.

Continue W024 shared command/frontend integration. The whole release programme
and acceptance ledger are unchanged. No GitHub write was performed.

The runner subsequently reported the persistent goal as blocked, without a reason
in its available status response. This is retained in runner-status.json; it does
not invalidate the completed local checks or establish a new engineering defect.
The project programme remains incomplete and resumable at shared image command work.
