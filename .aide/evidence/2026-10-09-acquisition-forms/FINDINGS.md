# Acquisition form findings

The initial new test stopped before copying because its ASCII-path definition
was 4090 bytes, below the intended greater-than-4096 editor regression. The raw
failure is retained. The fixture now uses owned Unicode path components within
the existing 240 UTF-16-unit Windows profile, making the UTF-8 definition exceed
4096 bytes without relaxing provider or decoder limits. Corrected working and
clean runs passed the strengthened assertion.

Review of the hidden-console harness found that redirected pipes would prevent
the intended interactive TUI route. The harness now starts the native executable
with its newly owned console handles and checks state restoration. This was a
fixture correction, not evidence of a product test failure or a weakened test.

Inspection of the actual GUI review screenshot exposed a misleading fake graph
revision on acquisition requests. Both frontend reviews now use graph revisions
only for graph commands. The acquisition review and submit bind the independent
definition/digest instead. The actual screenshot confirms that correction.

Native phase changes trigger full control redraws. Preserving unchanged editor
text avoids resetting the phase caret during typing/backspace. An actual native
test verifies the caret after the first backspace, the second edit, cleared
execution grants and inert submission. Model and native tests both retain the
separate review/submission boundary.

The product still refuses public image.acquire. The marked private test variant
identifies itself in build information and provides only generated-file test
evidence. Structured shell execution and interactive acquisition-watch results
must be qualified before public admission. W033 is partial; owner acceptance is
empty and the wider DiskEd 0.1.0 platform/operation programme remains open.
