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

## Shared command development

DE-W048 adds the provisional `filesystem extract` command to the current native
composition. Its [owning contract](../spec/catalog/fat-extraction-command-prototype.json)
was recorded before implementation. [Exact-source qualification](../.aide/evidence/2026-10-13-fat-extraction-command/README.md) at `8d1905b9` passes 106 native groups and 20 selected headers in the recorded Windows lane. All 11 complete copies and native interface/cancellation/resume journeys are retained; production and other-host gates remain.

Inspect an explicit FAT volume with `image inspect SOURCE --view fat
--volume-offset OFFSET --volume-bytes LENGTH`. Each basic file row supplies an
`extraction_selector` object. Auxiliary, allocation-window/scan and name-consumer
views do not supply that basic selector. A selector is comparison evidence;
preparation independently checks the current held source and complete mapping.

Prepare with `filesystem extract prepare SOURCE DESTINATION --map MAP
--state-dir EXISTING_EMPTY_DIRECTORY --selection-json SELECTOR_JSON`. Review the
returned definition and digest. Execute with `filesystem extract execute
--definition-json DEFINITION_JSON --definition-digest DIGEST --allow-source-read
--allow-destination-write --allow-map-write --allow-host-effects`. Shell, TUI, GUI
and machine requests use the same descriptor/service. Their review step does not
grant effects without those explicit execution fields.

Logical definition2 binds logical plan2; raw definition1 remains raw plan1.
Logical requests retain ordinary/stop/zero-retry semantics. Existing outputs,
aliases, stale selectors and contradictory definitions refuse. Reconnect, watch
and cancellation use the common acquisition operation ID and explicit state root.
An observation response is separate from the operation outcome and worker exit.

Compiled read-only catalogs use a separate finite parsing budget of 256 KiB and
32,768 values. External request framing remains 64 KiB; typed definitions remain
16 KiB and selector editors are limited to 4 KiB. This does not broaden unknown
mutation fields, grant storage privileges or freeze a production API.
