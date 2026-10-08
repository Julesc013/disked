# Retained development findings

The initial adapter build failed because the private implementation class lacked
its closing brace. The corrected build retained /W4 /WX and the existing flags.

The initial creation-race harness timed out because it waited for a child before
draining the complete receipt, which can exceed the stdout pipe buffer. The child
was terminated and waited for by its owner. The harness now uses communicate
while waiting. No runtime expectation was weakened.

The first full working native run passed 40/42 groups and failed both product
acceptance source-input-closure tests. Header/test inputs had legitimately changed
after build identity generation. A rebuilt snapshot passed all four targeted
acquisition/acceptance groups. These intermediate observations are retained;
only a clean pinned-source run may establish the final complete native result.

The first structural check also rejected a required-input edge to a Markdown
concept outside the typed input registry. The test instead depends on its probe
input; owning DE-103 enters the existing semantic context closure. Subsequent
structural checks pass. The tool's unknown-node rejection was preserved.

Review added a destination-coverage guard before incomplete-map repair/replay:
unexplained growing-file suffixes, or nonzero preallocated fixture suffixes,
cannot be overwritten. An independent regression retains the bytes and map.
Receipts distinguish expected map length, observed held-handle file sizes and
unknown size observations. A failed call can leave partial bytes beyond counters
for successfully returned calls; effect uncertainty and pending intent remain.

Only generated ordinary files were used. Kill/wait tests are process interruption,
not power loss. Injected disk-full/flush/read errors are controlled API faults,
not real failing-media, disconnection or thin-provisioning qualification.
