# Private tree correction reviewed; broad qualification failed

Keep the source owners and names. `exfat_tree.*` collects supplied-byte tree and
logical-content observations, `exfat_namespace.*` owns name association/comparison,
and `exfat_capture.*` owns the original root/system capture. No second format
parser, scheduler, native source opener or public command was introduced.

The tree copies its request and validated limits before callbacks. Four regression
cases reproduce budget enlargement in the old reference-based collector; all44
cases/10 methods now pass on x64 and Win32. Exact `9c2d2b09` passes five selected
x64 groups and three Win32 supplied-byte suites, four headers per architecture,
242 tooling tests/two skips and import/context/source-freshness checks. Win32 uses
an isolated fixture composition derived from the actual CMake graph. This does
not qualify a Win32 product or the full native suite at that revision.

The earlier exact `e7e3297f` build and51 headers succeed, but its full144 native
run has136 passes and eight failures. Verification, extraction and acquisition
workers exceed test deadlines; GPT execution times out after preparation; one
syntax probe exceeds five seconds. These failures remain unresolved and prohibit
integration into `main`. The tool/header generation and fixture-graph runner
failures, and their corrections, are retained separately.

Two focused same-artifact probes do not reproduce their delays: the parser case
completes in0.036seconds, and the generated GPT seeded execution produces its
expected injected crash in0.901seconds. Both keep the original deadlines. The
GPT fixture remains retained with its process and I/O trace. These results do not
prove the cause, clear the full failures or qualify storage recovery.

Implementing-agent review supports the private corrected collection semantics.
DE-W074 remains partial while broad qualification is unresolved. Owner acceptance,
held-source/worker/frontend tree admission, full original0.1.0, other targets,
production writer/recovery and release gates remain open.
