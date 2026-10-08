# Observation implementation findings

The initial public observation run passed replay and reader checks, then failed
on a guessed expected exit for selecting a fake operation against an acquisition
directory. The established fake observer refuses absent fake metadata with exit
2 and operation_request_unavailable. The assertion was corrected to that existing
contract and strengthened to verify no acquisition metadata changes. The raw
failure log is retained; corrected working and clean full runs supersede it.

Implementation review added full-binding retention and monotonic coverage checks
to the reader. Validly rehashed changed bindings or regressing counters cannot
advance its cursor. A torn history exposes a verified prefix but remains unknown;
corrupt complete records are rejected without repair. The tests independently
hash emitted worker records and compare actual byte/map results.

Public acquisition inspect/cancel and CLI/stdio watch are now implemented. The
actual copying entrypoint remains in a private probe. Visible GUI/TUI/shell copy
review/submission and interactive response/rendering qualification remain open.
The provisional records are not the production journal ABI and these Windows
generated-file results do not qualify other platforms, physical or failing media,
power-loss recovery, privileged operations or a release. Owner acceptance is empty.
