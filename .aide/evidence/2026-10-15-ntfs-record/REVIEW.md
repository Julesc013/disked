# DE-W076 implementing-agent review

The private supplied-byte work reaches its defined review boundary using native
evidence at `c0749e221b06f89c0aff78bc0af3eceed01b0f84` and the byte-manifest
correction at `ce5efdaef96f5973d78c9cc021f5de2d4d13e38a`. This is the implementing agent's
review, not independent safety qualification or owner acceptance.

The decoder checks the complete declared record before indexing its update
sequence array or protected tails. Oversized input returns a budget status;
bounded malformed input retains issue flags and available raw values. Header
arithmetic is guarded before subtraction/multiplication and uses the existing
portable integer representation. The observed flags remain data.

Restoration validates every tail before copying, rejects overlapping source and
output spans using pointer equality, and changes only the protected tail words
in separate caller-owned RAM. Failed restoration leaves destination and result
unchanged. Borrowed inputs and API/control/result objects have explicit lifetime
and disjointness requirements. This private C interface is not a hostile caller
or public ABI boundary.

The native guard-page/read-only probe agrees with964 independent Python cases,
including every truncation below512 bytes, every one of96 tail positions in the
largest record, capacity/overlap errors, raw64-bit values, flags and profiles.
Eight native API-argument checks run at each probe launch. All11 selected portable
groups, one standalone header, the actual CMake header/dependency audit,
imports/security, strict GCC/Clang C90 syntax, structural/context/source freshness
and242 tooling tests/two skips pass. The c0749e22 overall campaign is **fail**:
its manifest was generated over CRLF working bytes for four files, while Git
stores LF bytes. There are no missing/extra files; exact LF-to-CRLF transformations
reproduce every mismatched digest. ce5efdae changes only manifest entries and
passes fresh clean manifest/index/structural/source-map/context checks. All989
registered/build/source inputs are byte-identical between these revisions; native
code, tests and contract values are unchanged. No unchanged native campaign was
rerun or failure erased. The clean sparse checkout contains every989
registered/build input and current source/tests/spec/docs/tools/external tree;
unused historical evidence is excluded. It is not a full archive checkout or
fresh complete native suite.

The initial working audit's missing private-header ownership and ungenerated
registry inputs are retained. CMake now owns the header explicitly, and the recipe
builds the existing registry generator. No checker, expected output or test
deadline was weakened. The initial inventory enumerator included an ignored
Python cache and failed verification; c0749e22 corrects the inventory to tracked
files, and50 retained files were independently matched against staged Git bytes.
No Python cache was committed.

The selected source remains independent of DE-W075: NTFS code is not linked into
product dispatch and opens no file/device. The earlier failed145-group product
campaign and later report-preparation timeout remain failures with unproven cause.
This review does not support merging the whole current development branch.

Continue original NTFS boot/MFT addressing and attribute/runlist work under its
own contract; retain W075/report diagnostics for cause investigation. Held-source,
provider/frontend, other original platforms/storage, physical writer/recovery,
license, owner and release gates remain open. The all-platform/storage0.1.0 goal
remains active.
