# Supplied NTFS boot and seed evidence

DE-W077 advances the original NTFS scope with a private supplied-byte C90 boot
observer, complementing the record primitive. Expected fields, signed encodings,
spans, diagnostics and limits were specified before evaluating the implementation.
No upstream formatter/reader was executed or imported as DiskEd implementation.

The first working native run passes 1,729 independent boot cases and 964 record
cases after extraction of their shared protected-input/JSON helper. It checks
all encoding bytes, exact mathematical boundaries, advisory marker/checksum,
BPB fields, truncations, read-only/guard input and error/result preservation.
The actual pinned build/header, strict GCC/Clang C90 syntax, build-boundary,
structural, source-map and context checks also pass. These working observations
are not a fresh exact-source full-suite or owner acceptance.

The finite recipe selects twelve portable groups, one private NTFS header,
boot-probe imports/security, both C90 sources and the structural/context/tooling
floor. Run it from an exact clean source checkout with an available repository
Python environment:

```text
python .aide/evidence/2026-10-15-ntfs-boot/reproduce.py --root PATH_TO_CHECKOUT --output NEW_OUTPUT_DIRECTORY
```

Bootstrap candidates are not validated MFT membership or a formula for later
fragmented records. Geometry, record support and seed addresses are distinct;
there is no NTFS volume/provider/frontend, boot/mount or writer admission. WSL
syntax checks do not qualify a Linux product or any legacy target. W075/report
failures, owner/physical/release gates and the full original0.1.0 remain open.

Exact clean `aefee4cd` finishes the finite qualification with all 12 selected
groups passing: 1,729 boot cases, 964 record cases, one header, 242 tooling tests
with two skips, actual compiler/import observations, both-source C90 syntax and
source/context/manifest freshness. No source input changed during the run.
See [results](qualified-aefee4cd/summary.json) and [review](REVIEW.md) for the
specific evidence and limits. No earlier failure is erased or reclassified.
