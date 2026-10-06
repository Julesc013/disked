# DE-W019 local agent review

Reviewed source `9ba3311ff948319841fe881a7e0c8a4ec5036312` against base `ed13e5014a09d1b245684f63814c1439aa53811d` and the DE-027 execution
contract. This is review by the implementing agent under the programme grant,
not independent security review or owner acceptance. The acceptance ledger is
unchanged. The bounded local slice can feed DE-W017 after the retained clean
checks; remaining human/terminal qualification keeps DE-W019 at needs-review.

- Shared dispatch preserves command IDs, typed parameters, graph revision checks,
  refusals and fake-worker operation identities. The shell introduces no planner,
  physical provider, elevation path, OS shell expansion or implicit target operand.
- Every accepted edit/recall/completion/selection invalidates review. F9 review is
  consumed before a callback; held activations and Enter cannot dispatch. The
  lexer has explicit byte/token limits and literal Windows-path quoting.
- Completion reads the static registry and cached graph. History is off by default,
  bounded and memory-only. Schema-marked secrets suppress history and retained
  output details. All displayed metadata is escaped; oversized presentation reports
  an unavailable marker without retrying the command.
- Console ownership is limited to existing mode bits, a private screen buffer or
  one linear prompt row. Native tests prove normal/Ctrl+C/failure restoration on
  this host. Resizing never grants authority or authorizes submission.
- Review corrected off-screen candidate focus, active-shell mode reporting,
  suppressed-but-retained secret output, silent stale clear-selection results,
  oversized rendering failure and excessive explorer transcript detail. Regression
  tests exercise the affected paths. GUI tests now compare catalog identities
  instead of a frozen count after adding the canonical session-close command.

The 19 clean native groups and full specification suite pass. The fake operation
producer checks, clean binary hash/import observations and real console traces
are linked from README. Synthetic timings do not satisfy human usability claims.
File-API stalls, aggregate operation budgets, late observations and broader
frontend responsiveness are DE-W017 work. No passing fake-shell test qualifies
production storage effects, privileged code or another platform.

Next safe action: DE-W017: run and repair the combined fake-provider/frontend resilience campaign, with explicit worker/resource/event ceilings and stale-observation guards. Preserve unknown outcomes and separate production storage/privilege gates.
