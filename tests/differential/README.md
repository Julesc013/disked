# Partition parser campaigns

Read CONTRACT.md first. This directory adapts generated ordinary files to the
private native probes and installed external partition readers. All tests are
local; no installation, device, mount or product command is involved.

The historical `run_wsl_campaign.py` recipe is suspended. It requires generated
output in `.aide-local`, which now permits only 32 MiB of context and metadata.
Do not run it under the current resource policy. DE-W106 must migrate the
coordinator and prove managed output/confinement/cleanup before reuse. The
direct collector CLIs are also suspended. The coordinated APIs emit finalized
packet records through a supplied runner; no actual worker/campaign is admitted.
`adapter_controls_passed` alone cannot qualify a complete campaign.
See [the planned correction](CONTRACT.md#planned-evidence-boundary-correction-de-w106).

The initial DE-W106 preparation now checks an explicitly declared observation
set and rejects omissions, duplicates, unexpected records and fixture mismatches.
Set-only receipts still leave evidence unverified. The opt-in finalized-packet
profile checks participant identities, raw artifacts, preservation and execution
outcomes against a caller-bound manifest. The CLI requires `complete_success`;
offline consistency tests do not qualify an actual campaign or worker.
The Windows-host regression suite exercises pure comparison code only, with
Linux execution checks explicitly skipped. DE-W105 and external campaign gates
remain open.

Comparator CLI inputs and output must be beneath the runner's
`DISKED_WORK_ROOT`, outside the repository. Use explicit
`--external PARTICIPANT=PATH` arguments. Duplicate participant names, linked
paths, duplicate JSON fields and oversized receipts are refused. Existing
reports are preserved. These checks route data; they do not establish an OS
quota or qualify an external worker. The historical WSL entrypoint now refuses
before any output creation or subprocess launch.

For a finalized packet, pass its precollection canonical manifest digest with
`--expected-manifest-sha256` and its managed packet folder with `--artifact-root`.
See the [private binding profile](CONTRACT.md#provisional-finalized-packet-bindings).
Old collector output remains unverified; it is not silently upgraded into this
format. The new collector APIs use shared declaration validation, fixed adapter
commands, distinct copies, bounded raw artifacts and per-call checkpoints. Their
runner must supply a measured identity and terminal process-tree result. An
exception preserves an unfinished call without retry or a quiescence claim.
Pure projections run on Windows too, while Linux process tests remain
explicitly platform-specific. Both GPT candidates and complete disagreements are
retained independently of the evidence-completeness result.

The coordinator checks every native build input before reusing its probes. It
requires the already installed `Ubuntu-24.04` and `Debian` WSL profiles, invokes
Python explicitly as UID 65534 (`nobody`), and records failures if tools are absent.
It never installs dependencies. The Linux campaign scopes a Git ownership
exception to read-only metadata commands for this explicit Windows-owned checkout;
it does not modify global Git settings. This describes the historical runner,
not an admitted current execution profile.

The campaign owner must freeze a manifest before invoking
`observe_native.collect` or `observe_external.collect`. Both require explicit
tool paths, the measured participant identity and the owning qualified runner's
execution callback. See the [collector contract](CONTRACT.md#coordinated-collectors-private-execution-qualification-pending).
There is no admitted standalone campaign entrypoint yet. The old direct CLIs
refuse before output or subprocess creation. The existing Linux `run` helper is
not by itself proof of process-tree, storage or worker qualification.

External dependencies are installed `sfdisk`, optionally `sgdisk`, Python, and
GCC/G++/gcov with AddressSanitizer and UndefinedBehaviorSanitizer. The native
observation adapter uses the Windows test probes from W021/W022. The GCC campaign
compiles the same C90 readers directly; the mutation harness is C++14 test code.

The result captures exact source/tool/artifact hashes, source-package versions,
commands, native findings, external diagnostics, discrepancies and coverage. Raw
invalid UTF-8 is retained as hex with a digest. Invalid JSON is retained without
inventing a table projection. Expected detector failures count as successful
positive controls only when the intended diagnostic is actually observed.

A mutation run logs the seed, iteration, seed image, byte length and CRC32 before
calling a parser. On a failure, the runner deterministically reconstructs that
input, checks its checkpoint and records a SHA-256 receipt. The same path is
tested by an intentional campaign failure. Reproduce a retained iteration with
the recorded `--emit` command and original ordered seed files. Coverage reports
name both the source file and translation unit, preserving system-header rows.

Generated images, instrumented binaries, caches and raw probe output belong only
in the owned managed campaign workspace, within its existing aggregate limits.
Retain compact verified evidence before cleanup: recipe manifest, tool identities,
commands, structured outcomes, bounded raw observations and a small failure input.
Do not accumulate images or duplicate archives. Windows API/UI reference work is
planned in DE-W107; see [the reference plan](../../docs/windows-reference.md).
Neither agreement with another tool nor a completed bounded campaign proves
exhaustive correctness, source consistency, recovery safety or platform support.
