# Exact-source exFAT root/system qualification

Exact source `bba3d600001109ad4dd370d5320f9bcda2d06e6e` passes 121 independent
image cases in nine methods, all 19 selected native groups, one private header,
PE/import/context/build-boundary/source-hash checks and 242 tooling tests with
two skips. Original working compiler/boundary failures and the stale-guard
limitation remain in the separate working evidence with their repairs.

The clean sparse checkout includes every registered and build input and all
current implementation/tests/spec/docs/tools/external files. Unused historical
evidence is excluded; checkout-selection.json and sparse-patterns.txt record the
exact selection. This is not a fresh complete native suite or archive checkout.
reproduce.py records actual commands and paths; use a new output path for reruns.

Applicability is only root/active-system metadata agreement over supplied bytes.
No native opening, atomicity, future freshness, complete namespace/tree/content,
physical writer, other-host or full original 0.1.0 release is admitted. Local
implementing-agent review and owner/independent acceptance remain separate.
