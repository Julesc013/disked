# Private FAT file-content windows

DE-W045 implements the payload-reading algorithm needed for file extraction.
The [owning contract](../spec/catalog/fat-content-prototype.json) defines expected
behaviour before evaluation. The code is under `runtime/capture/fat_content.*`:
it consumes supplied observations/reader ports, without native handles or writes.

`prepare_fat_content(observation, node_id, expected_binding)` returns an owned map
only after checking the raw boot sector and live file record, geometry, selected
chain and all copy variants, extent arithmetic and content coverage. The caller
must supply the expected source label, epoch, source length, volume window and
copy. Matching these labels does not authenticate a file or prove current freshness.

`map.read(offset, count, reader, limits)` maps logical file bytes onto source
extents. Count is 1..196,608 bytes, with at most 512 callbacks of at most 4,096
bytes each. Callers may lower those limits. All pieces are preflighted before
the first callback; an exceeded budget refuses without I/O. A window clamps at
EOF. Offset at EOF succeeds with empty data; offset beyond EOF refuses.
Fragmentation and nonmonotonic physical order do not change logical order.
Allocated slack and excess clusters never appear as content.

The owned result uses `org.disked.fat-content-window/1` and contains lowercase
hex bytes, logical/source correlation, counts, next offset and bounded read
receipts. `complete` applies to the requested available window, not the whole
file or filesystem. `short_read`, `reader_error` and `invalid_reader_view` retain
only the actual contiguous prefix. Reported callback length is separate from
accepted bytes; thrown exception text is omitted. There are no retries or fills.

Known cross-links, excess allocation, tree completeness and metadata consistency
remain separate observations. They do not establish exclusive ownership or
filesystem health. A selected complete chain can be read while unrelated
traversal is incomplete. Damaged/incomplete or copy-disagreeing selected chains
require a future explicit salvage contract.

The test probe supplies generated sparse bytes, rather than a physical device or
customer source. It independently checks logical byte sequences, physical read
positions, unchanged inputs and failures before callbacks. Native source identity,
held-handle freshness, contained payload workers, public commands/frontends and
destination extraction remain subsequent work. Retained metadata is not itself
a source-opening grant. Full all-platform/storage 0.1.0 remains unfinished.
