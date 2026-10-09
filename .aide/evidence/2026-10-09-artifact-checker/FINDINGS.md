The completeness checker originally used `ZipExtFile.read()` and compared its
result with the expected size and hash. An owned malformed deflated fixture
contained the correct prefix followed by undeclared expanded bytes, while its
local/central size and CRC described only the prefix. The standard reader returned
the prefix; the initial checker accepted it. `working-hidden-tail-probe.log` and
`hidden-tail-probe.json` retain the failing 41-test development run. This was an
uncommitted candidate, not a defect claimed against the previous committed product.

The corrected checker consumes the entire raw compressed extent with bounded
output buffers, requires exact deflate EOF without compressed suffix, checks
actual expanded size/CRC/hash, matches 32/64-bit descriptor and local ZIP64 values,
and verifies contiguous nonoverlapping local records. Expected rejection was
preserved. `hidden-tail-counterexample.json` retains an exact generated fixture
as hex, the standard-reader observation and the corrected rejection.

An earlier working run also exposed different legacy ctime values from path stat
and descriptor stat for the same owned file on this host. The tool now compares
shared identity/size/mtime across APIs and each API's own full fingerprint before
and after the read. It retains change detection, requires quiescent staging and
makes no hostile concurrent-filesystem or atomic-snapshot claim. The initial
35-test failure log and subsequent successful working runs are retained; their
earliest observation recorder did not retain every subtest failure. Final clean
evidence records all test and subtest outcomes.

No fixture content was extracted or executed, and no expected outcome was weakened
to obtain a pass. Unsupported ZIP metadata/carriers remain rejected under the
private profile. Product runtime and release authority are separate.
