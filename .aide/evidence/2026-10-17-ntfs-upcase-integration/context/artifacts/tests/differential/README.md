# Partition parser campaigns

Read CONTRACT.md first. This directory adapts generated ordinary files to the
private native probes and installed external partition readers. All tests are
local; no installation, device, mount or product command is involved.

From Windows, after a native bootstrap build, run:

```text
python tests/differential/run_wsl_campaign.py --output .aide-local/campaign/example --mbr-probe build/windows-bootstrap/Release/mbr_probe.exe --gpt-probe build/windows-bootstrap/Release/gpt_probe.exe --probe-identity build/windows-bootstrap/generated/build-identity.json
```

The coordinator checks every native build input before reusing its probes. It
requires the already installed `Ubuntu-24.04` and `Debian` WSL profiles, invokes
Python explicitly as UID 65534 (`nobody`), and records failures if tools are absent.
It never installs dependencies. The Linux campaign scopes a Git ownership
exception to read-only metadata commands for this explicit Windows-owned checkout;
it does not modify global Git settings. Output directories must be new and within
the checkout's `.aide-local` tree.

The individual adapters also work directly in an unprivileged Linux environment:

```text
python tests/corpus/partition_images.py --output /path/to/new/corpus
python tests/differential/observe_external.py --corpus /path/to/corpus --output /path/to/new/observations --sgdisk
python tests/fuzz/run_campaign.py --corpus /path/to/corpus --output /path/to/new/faults --iterations 10000
```

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

Generated images, instrumented binaries and complete raw native probe output
remain in `.aide-local`. Durable evidence can retain the recipe manifest, tool
observations, source inputs, commands, coverage and any small failing input.
Neither agreement with another tool nor a completed bounded campaign proves
exhaustive correctness, source consistency, recovery safety or platform support.
