# Native invocation evidence

Clean source: `90f91e1a2f529c12106fc46925f8c51b6b59f10e` on `goal/disked-0.1.0`.
Executable: `.aide-local/artifacts/DE-W011-90f91e1a/disked.exe` (403456 bytes).
SHA-256: `sha256:139e581258a9db76bcbe0047e5d489ed1ccbec902a28feb3fe6d0e0a2a13ef0d`.

An independent clean clone built and passed all nine native CTest groups, strict
producer-schema checks, structural checks and specification manifest verification.
`clean-commands.json` records exact commands, working directories, outcomes and
logs. `clean-results.json` binds inputs, compiler/configuration, host and artifact.
The source remains fake-only. Direct imports are KERNEL32.dll only.

`clean-launch-observations.json` retains actual direct/detached, cmd, Windows
PowerShell, PowerShell 7 and hidden test-console observations. The console tests
compare handles, modes, dimensions and code pages, verify explicit/inferred prompt
permission, and reject a screen-buffer handle as a prompt input channel. Native
policy runs 29 canonical fixtures and 270 comparisons with the abstract oracle.
Parser/JSON/reader/provider-guard tests remain enabled. The full spec suite recorded
160 tests: 158 passed, two symlink cases skipped. Structural checks: 883.

The retained artifact comparison shows malformed UTF-16 previously bypassed a
trailing machine-output flag; the new parser emits a framed diagnostic. It also
shows the previous build already handled the exercised absent-input cases; no
previous crash is claimed. Initial fixture errors and their explanation remain
in [the development review](REVIEW.md).

Only Windows 10 x64 build 19045 is exercised. Explorer, Windows Terminal/ConPTY,
SSH/RDP, scheduled tasks, file associations, XP/7/11, subsystem alternatives and
visible no-flash behavior remain unrun. Owner acceptance and DE-DEC-002 are pending.
The [partial handoff](../../handoffs/DE-W011-native-invocation-2026-10-06.json)
continues local development with DE-W013; it does not complete all of DE-W011 or
the full DiskEd 0.1.0 goal.
