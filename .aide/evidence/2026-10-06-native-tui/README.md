# Native terminal frontend evidence

Clean source: `5012d858064ab3635e3ea0422e41345cbcf72a78` on `goal/disked-0.1.0`.
Executable: `.aide-local/artifacts/DE-W014-5012d858/disked.exe` (515072 bytes).
SHA-256: `sha256:69e65a64dc6d9ef53dcf9a8c7240cd18480ea2c80377b320b6ca592367d74069`.

A fresh local clone configured, built and passed all 13 native CTest groups,
strict response/graph/terminal producer checks, structural validation and
manifest verification. `clean-commands.json` records exact commands, outcomes and
logs; `clean-results.json` binds source inputs, compiler, configuration, host and
artifact. Direct imports remain KERNEL32.dll only. The exercised host was Windows
10 x64 build 19045, BLACKGLASS-WIN1\Jules, non-elevated.

Eight terminal-model tests cover shared-service parity, identity selection,
stale review, typed fields, inert paste/repeat input, explorer reachability and
bounded complete rendering. Fifteen native-console tests cover actual input,
screen and linear layouts, small/resize cases, explicit linear preference,
Ctrl+C key and signal handling, fault cleanup, unrelated mode-bit preservation,
inactive standard output, wrong-role input and unavailable channel refusal.
`clean-console-observations.json` retains the actual console observations.
Earlier protocol, parser, invocation, shared-service and provider-trap tests
remain active. Working specification validation recorded 163 passes and two
symlink skips (165 tests), 888 structural checks and 36 passive AIDE records.
Live AIDE integration remains unrun.

Reproduce from the source revision using the pinned toolchain in
[the build instructions](../../../docs/native-bootstrap.md):

```powershell
cmake --preset windows-bootstrap
cmake --build --preset windows-bootstrap
ctest --preset windows-bootstrap
& .\build\windows-bootstrap\Release\disked.exe tui
& .\build\windows-bootstrap\Release\disked.exe --tui --terminal=linear
```

The last two commands require a real console and are interactive. F10 exits.
CTest creates hidden consoles owned by the tests; it does not take over the
caller's terminal. The two renderers share the same model, command forms and
service. No physical provider, storage effect or persistent history is admitted.

Initial failures and review fixes are retained and explained in
[the agent review](REVIEW.md). Screen-reader, ConPTY, VT, remote, legacy-host,
clean-VM and forced-termination qualification remain unrun. The
[handoff](../../handoffs/DE-W014-native-tui-2026-10-06.json) leaves owner acceptance
pending; the programme grant permits local continuation to DE-W015. The full
0.1.0 goal remains active.
