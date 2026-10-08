# Journal codec findings

The initial empty-binding vector unexpectedly carried a later all-ff binding.
The queued request dictionary referenced mutable fixture data. Queueing now
snapshots the exact canonical JSON; the original zero-binding rejection assertion
is unchanged. The raw failure is retained. This was a test-construction defect,
not proof the native codec accepted an empty binding.

The new registry entry initially used delivery "included". The existing schema
permits "content" or "artifact"; the profile now correctly uses "content" while
code remains hash-bound/retrievable artifacts. The validator was not weakened.
Both corrected working and clean runs passed.

The subsequent initial clean campaign at 5293cf4e passed 47/48 native groups and
failed the existing shared-image callback test. Its cause remains unestablished;
an unchanged timed probe and three repeated groups passed. The private fixture
now uses controlled local events, with actual callback-entry/release/slot
observations and a product negative control. The raw failure and follow-ups are
retained, with each campaign bound to its actual revision. This does not claim
that a runtime defect was found or repaired.

The initial ce9ae70f campaign subsequently failed the acquisition fixture's
unchanged 30-second deadline. Its retained worker completed in 30.837 seconds;
subsequent independent reconciliation verified the generated 16-MiB copy, map
seal and absent worker without replay or cleanup. Unchanged clean revalidation
passed. The initial deadline remains unmet and the host latency cause remains
unestablished. No expected output, deadline or verification requirement was
relaxed for this result.

The byte codec deliberately supplies no payload-semantic or durability claim.
Known record-kind names are framing identities, not approvals. The next work
separates immutable plan definitions and actual receipts, defines independent
recovery traits, and models flush/effect/observation transitions and uncertain
recovery. Production decision DE-DEC-004 remains proposed, with no acceptance.
