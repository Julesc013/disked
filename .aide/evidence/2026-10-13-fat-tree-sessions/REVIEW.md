# Implementing-agent review

Reviewed session reservation and per-entry locking, exact page chain/binding and
source checks, immutable latest-record retrieval, stale selectors and retained
history after failed publication. The runtime port performs no host I/O; native
cursor/source/process ownership stays in the Windows adapter. The source and its
ancestors remain held through actual exit, including failed launch cleanup.

The stream owns its session while output is emitted. Other page/record/close
requests refuse busy; status/cancel remain observations/actions within the existing
entry guard. Page and record-chunk events use explicit negotiation and finite
page/progress budgets. Channel failure, uncertain publication and retirement do
not authorize a replacement. Close keeps completed cancellation facts unchanged.
One-shot NDJSON and process-lifetime frontends share the same native provider.

Native session, complete large-tree, actual GUI/TUI/shell and normal/fault results
support this Windows prototype. All existing native groups pass at the frozen
source. This is implementing-agent review; owner/independent safety acceptance,
other hosts, recursive metadata effects and full0.1.0 remain separate work.
