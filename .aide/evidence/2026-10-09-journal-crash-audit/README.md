Repeated-crash journal reconstruction was built and verified from source `5adb71431d3b048eafc04d7de43fdc874f96466b`, based on `6422c1801396a4badc4843d396e28e539eb5785d`.

The clean reproduction results retain exact commands, logs, source input hashes, thirteen artifact hashes, actual Windows host/toolchain, product launch and PE dependency observations. Ten of 53 native groups were rerun; other 43 remain unverified at this revision. All 250 registered build inputs match their recorded hashes. The product excludes all five private journal libraries.

Use the retained `reproduce.py` from this evidence directory at the matching clean source checkpoint with the recorded toolchain and existing Python dependencies. The script was retained after the source checkpoint; copy or reference it from the evidence commit. It creates a local clone and requires unused output destinations. Different source/evidence commits produce different build stamps, and no byte-for-byte reproducibility across build paths/timestamps is claimed.

`FINDINGS.md` records two baseline defects and their corrections; `REVIEW.md` is implementing-agent review, not owner acceptance or independent safety qualification. The run is partial DE-W040 progress and does not finish DiskEd 0.1.0 or admit live storage writes.
