# Pending Windows elevation: retry guard

Base: `31bc56b767c3c7a8ca7e14bb7e908e25f125428e`.
The preceding goal turn made progress: it recorded the actual setup grant, tested
worker isolation/recovery and retained the ordinary-context mount refusal.

The committed COM-initialized launcher was attempted with `--elevate`. Its
requester remained live without a setup receipt or image. Only that exact
requester (76444, verified parent 67684 and command line) was stopped. The managed
workspace was removed. No setup helper or virtual image was observed.

Read-only CIM inspection found `consent.exe` processes 72136 and 43448 in Windows
session 1, with start times matching the two request attempts. Their command lines
are unreadable in this token. Ownership is not established by that correlation;
neither consent process was terminated. Both remained live after the requesting
controller exited. A requester exiting therefore does not prove prompt retirement.

The proof now reads a bounded live process snapshot before calling the elevation
API. Existing consent in its session blocks another request; unreadable session
metadata also blocks admission. A launch refusal gets its own receipt so it
cannot overwrite actual image/cleanup evidence.

Eight focused tests pass, including real Windows snapshot inspection and a
regression proving refusal occurs before a launch API is loaded. An actual
`--elevate` invocation then returned 78 without submitting another request. Its
receipt is `storage-elevation-admission.json`. The process-session query returned
access denied for both consent processes; the independent CIM observation above
provided their session IDs. No new image, profile or elevation prompt was created
by the refused invocation.

The helper now holds `Global\DiskEd.CappedScratch` for its entire setup/lease/
cleanup lifetime. A normal user-context test holds that actual mutex while
invoking the helper and verifies refusal before storage creation. This prevents
late approvals of obsolete requests from racing over the same image. The mutex
is released even if writing final state fails. It creates no persistent file.
The positive helper-contention test applies only to the granted local checkout,
host and user; other Windows environments skip that machine-bound case.

The snapshot uses Microsoft's [PROCESSENTRY32W](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/ns-tlhelp32-processentry32w)
metadata. [ProcessIdToSessionId](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-processidtosessionid)
requires process-query rights; unreadable session data remains unknown.

The complete tooling suite runs 97 tests: 96 pass and one existing execution-policy
skip. The final host-scope check was followed by eight passing focused tests.
Structural validation and manifest verification pass; the unchanged specification
suite was not rerun this turn. Sampled validation working data peaked at 497,714
bytes and all managed workspaces were removed.

The user grant is sufficient. The next necessary external change is completion
or cancellation of the relevant Windows UAC prompts at the VM console. Cancel an
obsolete DiskEd request whose controller has exited; do not approve it as though
its original proof runner were still waiting. Recheck
live OS state afterward, then execute the already-authorized 32 MiB proof. Do not
queue retries, weaken the storage gate, change UAC policy, terminate unrelated
processes or treat this as another missing-authorization question. The original
all-platform/storage 0.1.0 objective remains unchanged and unfinished.
