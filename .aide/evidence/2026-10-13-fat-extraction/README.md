# Complete mapped FAT extraction evidence

Native source `20ecddbd153a2a016b02d8c49c4092ddedc99f9e`, development base
`dc56b190409581af95ee7a765175acd8f3db5dfc`. Exact tested source and integration
revisions are separate. Local implementation/tests/agent review/dev-main promotion
is authorized; owner, signing/publication, physical and installation gates remain.

The clean Windows campaign passes 104 native groups, complete-file extraction
cases in 9 methods, the prior 209 content-map and 59 held-file cases, 20 selected
standalone headers and 226 tooling passes with two skips. Summary/detailed cases retain actual counts;
polling observations vary with process timing. Source blobs, toolchain, imports,
launches, contexts, artifact hashes, full commands and logs are retained. GCC is
strict C90 syntax only; no GCC runtime/ABI or historical-host qualification.

The existing acquisition engine now admits a private plan2 logical FAT source and
separate backing-image resource. It copies the complete mapped file across windows
and acquisition chunks, including files larger than 1 MiB and empty files. Explicit
exact grants, no-clobber, aliases/capacity, flush/readback, checkpoint/pending/seal
records and resume remain in the existing engine. Before/after metadata and repeated
payload agreement guard logical reads. No zero substitution or retries are admitted
for this FAT byte-content profile. Raw plan1 semantics remain unchanged.

Independent tests check FAT12/16/32 fragmentation, source hashes, exact complete
destination bytes/maps, slack/EOF, preparation without outputs, refused selectors/
grants/aliases, partial writes/resume and altered source/checkpoint data. Actual
contained acquisition-worker preparation/execution is tested; operation finish and
real process exit are distinct from completed observation reads.

Development diagnostics retain the initial harness mistake: it treated a completed
observation read as operation completion, indexed a null outcome and attempted
cleanup while a child still held its cancel file. The harness now inspects finished
phase and waits on the actual owned process. The diagnostic note is an attributed
tool-output observation, not a reconstructed full native log or a passing result.

The failed campaign at source `a40c7b43` remains under failed-a40c7b43:
101 of 104 groups passed and three fault-command groups failed. The new acquisition
dependency had pulled the normal FAT file provider into the fault product, bypassing
injected failures. The repair captures metadata directly through the acquisition
source handle and the existing closure checker excludes normal file/snapshot/worker
targets from the fault product. Focused repaired groups and a fresh full campaign
are recorded separately; the old failure is never reclassified as a pass.

This qualifies a private complete-file backend, not public command/frontends,
recursive/timestamp/ACL fidelity, larger coherent maps, mounted consumers, physical
power loss, production journal/recovery, owner acceptance or full 0.1.0. Reproduce
with the exact source and fresh output using reproduce.py. audit_retention.py checks
retained integrity/source binding; it does not rerun native tests.
