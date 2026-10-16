# DE-W072 automatic observer stage: implementing-agent review

Review the bounded stage at exact 6edabcc7, without accepting the whole command
work unit. The existing runtime/capture owner and portable upcase decoder
support a single typed representation choice. Explicit adapters preserve their
v1 field shape; automatic observation has a separate private v2 shape. Candidate
initialization, evaluated completion and validity are distinct, including resource
exhaustion after a first valid candidate. Complete maps are compared directly;
different valid maps produce no selected digest or aggregate applicability.
All choice evaluation uses the original copied table; it causes no additional
source reads or host Unicode normalization. Output allowance and map/digest
buffers are charged under finite existing limits.

Independent pre-recorded expectations and full-map fixtures match actual native
results. Legacy source and contained-reader regressions pass, preserving exact
source pre-read checks, frame replay and exit-only retirement. Four selected
native groups and header compilations, imports/source/context evidence and
242 tooling tests with two skips pass in a clean sparse checkout. The full
139-group cce05d17 campaign applies to its earlier source, not this stage.
Unavailable file-symlink coverage remains unverified.

Continue within W072 to versioned automatic file/frame/owned-reader transport
and shared image.inspect service/frontends. Keep the current source ownership,
command IDs and all original0.1.0 requirements. This local stage review does not
record owner acceptance, qualify public frontend/SDK/storage ABI, or admit writers.
