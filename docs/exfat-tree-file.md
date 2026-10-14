# Held ordinary-image exFAT trees

DE-W075 extends the existing `providers/image/exfat_file` adapter. Its new private
tree API holds the ordinary file and ancestor generations through collection,
retained replay and final binding checks. Root capture v1/v2 outputs and their
read order remain compatible. The runtime collector remains the owner of tree
semantics; portable/exfat remains the format decoder.

Inputs, limits, expected metadata and callback objects are copied before any
callback. Actual held metadata establishes source identity and capture epoch.
Every applicability decision is retained alongside the ordered read responses.
Replay consumes those exact sequences without native reads or live cancellation
callbacks. Changed binding, metadata or replay withdraws stability and retains
observed prefixes. Tree completeness and observed source-region stability are
different properties; neither grants current-source or mutation authority.

Working native tests pass46 generated-file cases/eight methods, including nested
fragmented/NoFatChain allocations, ValidDataLength zero filling, actual held-handle
exclusion, invalid inputs, cancellation and replay disagreement. The original89
root-file cases and44 supplied-tree cases pass. The first dependency check correctly
reported the new tree/namespace closure; its owning declaration is updated for
the implemented shared API. Exact source qualification is pending.

This is a synchronous private adapter. It creates no extracted files and is not
admitted to normal worker/frontend dispatch. Paging/backpressure, contained
transport and process retirement, other platforms/storage, owner acceptance and
full original0.1.0 remain at their gates. No new fault environment protocol is
available in normal code.
