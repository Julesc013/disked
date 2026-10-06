# DE-W017 initial findings (working tree)

The baseline `baseline-gui-blocked.json` records three timed-out GUI message
probes during the five-second test-only worker delay at source `9ba3311f`.
Initial targeted tests then exposed a worker inheriting and pinning the GUI's
launch directory. The worker now selects its explicit state directory as CWD.

The first aggregate test failed waiting for one job member. Follow-up native
queries observed the owned delayed executable plus `C:\Windows\System32\conhost.exe`
in the job. `CREATE_NO_WINDOW` still produced that hidden console host on this
host. Switching to `DETACHED_PROCESS` produced four executable-only members and
prevented a fifth launch. A test constant for combined job flags was also corrected
to the SDK's `0x308`; production used the SDK constants throughout.

The first memory probe's private expected marker rejected Windows error 1455
(commitment limit). The test-only worker now retains the actual Win32 allocation
error in its exit code; the repaired probe observed 120,520,704 peak committed
bytes, below the configured 134,217,728 limit, and error 1455. It retained unknown
operation state with no automatic re-execution. These working-tree records are
not evidence for the later committed executable; clean reproduction follows.

An initial request-channel fixture supplied a scalar result, contradicting the
response contract. The fixture was corrected to use an object; product validation
remained strict. A later allocation-failure regression denies all further C++
allocations on the callback thread and verifies the preallocated unknown receipt.

GUI current-plus-earlier replies previously reused the single-response rendering
bound. A regression with two 60,000-byte payloads verifies both remain intact in
the private composite display; public response bounds remain unchanged.

The first full specification run retained under `working-1/` ran 169 tests with
seven context-fixture errors/failures and two skips: DE-W012 required 181,983 bytes
and correctly refused the former 180,000-byte fixture allowance. Binding tests
now explicitly allow 260,000 bytes. Artifact budget refusal remains one byte;
existing small-content-budget/no-output tests remain unchanged. No production
context budget or truncation policy was relaxed.

The repaired full native run passed all 23 groups. A separate raw-console
measurement then read a partial frame between writing the outcome header and
redrawing the editable prompt. The fixture now waits for the unchanged draft
after that new outcome, preserving the same navigation latency criterion and
failing if the draft is lost. The original failing observations remain in
`working-2/console-waiting.json`; no implementation outcome was changed to pass.
