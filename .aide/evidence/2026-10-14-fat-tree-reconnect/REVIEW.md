# Partial implementing-agent review

Ownership follows the existing boundaries: supplied-data parsing in runtime,
actual local file/process checks in the Windows adapter. The old private plan
and historical request1 meaning remain intact; only new producers emit request2.
Controller/writer PID reuse and changed executable generations are unresolved,
not liveness. Recorded exit is explicitly weaker than a currently held process
observation. Cancellation is gated by intact state and two matching live owners.

The admission owner forwards cooperative cancellation. It stops writing
observing records after publication, preserving the terminal-history contract.
Strict chain fixtures include rehashed contradictory records, incomplete tails,
changed control children, outcome withdrawal/change and published-before-exit.
Actual second-caller cancellation plus existing admission regressions pass.
The current controller remains caller-owned; no detached/public-command/full
work-unit acceptance is claimed. Later native wait/watch and frontend gates
remain real. This is implementing-agent review, not independent owner approval.
