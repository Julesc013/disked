# Supplied NTFS FILE record evidence

DE-W076 advances the original NTFS scope with a private supplied-byte C90
envelope/fixup primitive. The expected contract was defined before evaluating
its implementation. Input stays borrowed and stable; restoration writes a
separate caller-owned RAM buffer only after validating every protected tail.
No volume, provider, physical operation or public ABI is admitted.

The first working run at base5507c412 has964 independent generated cases and
11 selected portable regression groups passing. Native API misuse checks,
read-only/guard-page input, output preservation, strict GCC13.3/Clang18.1 C90
syntax, probe imports/security, context, manifest and242 tooling tests/two skips
pass. Its overall result is **fail**: the whole build-graph audit found the new
header's missing ownership declaration and missing generated registry headers.
The failed audit is retained under `working/`, with the exact changed input
bytes under `working-inputs/`; `working/inputs.json` binds the broader inputs.

The CMake declaration now exports the private NTFS header through its actual
owner. The qualification recipe builds the existing `bootstrap_registry` target
before the full graph audit. The corrected working audit and964 cases pass;
qualification at a clean exact revision follows the source commit. No checker,
fixture expectation, product deadline or admission boundary was weakened.

Reproduce the finite selection, with the repository Python environment:

```text
python .aide/evidence/2026-10-15-ntfs-record/reproduce.py --root PATH_TO_CHECKOUT --output NEW_OUTPUT_DIRECTORY
```

The recipe selects11 portable groups and one standalone NTFS header, records
the actual native compiler/build/import closure and artifacts, then checks
source/context/spec/tooling freshness. WSL GCC/Clang checks are syntax checks,
not a Linux product run. This is not the entire native suite, a DOS/OS2/Win32
qualification, an atomic NTFS acquisition, an attribute/runlist reader or a
writer/recovery qualification. DE-W075/report-preparation failures remain open.
The original all-platform/storage0.1.0 scope, owner and release gates remain.

The clean `c0749e22` run passes the native/portable/header, C90 syntax,
structural/context/source and 242 tooling checks (two skips), but its overall
status remains **fail** because of the byte manifest. Four expected hashes bound
CRLF working copies while Git stores LF. The diagnosed `ce5efdae` correction
changes only manifest entries; fresh clean manifest/index/structure/source-map
and context checks pass. All 989 registered/build/source inputs are identical
between those revisions. Native tests were not repeated to erase the failure.

See [applicability](applicability.json), [implementing-agent review](REVIEW.md),
[original exact run](campaign-c0749e22/summary.json) and
[manifest correction](manifest-ce5efdae/summary.json). These qualify the bounded
private primitive, with owner, full native/product and original release gates
remaining separate.
