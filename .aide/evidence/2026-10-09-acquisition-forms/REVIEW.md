# W033 implementing-agent acquisition form review

Reviewed `7bb3eb4b58fe7976a36fd005a40d37e7ac5c20af` against `670e1075bbf1b8dee68c6c593cfecc427cc2bac2`, DE-103, DE-024 and the continued local
development grant. Passing checks permit local continuation; they do not record
owner acceptance, a release, or independent safety review.

Both frontend models project phase fields from the canonical parameter schema.
The discriminator is first; prepare exposes path/options fields, while execute
exposes the full definition, digest and separate effect grants. Unknown or empty
phase leaves only the selector and cannot be reviewed. A phase change discards
other values, old grants and reviewed typed parameters. No preparation result
implicitly grants effects. The shared command validator still admits requests.

Structured editors allow at most 16 KiB and share the strict definition decoder's
depth/value/string budgets. Scalar fields retain their 4096-byte limit. Invalid
or oversized object edits invalidate review rather than authorizing older valid
text; empty TUI text cannot clear that condition. Duplicate JSON keys, missing
effect grants and oversized definitions dispatch no request. Review and fresh
submission remain separate; scrolling and paging do not submit a form.

The native GUI applies field-specific edit limits, updates visible fields when
phase changes and preserves the phase editor caret during redraw. Actual native
control tests verify successive backspaces, changed phase, cleared grants and
inert Submit. Acquisition review carries no fake graph revision precondition;
its identity is the exact definition and digest. The rendered review screenshot
was inspected after that correction. Console tests verify inert Enter/review,
fresh F9 submission and restoration of handles, modes, codepages and display.

The Windows acquisition adapter is shared by the command probe and marked native
test composition. Native asynchronous callbacks own immutable copies of reviewed
parameters. Exact definition/effect validation occurs before worker dispatch;
callback construction does not start effects. The public executable remains
unavailable for acquisition admission and keeps its existing worker role policy.

All 46 native groups, 175 specification tests, 921 structural checks, generated
freshness, manifest and exact context/source/input/artifact identities passed
clean reproduction. Two actual GUI/TUI copies match source bytes and independent
map hashes. This qualifies the frontend component on the tested Windows host.
It does not qualify structured shell execution, large interactive watch results,
public admission, other platforms, physical storage or production recovery.
