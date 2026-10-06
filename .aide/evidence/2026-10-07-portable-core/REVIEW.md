# DE-W020 local implementing-agent review

Reviewed `aaac4d4fc712d3c03d2a9960e949a13a5c83995e` against `6e49cf3b19a6f4b91ceea767e5bcd35412e497f9` and the DE-031 contract recorded before
implementation. This is implementing-agent review under the cross-unit grant,
not independent safety review or owner acceptance. Acceptance receipts remain
unchanged. The work record stays needs_review for owner review.

- Exactly bounded unsigned arithmetic widens before multiplication/shift. The
  schoolbook product's largest accumulator is 65535*65535+65535+65535, exactly
  representable in u32. High limbs are checked before publishing a u64 result.
  Subtraction tracks borrow; division keeps a fixed 64-step quotient/remainder
  calculation and handles the explicit high remainder bit. Refusals do not
  publish intermediate values. Exact aliases of arithmetic inputs are supported;
  quotient/remainder outputs remain separate caller-owned objects.
- Size conversion processes bytes against the target's actual size_t ceiling.
  Slicing uses subtraction-based bounds before pointer arithmetic and permits
  only a valid empty slice at the end. Empty null views avoid null+0 arithmetic.
- Endian reads copy bounded bytes into a zeroed value. Writes establish bounds,
  width and the complete serialized value before changing the buffer, retaining
  their destination pointer locally. The guard-page test exercises truncated
  reads and refused writes against real memory protections, not a mocked length.
- Named space objects and their names are immutable borrows for extent lifetime.
  Identity resolution stays in the caller; pointer equality only binds a local
  space object. Inclusive end, partition length, device end, exact block units
  and byte products are checked independently. Overlap excludes adjacency.
- Standard C headers are the portable module's only external includes. There is
  no allocator, OS API, file handle or provider callback. C90 source is compiled
  as C, with a separate C++ caller validating actual unmangled linkage.
- The Python oracle uses independent arbitrary-precision integers and byte
  conversion. Boundary/seeded cases, unchanged-output sentinels, invalid internal
  objects and target-width refusals cover the contract. Three clean compiler
  lanes agree on shared semantics; the 32-bit size ceiling differs explicitly.
- The former DE-W018 implementation was extended in place. Its legacy probe
  contract and 411-case regression remain usable. Work/context/build closures
  include the core, harnesses and coordinator. No new public SDK or storage
  command is inferred from a static library or green tests.

The deliverable and two work-unit acceptance criteria are satisfied for local
portable-core development on the recorded compiler/host profiles. Continue to
DE-W021 under the existing grant. Keep historical qualification, owner acceptance
and storage/release gates distinct; the full programme remains active.
