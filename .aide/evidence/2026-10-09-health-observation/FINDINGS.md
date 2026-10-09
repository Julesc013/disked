The first clean reproduction at `3897a55f41e15ca7900cd6e6868dc8c2c172a2e9`
built the native collector/product and passed 95 collector cases and four focused
CTest groups. Its full specification suite then failed with one failure, six
errors and two skips. The retained `reproduction-3897a55f/clean-spec-tests.log`
shows the shared live-repository context fixture exceeded its 260,000-byte
allowance: required content was approximately 263,807 bytes.

The no-truncation guard correctly rejected that pack. The fixture tests input
binding/freshness and portable artifacts; its allowance was not a product or
runtime budget. It now supplies 350,000 bytes explicitly, matching the current
development context allocation. No expected outcomes/assertions, dependency
selection, required input or rejection behavior were removed or weakened. The
separate undersized-payload and one-byte-artifact-budget tests still require
refusal before partial output is written.

The corrected source checkpoint receives a new clean reproduction. The earlier
failed run remains failed evidence; its partial native results are not promoted
into a full-suite pass. This is a test-fixture capacity adjustment, not a claim
that DiskEd context or runtime resources are unbounded.
