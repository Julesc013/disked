# Private report exit-wait diagnostics

Qualified test/helper source `b5d6ddfca183d95408d488a17773fd433f59f20c` against exact native producer `f7b4376fe4ec4a88d07252f3feb25ee97e654a14`.
The product, separate fault executable and parameter probe retain their original
source/hash identities. The 493-input comparison changes exactly three private test
files; all production/native inputs are byte-identical. No new product executable,
full-product qualification or original parallel-delay fix is claimed.

The existing report-worker test owns report_exit_observation: one actual wait on
the caller's creation-verified handle with the original hardcoded3000-ms budget,
raw result and monotonic elapsed time. It opens/closes no handles and does not
authorize retries or infer exit from a receipt. Image-lookup fallback and product
export keep their original actual-signaled==0 guard, diagnostic prefix and full
identity/state details, adding wait evidence to failures. No runtime file/name,
public command semantics, deadline or test failure criterion changed.

Five owned Python child journeys pass 18 checks: normal and
actual exit, reused creation identity, live lookup timeout and a scoped simulated
WAIT_FAILED. The fault is harness data, not an observed Windows API outage. Caller
ownership of the retained signaled handle is independently checked. Clean actual
joined-export CLI/stdio/GUI/TUI/shell runs pass 286 checks
against the separately bound existing PEs. All semantic check identities from the
prior diagnostic remain and all observed checks pass. Tooling213passes/twoskips,
1075structural checks, index/manifest/source-map and source-bound context pass.

The first qualifier wrongly assumed the previous isolated run's281 count was fixed.
The native test actually passed286: five additional successful completion-observation
CLI calls. Unique semantic check-name sets are identical. The corrected qualifier
checks those exact identities, all passed observations and count/list consistency.
It revalidated the unchanged clean source and all493inputs/three PE hashes before
continuing tooling/spec checks with the original successful native runs. Original
qualifier/error log and continuation are retained; no native test was changed to
hide a failure. Initial uncommitted owned-child18 pass remains diagnostic only.

Source and artifact byte audits bind the test source and historical producer
separately. The earlier six-wait isolated trace and original exact failed fixture
remain in joined-report-waits evidence. Earlier parallel exit-delay cause stays
unestablished. DE-W030 and the full all-platform/storage0.1.0 goal remain active,
with no owner/live/provider/physical/other-host/writer/recovery/release admission.

Reproduction: use reproduce.py from the repository root, the recorded clean local
clone and source-bound f7 producer PE copies. Its default output is
.aide-local/report-exit-diagnostics-clean; use a fresh workspace/output location
or --resume only to continue the same unchanged qualification. Logs record exact
commands. Broad77-group product evidence remains at its original producer revision.
Next: a finite instrumented parallel campaign can examine future occurrences,
preserving every timeout and real exit/identity requirement; continue independent
programme implementation without unlimited attempts to reproduce an old event.
