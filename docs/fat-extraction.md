# Complete mapped FAT file extraction backend

DE-W047 copies a complete selected FAT logical file through the existing
ordinary-file acquisition engine. The [owning profile](../spec/catalog/fat-extraction-prototype.json)
defines expected behaviour before evaluation. This private backend is the next
step toward public extraction; no new public command is admitted here.

The selector binds a basic/default FAT capture's metadata digest, node, file size,
volume window and FAT copy. Source generation, code and parents remain independently
bound. The acquisition provider captures metadata through its held source handle,
rereads the captured regions and confirms the native generation before building
a checked logical content map. It does not depend on a second concrete FAT file
provider; normal and fault-test provider compositions remain separate.
Names from disk never become paths. The destination and checkpoint-map paths are
explicit inputs, with no-clobber creation after an exact execution grant.

Private plan2 distinguishes logical source bytes from a backing-image resource
with actual image identity, extent, aliases and failure domain. Both declared read
resources are covered by the source-read grant. Destination/map/host/code boundaries
retain their existing checks. Raw plan1 and its map/worker behaviour remain unchanged;
an older reader must reject plan2 rather than interpret it as a flat image.

Extraction supports the entire file represented by the bounded metadata map,
including empty files. It does not stop at one 196,608-byte window. Acquisition
chunks split into checked content windows and native pieces. Captured metadata is
reread around each logical source read; payload is reread and compared before that
chunk is committed. Slack never appears as file content. Ordinary/stop/zero-retry
policy is required; substitution cannot fabricate file bytes.

The engine reuses pending/checkpoint/seal records, flush ordering, destination
readback, capacity checks and uncertain-effect handling. Resume binds the exact
selector and logical/backing/code generations and reverifies covered source and
destination bytes before repair or further writing. A completed observation read
does not mean an operation finished; clients must inspect its operation state and
actual process exit.

This is byte-content extraction. It does not restore timestamps, ACLs or other
filesystem metadata, recurse through trees, mount images, qualify an atomic
snapshot or access physical devices. Larger coherent maps, public command/frontend
admission, further filesystems/hosts, production recovery and the unchanged full
all-platform/storage 0.1.0 remain subsequent work. Owner/release gates stay separate.

Exact source `20ecddbd` passes complete mapped-file extraction cases, 104 native groups
and 20 standalone headers in the recorded Windows lane. [Retained evidence](../.aide/evidence/2026-10-13-fat-extraction/README.md). This is complete-file backend qualification;
public extraction, future source freshness and full product/owner admission remain
separate. Historical failures retain their actual outcomes.
