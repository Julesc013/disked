# Contained native namespace: focused review

The focused private native namespace passes at source
`57578ab08541e22f6cdfadc8c9db43ff182f59bb`. Full current product qualification
is still pending; this review does not admit a public provider or complete DE-W030.

The distinct compiled native child uses the fixed Windows namespace table and
rejects caller-supplied provider input. Typed native bindings remain separate
from fixture bindings. The injected role still refuses native and mixed tables.
Namespace graphs and retained inventory publications use the existing capture,
epoch, retirement and immutable ownership contracts. Product entrypoints and
fake-only defaults are unchanged.

Both x64 and Win32 passed all 15 predefined native cases. Each architecture also
passed the existing adapter (49 controllers/258 assertions), contained worker
(24/116, 18 actual children) and graph (30/1,103, 26 actual children) regressions.
The gate includes malformed child inputs, cancellation before dispatch, bounded
gate waits, partial coverage, refresh, immutable publication and binding rejection.
An entered checkpoint proves collector dispatch, not entry into a kernel API.

The campaign ran in the Windows 10 guest, build 19045.7548, through the Agents
coordinator and an ordinary confined worker in the demonstrated 32 MiB cap.
MSVC 19.44.35228 and SDK 10.0.19041.0 identities, exact arguments, executable
hashes, import observations and all new native streams are retained.
The 60 execution-port calls include the original eight containment controls.
The archive is 46,684 bytes: 111 entries and 933,737 original bytes. Old regression
summaries, entry hashes and selected guard streams are retained; not every old
successful payload is retained. Generators remain available.

[Replay](capture/replay.json) verifies source blobs, closed case sets, port results,
stream hashes, archive entries, graph labels and original UTF-16 target witnesses.
[Fresh cleanup](capture/cleanup-live.json), observed at 07:29:28 UTC on 21 October,
found no owned processes, inaccessible owner queries, qualification root, scratch,
actor, profile directory, hive or profile key. Guest system free space was
96,786,976,768 bytes. The host workspace peaked at 1,414,167 bytes and was removed.
The VM backing file's logical length was unchanged; allocated growth was not measured.

Three failed attempts remain: compile errors at `a454bf0d`, an observation-checker
label-location error at `c771e000`, and an exclusive artifact-label collision at
`d28b9b9b`. Their resources were retired. Repairs preserved product guards and
expected outcomes. The corrected checker also replays the retained first 11 cases.

The native source and contract inputs match the Git blobs at `57578ab0`.
Two generated specification projections were dirty during that run; they were
not native compilation inputs. They will be regenerated and committed before
the full qualification snapshot. This is not a claim of an entirely clean
metadata checkout at the focused source revision.

Next: qualify the full current x64 product and applicable private Win32 slice
with complete DE-W030 inputs, then run repository checks and review before
integration. Other Windows builds, XP, physical identity and access, public
provider admission, owner acceptance, release and full 0.1.0 remain unqualified.
