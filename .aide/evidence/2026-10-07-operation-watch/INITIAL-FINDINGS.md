# Watch implementation findings

The first live CLI smoke observation emitted sequences 1 and 2 at about 47 ms,
3 at 264 ms, 4 at 790 ms and 5 plus the final response at about 1.04 s. The retained
JSON records the actual frames; these approximate times came from the exploratory
console log, not the later source-bound timing evidence.

The first seven-method native campaign found the Win32 form's existing two-string-
field ceiling prevented staging watch, and one fixture expected a scalar-validator
diagnostic instead of the existing CLI invalid-option diagnostic. The implementation
now supports bounded paged string/boolean fields with shared typed review; TUI
uses the same conversion. The diagnostic fixture preserves the existing CLI
mapping. The initial failure and subsequent passing seven/ten-method runs remain
in this directory.

Compilation caught a shadowed local index under /W4 /WX during paging changes;
the field index was renamed. One exploratory build named gui_probe instead of its
actual CMake target gui_model_probe; it failed after successfully building disked
and disked_file_wait. The corrected targets built and their model checks passed.

A specification regression insertion briefly left a record assertion in the wrong
method, causing NameError; it was moved back without removing the assertion.
The syntax corpus schema does not admit an expected parameters member, so the
watch alias fixture uses its existing identity/operand/named-option fields with
valid new watch arguments. Native watch tests independently verify parameter
relationships. No expected runtime outcome was weakened to bypass a failure.

The final source-bound campaign adds explicit output-failure suppression of a
queued new operation, strict event schemas, unknown/verification-failed/cancelled
outcomes, observer timeout without late frames, and hidden-console/private-desktop
parity. No real storage, privileged execution or production journal is qualified.
