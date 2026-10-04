# Planned command and terminal experience

DiskEd has no native command handlers yet. The [canonical registry](../spec/catalog/commands.json) describes planned commands; all examples below are design examples.

One-shot CLI, machine output, an explicitly selected persistent shell, TUI and native GUI share action meanings and target identity. `--cli --interactive=yes` permits prompts through a usable human channel; it does not open a shell. Missing prompt channels produce an explicit error. JSON/NDJSON remains noninteractive. The persistent entry is planned as `disked shell`.

Registered shorthand such as `tgt ls`, `part resize`, `fs format` and `op watch` expands to the canonical descriptor. Execution does not guess prefixes. Completion, history and multiline paste remain inert until submission; Tab never scans storage or obtains privileges. Formatting and resize shortcuts still construct plans.

Terminal support depends on the actual input/output channels. Qualified DOS local or Win32 native consoles can use their own text/input facilities; serial or captured channels may need plain output. Keyboard-complete linear presentation, monochrome text and narrow layouts preserve action and target meaning. Modern colour, mouse, glyphs, transient prompts and live status are optional capabilities, with measured backend support required.

Progress distinguishes completed and verified work, unknown totals and waiting. Captured output contains stable records rather than redraw frames. Terminal data is escaped separately from exact source values. History, presentation transcripts, diagnostics and recovery journals have distinct bounded storage and privacy rules.

Contracts: [commands](../spec/interaction/commands.md), [invocation](../spec/interaction/invocation.md), [terminal sessions](../spec/interaction/terminal-session.md), [interactive shell](../spec/interaction/interactive-shell.md), [output/progress](../spec/interaction/output-and-progress.md). Implementation belongs to DE-W011/012/014/019 and the fake failure campaign; platform/runtime tests remain unrun.
