# exFAT command execution contract and expected selection

The existing explicit native decoders at exact cce05d17 agree with complete,
independent mapping oracles on six candidate-selection scenarios (12 native
inputs). These define expected behaviour before implementing automatic selection:
unique compressed, unique literal, equal valid maps, different valid maps and
invalid mandatory ASCII. They do not test an automatic implementation or any
normal product exFAT command. Original table and binary hashes are retained.

The same 131072 bytes and checksum can validate both explicit representations
while producing different complete maps. Refusing that ambiguity is DiskEd's
derived policy. Microsoft's format specification requires reading both encodings;
it does not itself prescribe this automatic-selection policy. Reproduce using
probe-selection.py with --probe PATH --output PATH from the repository root.
The script imports the independent existing tests/property oracle; it does not
use host Unicode normalization. Original scratch attempts corrected an import
name, handled invalid-init output and replaced a false literal-only expectation
with the measured identical-map result. No native algorithm defect was alleged.

DE-W072 continues in the existing image.inspect identity, shared runtime service,
product composition and Windows host. The owning profile and work record fix
invocation, limits, output/status semantics and acceptance before evaluation.
All original full0.1.0 platform/storage and owner/privilege/release gates remain.
