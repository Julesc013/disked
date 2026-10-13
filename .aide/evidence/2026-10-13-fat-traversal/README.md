# FAT directory paging qualification

Clean native source `b770b3feecb92532c6cc884ec2ea5dbb0455a1f9`, base `4adbb224294075c4301e9cf94e9681ec8bbe58b7`. The recorded Windows lane passes
**110 native groups**, **21 selected standalone headers**, and
**232 tooling tests** with **2 skips**.
Eleven independent methods cover 103 native supplied-region cases, including
17,601 entries in a 1,100-cluster directory chain, deep parents and lossless
name/metadata continuation. Different page partitions reconstruct the same
event stream; every page digest is independently recomputed.

Source ID, capture ID, epoch, source size, volume window and FAT copy are checked
before advancement or callbacks. Required applicability observations bracket
reads and page publication. Withdrawal is permanent; prior pages stay historical.
Bitmap memory, queue/depth and page work/output budgets are explicit. Original
record/name/boot fragments survive interruption. Deleted metadata is never
invented as live data; contradictory directory words/attributes/state prevent
descent. Cycles and reused directory storage never repeat expansion.

This is private in-process runtime state over supplied bytes. It does not open
files, authenticate its caller's binding, prove an atomic source snapshot, inspect
all file allocation or grant extraction. Held native files, contained workers,
public traversal, recursive extraction/metadata restoration, other formats/hosts,
physical/production recovery, owner acceptance and the full 0.1.0 remain work.
Old capture/selector/plan versions are unchanged. GCC is syntax only.

Exact commands, logs, Git blob/input bindings, context, build/toolchain/import and
artifact hashes are retained. Reproduce at the frozen source with a fresh output
directory; audit retained history without rerunning native tests. Source and
integration revisions are separate. Development failures retain their outcomes.

Four supplemental cases run `check_selected_copies.py` against the same hashed
native probe and frozen fixtures. FAT12/16/32 select copy1 while copy0 contains
conflicting free entries; FAT32 also distinguishes its active copy1 from selected
inactive copy0. Actual read/event offsets remain inside the selected table.
`selected-copy-cases.json` retains those separate outcomes. The frozen native
source and original 103-case campaign are unchanged.
