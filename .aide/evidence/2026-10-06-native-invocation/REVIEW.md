# DE-W011 local invocation slice: development review

Reviewed by the implementing agent on 2026-10-06 under the user's explicit local
cross-unit continuation policy. This is not independent review, owner acceptance
or a shipping subsystem decision.

The native policy shares the specification's decision order and passes the
canonical cases plus a 270-case cross-product. Real adapters pass composition
availability explicitly; an unavailable auto-selected TUI produces plain help,
while explicit unavailable GUI/TUI requests are refused. `mode.explain` reports
actual channels, policy inputs, selection and the same host's bare-launch decision.

Windows observations do not open replacement handles, consume input, enumerate
storage or change console attachment, visibility, modes, code pages or dimensions.
Console sharing is conservatively protected; membership does not prove creator
identity. A bounded process list and input/output buffer queries support the
reported facts. An output screen buffer supplied as stdin fails the verified
prompt-channel check. Unknown desktop/display intent remains explicit.

Real process tests cover pipes, files, absent/invalid handles, cmd, Windows
PowerShell, PowerShell 7, and inherited console children. The console fixture
creates its own hidden console and compares state before/after each child; it
never attaches to the user's existing console. Explicit and inferred CLI prompt
permission agree. No synchronous handler actually asks for input.

The first fixture incorrectly used CREATE_NO_WINDOW to represent absent handles;
Windows still supplied console handles. It was corrected to DETACHED_PROCESS,
with actual handle-kind assertions retained. cmd needed a cmd-specific command
line rather than C-runtime argument quoting. A custom console-handle case needed
explicit inheritance. These are fixture corrections, not changed product
expectations. Initial failing output is retained separately.

The old executable already completed build inspection and diagnosed missing
transport input on the observed detached host; no old crash is claimed. The
artifact comparison does establish a real defect: malformed UTF-16 returned
human stderr even when a later `--json` requested structured output. Passing the
encoding error through the complete parser fixes that framing mismatch. Negative
CRT descriptors are now guarded, and unavailable output/input have explicit
outcomes without attempting unusable streams.

The nine CTest groups also retain parser, JSON, strict response/compatible-reader
and poison-provider checks. The native boundary continues to be fake-only. Exact
logs, source inputs and executable hashes are separate from this narrative.

DE-DEC-002 remains proposed: Explorer, Windows Terminal/ConPTY, SSH/RDP, scheduled
tasks, file associations, XP/7/11, a Windows-subsystem/AttachConsole alternative
and visible console-flash behavior are unrun. This local slice does not complete
all DE-W011 host qualification. Continue with DE-W013's fake resource graph while
retaining those outstanding launch claims and the empty acceptance ledger.
