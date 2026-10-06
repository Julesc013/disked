# First clean reproduction

The first independent clone at `eede529653a15f8be3ded35c53a4530b3cb52908`
built successfully and passed all seventeen native groups and the producer
checks. Its structural check failed: generated index/command-reference hashes
had been computed from CRLF working inputs which Git committed as LF.
`clean-structural.log` and the other root-level `clean-*` files retain that run.
No passing structural result or complete reproduction is claimed for that commit.

The authored inputs were normalized to their existing repository LF policy and
the generated index, command reference and manifest regenerated. No runtime
semantics or expected test outcomes changed. The corrected source is rebuilt in
another independent clone, with its evidence under `reproduction-<revision>/`.
