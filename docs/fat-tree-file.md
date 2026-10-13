# Held-file tree paging

DE-W054 connects the paged FAT controller to ordinary Windows image files and
owned child processes. `providers/image/fat_tree_file.*` owns one source handle
and its pinned ancestor closure. `fat_tree_snapshot.*` owns the private request,
frame checks and pure parent replay. `platform/windows/storage/fat_tree_worker.*`
owns the page channel and delegates process lifetime to `ObservationWorker`.

The opened source must match the exact expected metadata before reads. Existing
local-path, reparse, hardlink, ordinary-file and recall/tiering refusals apply.
The handle permits read sharing throughout the traversal. Each bounded region is
read again; bytes, read errors, metadata observations and agreement are retained
as separate facts. Agreement does not prove an atomic snapshot or future access.

The child publishes through one anonymous 2 MiB slot. Publication, consumer-copy
and acknowledgement states prevent overwriting an unconsumed page. The parent
copies the packet, checks its digest and real process/code/request/epoch context,
then independently reconstructs the page from its recorded regions and checks.
Only that owned session can construct an immutable retained page. Pure replay
opens no file and authenticates no process.

The slot is reused for the next page; it is not a whole-tree size cap. Caller
retention is separate from the worker's bounded current-page state. Final
publication binds the received count and final page digest. A final receipt and
actual process exit remain separate observations. Cancellation requests no new
authority; hung or late workers retain ownership until exit is confirmed.

The existing process host supplies image/parent pinning, anonymous inheritance,
startup admission, jobs, memory and aggregate worker budgets. No second scheduler
or larger host payload limit is added. Windows maps `FILE_MAP_WRITE` as a read/write
view, as specified by [Microsoft](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-mapviewoffile).

Normal builds reject fixture controls. Separately compiled tests alter source
receipts, pages, process/epoch context and replies, and exercise cancellation,
hangs and startup failures. Retained pages remain historical after a failure or
retirement. They grant no present source access or mutation authority.

Focused development passes 57 cases, including a full 17,601-entry tree exceeding
8 MiB aggregate publication, nonzero/conflicting FAT copies and long-name page
continuity. Exact clean source qualification is pending. This private path opens
ordinary files without mounting or creating output files. Public traversal,
recursive extraction, metadata restoration, other hosts, owner/physical/production
recovery and full 0.1.0 remain separate work.
