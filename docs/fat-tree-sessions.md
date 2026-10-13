# Paged FAT tree sessions

DE-W055 exposes the held-file page reader through `filesystem tree`
(`filesystem.tree.inspect`). Its phases are `open`, `next`, `read`, `status`,
`cancel`, `close`, `list` and `scan`. The default is `list`. Static discovery and forms
derive from the canonical command descriptor and parameter schema.

Sessions last for the current product process. Protocol, shell, TUI and GUI can
make successive requests. A one-shot CLI invocation cannot reconnect after its
process exits. One-shot traversal uses `--phase=scan --format=ndjson`; protocol clients also
require explicit `org.disked.fat-tree-events/1` negotiation. Stream opened/page/
record-chunk envelopes preserve the256-request/four-MiB input-session limits.
Default4096/max65536 pages and default/max30000ms no-page-progress wait are
finite configurable budgets. Final publication, coverage and exit stay distinct.
Streaming qualification is in progress.

`open` requires an ordinary image path and exact volume offset/length. Optional
copy, traversal and page limits are validated before source access. The source
and ancestors stay pinned, and the same owned worker supplies every page.
There are four reserved/owned slots. An outstanding open keeps its reservation.
Busy requests refuse; a global session lock does not span provider I/O.

`next` polls without waiting for an entire tree. A published page includes its
semantic events, source binding, sequence/digest chain and exact owned context.
Its receipt binds the latest copied frame/context record. `read` retrieves
hex-encoded JSON bytes in chunks of at most 196608 bytes, selected by session
and exact page sequence. Advance only after retrieving needed bytes: the next
page replaces the latest record, and old selectors then refuse. The 2 MiB
record bound applies to one page; it is not a whole-tree limit.

Cancellation preserves historical copied bytes. A close request cancels/retires
the reader, retaining its slot and dependencies until actual exit is observed.
Final publication, cancellation and exit remain distinct observations. Source
hash agreement is neither an atomic snapshot nor future access authority.

Runtime owns reservation, command semantics and copied record retrieval. The
Windows adapter owns actual file/ancestor/process lifetimes and delegates page
transport to the existing contained worker. No physical access, mount, source
write, extraction destination, production ABI or new scheduler is introduced.

Implementation and qualification are in progress. The broader platform/storage
0.1.0 scope, recursive extraction/metadata restoration and separate owner,
production, privilege and release gates remain.
