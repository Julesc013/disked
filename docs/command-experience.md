# Planned command and terminal experience

The [native bootstrap](native-bootstrap.md) implements human help, build identity and command discovery. The full command contracts, machine output and other interfaces remain planned. The [generated command reference](../spec/generated/command-reference.txt) lists all 34 planned descriptors, their registered alternatives and global controls from the canonical catalogs. The examples here describe intended behavior, not an installed CLI.

You should be able to append what you forgot. These proposed forms have the same meaning:

```text
disked --json target list
disked target --json list
disked target list --json
disked list --json
disked list --json targets
```

Global and selected-command options may move before, between or after command words and operands. Keep each separated option and value together, as in `--format json`; the attached form `--format=json` also works. An option still belongs to its command: moving `--length=50GiB` earlier does not make it valid for target enumeration. Parsing finishes before output files, device discovery or frontend initialization.

`--` ends option and command-word recognition. In `disked image inspect -- --json`, the final token is a literal image filename. Unknown flags, inferred prefixes, duplicate non-repeatable options and contradictions are errors. Appending `--json` is convenient; appending it after an explicit `--format=human` is a conflict, not an override.

Use `list` (also `ls` or `list targets`) for target enumeration, `show TARGET_ID` for target inspection and `commands` for command discovery. `show` never guesses whether an identifier belongs to a plan or operation. Registered `part`, `fs` and `op` command forms remain available alongside full names. The earlier unreleased `tgt ls` proposal is retired. These choices need user testing; character count alone does not establish convenience.

`--help`/`-h` works wherever an option may appear. `disked help partition resize` and `disked partition resize --help` provide the same contextual help without requiring a real partition or provider. Help and completion show canonical forms and aliases. Errors in the persistent shell preserve the editable line and identify the token to fix. Prefix suggestions require explicit selection; execution does not guess.

One-shot CLI, machine output, the explicitly selected `disked shell`, TUI and native GUI share action meanings and target identity. `--cli --interactive=yes` permits prompts through a usable human channel; it does not open a persistent shell. JSON/NDJSON remains noninteractive. `--headless` selects CLI/noninteractive behavior without implicitly selecting JSON. Resize and formatting forms still construct plans.

Terminal behavior depends on actual input/output capabilities. Qualified DOS local or Win32 consoles may supply text widgets without VT. Rich colour, mouse, Unicode, transient prompts and live status are optional; complete keyboard and linear presentation preserve meaning on narrow, monochrome, redirected and constrained channels. Completion/history/paste stay inert until submission. Tab never scans devices, obtains privileges or acquires providers.

Progress distinguishes completed and verified work, unknown totals and waiting. Captured output contains complete records. Exact source values remain separate from escaped terminal text. History, transcripts, diagnostics and recovery journals have distinct ownership, bounds and privacy rules.

Contracts: [commands and parser boundaries](../spec/interaction/commands.md), [invocation](../spec/interaction/invocation.md), [terminal sessions](../spec/interaction/terminal-session.md), [shell](../spec/interaction/interactive-shell.md), [output/progress](../spec/interaction/output-and-progress.md). The [syntax corpus](../spec/fixtures/command-syntax.json) contains native test expectations; current metadata checks do not execute a DiskEd parser. Implementation and qualification belong to DE-W012/018/019/071.
