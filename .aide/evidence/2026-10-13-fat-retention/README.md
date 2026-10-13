# FAT capture retention evidence

Native source `4d3dc0a3cb1597289926cb6e010c57f7156b285d`; development base `e938724876da520cf2270323dedc100e285e78fb`. The source freeze is distinct
from the later evidence/integration revision. Local implementation/tests/agent
review and tested dev/main synchronization are authorized; owner acceptance and
the full all-platform/storage 0.1.0 goal remain separate.

The clean native campaign passed 101 groups, 68 retained-capture command/frontend
cases, 91 synthetic store checks/400 concurrent reads, an exact eight-MiB record in
43 chunks, 18 standalone headers and 224 tooling tests with two skips. Previous
FAT/GPT/image/frontend/worker/regression cases remain in the retained detailed logs.
Compiler, source blobs, imports, build configuration, contexts and artifact hashes
are bound to the exact source. GCC checks are strict-C90 syntax only.

The runtime retains the original independently verified FAT frame/context/final
worker observation as immutable bounded UTF-8 JSON bytes. List/read/release perform
no source I/O. Tests delete generated FAT12/16/32 sources before reconstructing
records, independently check raw metadata regions and hashes, preserve Unicode and
honest changed-source facts, exercise quotas/IDs/EOF/ranges and late completion,
and use actual CLI/stdio/GUI/TUI/shell flows. Maximum GUI read data has 393,216 hex
characters. Reserved entries cannot be released while the callback is running.

The development diagnostics retain earlier GUI fixture failures. Its page helper
used the wrong private control IDs; correcting the helper enabled the intended
read-form test without changing expected output or weakening the product. Initial
input-registry classification was also corrected to an admitted kind. Passing
preliminary results came from dirty-tree diagnostic builds, not this clean campaign.
The first clean parallel campaign failed five groups. Its complete record is
retained alongside a passing serial diagnostic and the later full parallel
qualification. No assertions/deadlines were changed; the underlying cause of the
initial concurrency-sensitive failures was not independently established.

Retention is current-process only, with no durable custody, source freshness,
unobserved payload extraction, mounted-consumer, hardware or writer qualification.
The original full product/platform/storage goal and production journal/recovery,
owner/physical/elevation/customer/install/sign/release gates remain open.

Reproduce using `.aide/evidence/2026-10-13-fat-retention/reproduce.py` with the exact source, a clean owned clone,
fresh output directory and the installed GCC15.2 path. Run `audit_retention.py` to
check retained integrity; that is not a native rerun. Local artifact copies are in
`.aide-local/artifacts/DE-W044-fat-retention-4d3dc0a3/`.
